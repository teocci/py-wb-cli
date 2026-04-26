"""Sliding-window rate limiters and JWT helpers for WB API calls.

Two limiter implementations share the :meth:`acquire` contract:

- :class:`RateLimiter` — in-memory, per-process. Thread-safe but ignores
  other CLI invocations sharing the same token.
- :class:`SharedRateLimiter` — SQLite-backed, cross-process. Two parallel
  ``wb`` processes coordinate through ``~/.wb-cli/rate_limits.db`` so WB
  sees a combined call rate that respects the documented budget.

Since R-1, the runtime authority for "may I call this endpoint right
now?" lives in :class:`wb.core.endpoint_budget.EndpointBudget` (driven
by WB's own ``X-Ratelimit-*`` response headers).
:class:`SharedRateLimiter` is still used by ``EndpointBudget`` as a
bootstrap window for endpoints that have no observed header data yet.

This module also exposes the JWT helpers that derive token-keyed
identifiers from a bearer token without ever persisting the token
itself: :func:`compute_token_fingerprint` (SHA-256 prefix used as the
budget table's primary key) and :func:`extract_seller_id` (plaintext
``sid`` claim used as a non-key column for ``wb rate status`` grouping).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import sqlite3
import threading
import time
from collections import deque
from pathlib import Path

__all__ = [
    'RateLimiter',
    'SharedRateLimiter',
    'compute_token_fingerprint',
    'extract_seller_id',
]

logger = logging.getLogger(__name__)

_TOKEN_FINGERPRINT_LEN = 16
_SQLITE_LOCK_TIMEOUT = 30.0
_FALLBACK_WARNED = False


def compute_token_fingerprint(token: str) -> str:
    """Return a non-reversible prefix of the token for limiter keying.

    Uses the same algorithm as :mod:`wb.storage.response_cache` so a
    future audit can correlate cache rows with limiter rows by token
    fingerprint without ever storing the raw token.

    Args:
        token: Bearer token (never stored on disk).

    Returns:
        First 16 hex chars of the SHA-256 digest.
    """
    digest = hashlib.sha256(token.encode('utf-8')).hexdigest()
    return digest[:_TOKEN_FINGERPRINT_LEN]


def extract_seller_id(token: str) -> str | None:
    """Extract the plaintext ``sid`` (seller UUID) claim from a JWT.

    Used as a non-key column in the ``endpoint_budget`` table so
    ``wb rate status`` can group rows by plaintext seller ID — every
    token of the same seller resolves to the same ``sid`` regardless of
    which API category (promotion, analytics, statistics, …) it was
    issued for.

    Returns ``None`` when the token isn't a 3-part JWT, the payload
    can't be base64url-decoded, the JSON is malformed, or the ``sid``
    claim is missing / non-string.

    Args:
        token: Bearer token (never stored on disk).

    Returns:
        The seller UUID as a string, or ``None`` when not extractable.
    """
    parts = token.split('.')
    if len(parts) != 3:
        return None
    payload_b64 = parts[1]
    padding = '=' * (-len(payload_b64) % 4)
    try:
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
        payload = json.loads(payload_bytes)
    except (ValueError, binascii.Error, json.JSONDecodeError):
        return None
    sid = payload.get('sid') if isinstance(payload, dict) else None
    return sid if isinstance(sid, str) and sid else None


class RateLimiter:
    """Thread-safe in-memory sliding-window rate limiter.

    Tracks timestamps of recent calls in a fixed-size deque. On each
    :meth:`acquire`, expired timestamps are evicted, and the caller sleeps
    until a slot opens if the window is full.

    Attributes:
        calls: Maximum calls allowed within ``period`` seconds.
        period: Sliding window size in seconds.

    Example::

        limiter = RateLimiter(calls=3, period=60.0)
        for campaign_id in ids:
            limiter.acquire()
            client.get_fullstats(campaign_id)
    """

    def __init__(self, calls: int, period: float) -> None:
        """Initialise the rate limiter.

        Args:
            calls: Maximum number of calls within the window (must be >= 1).
            period: Window duration in seconds (must be > 0).

        Raises:
            ValueError: If ``calls < 1`` or ``period <= 0``.
        """
        if calls < 1:
            raise ValueError(f'calls must be >= 1, got {calls}')
        if period <= 0:
            raise ValueError(f'period must be > 0, got {period}')

        self._calls = calls
        self._period = period
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until a call slot is available, then record the call.

        If the sliding window is full (``calls`` timestamps within the last
        ``period`` seconds), this method sleeps until the oldest timestamp
        expires. Thread-safe: multiple threads share the same window counter.
        """
        with self._lock:
            self._evict_expired()

            if len(self._timestamps) >= self._calls:
                oldest = self._timestamps[0]
                sleep_for = self._period - (time.monotonic() - oldest)
                if sleep_for > 0:
                    time.sleep(sleep_for)
                self._evict_expired()

            self._timestamps.append(time.monotonic())

    def _evict_expired(self) -> None:
        """Remove timestamps that have fallen outside the current window."""
        cutoff = time.monotonic() - self._period
        while self._timestamps and self._timestamps[0] <= cutoff:
            self._timestamps.popleft()


class SharedRateLimiter:
    """Cross-process sliding-window rate limiter backed by SQLite WAL.

    A single SQLite file at ``db_path`` stores one row per historical
    API call as ``(token, endpoint, ts)``. Each :meth:`acquire` opens a
    ``BEGIN IMMEDIATE`` transaction to prune expired rows and count
    in-window rows atomically, then either inserts a new row (slot
    available) or releases the lock and sleeps until the oldest row
    ages out. The sleep happens outside the transaction so parallel
    processes are never blocked on an idle limiter.

    If the database cannot be opened, becomes locked beyond the
    configured timeout, or any ``sqlite3.Error`` is raised during
    :meth:`acquire`, the instance transparently flips to an internal
    :class:`RateLimiter` and records subsequent calls there. A single
    module-level warning is emitted per process on the first fallback.

    Attributes:
        calls: Maximum calls allowed within ``period`` seconds.
        period: Sliding window size in seconds.
        endpoint: API endpoint path; part of the row key.
        token_fingerprint: SHA-256 prefix of the token; part of the row key.
        db_path: SQLite database path shared across processes.
    """

    def __init__(
            self,
            calls: int,
            period: float,
            *,
            token_fingerprint: str,
            endpoint: str,
            db_path: Path,
    ) -> None:
        """Initialise the shared limiter, creating the DB on first use.

        If schema creation fails (permissions, disk, corrupt file), the
        instance activates the in-memory fallback immediately so callers
        never see the failure at :meth:`acquire`.

        Args:
            calls: Maximum calls within the window (must be >= 1).
            period: Window duration in seconds (must be > 0).
            token_fingerprint: Stable prefix identifying the token pool.
            endpoint: API endpoint path (second part of the row key).
            db_path: Shared SQLite database file.

        Raises:
            ValueError: If ``calls < 1`` or ``period <= 0``.
        """
        if calls < 1:
            raise ValueError(f'calls must be >= 1, got {calls}')
        if period <= 0:
            raise ValueError(f'period must be > 0, got {period}')

        self._calls = calls
        self._period = period
        self._token_fingerprint = token_fingerprint
        self._endpoint = endpoint
        self._db_path = db_path
        self._fallback: RateLimiter | None = None

        try:
            self._init_db()
        except (sqlite3.Error, OSError) as exc:
            self._activate_fallback(exc)

    def acquire(self) -> None:
        """Block until a call slot is available, then record the call.

        On any SQLite failure, switch to the in-memory fallback once
        and delegate future calls to it.
        """
        if self._fallback is not None:
            self._fallback.acquire()
            return

        while True:
            try:
                sleep_for = self._try_acquire_once()
            except sqlite3.Error as exc:
                self._activate_fallback(exc)
                self._fallback.acquire()  # type: ignore[union-attr]
                return
            if sleep_for <= 0:
                return
            time.sleep(sleep_for)

    def _try_acquire_once(self) -> float:
        """Attempt to reserve a slot atomically.

        Returns:
            ``0.0`` if a slot was reserved (a row was inserted); otherwise
            the number of seconds to sleep before the next attempt.

        Raises:
            sqlite3.Error: Propagated from the underlying driver — the
                caller converts these into a transparent fallback.
        """
        conn = sqlite3.connect(str(self._db_path), timeout=_SQLITE_LOCK_TIMEOUT)
        try:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('BEGIN IMMEDIATE')
            now = time.time()
            cutoff = now - self._period
            conn.execute(
                'DELETE FROM rate_limit_log '
                'WHERE token = ? AND endpoint = ? AND ts < ?',
                (self._token_fingerprint, self._endpoint, cutoff),
            )
            row = conn.execute(
                'SELECT COUNT(*), MIN(ts) FROM rate_limit_log '
                'WHERE token = ? AND endpoint = ?',
                (self._token_fingerprint, self._endpoint),
            ).fetchone()
            count = row[0] or 0
            oldest = row[1]
            if count < self._calls:
                conn.execute(
                    'INSERT INTO rate_limit_log (token, endpoint, ts) '
                    'VALUES (?, ?, ?)',
                    (self._token_fingerprint, self._endpoint, now),
                )
                conn.commit()
                return 0.0
            conn.commit()
            return max(0.0, self._period - (now - oldest))
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create the shared table on first use (idempotent)."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path), timeout=_SQLITE_LOCK_TIMEOUT)
        try:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS rate_limit_log (
                    token    TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    ts       REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_rate_limit_log_key_ts
                    ON rate_limit_log (token, endpoint, ts);
            ''')
            conn.commit()
        finally:
            conn.close()

    def _activate_fallback(self, exc: Exception) -> None:
        """Swap this instance into in-memory mode after a DB failure.

        Args:
            exc: The underlying error that triggered the fallback; recorded
                in the single process-wide warning so the operator can
                diagnose the cause (permissions, corruption, etc.).
        """
        global _FALLBACK_WARNED
        self._fallback = RateLimiter(self._calls, self._period)
        if not _FALLBACK_WARNED:
            _FALLBACK_WARNED = True
            logger.warning(
                'Shared rate limiter DB unavailable (%s); falling back to '
                'in-memory rate limiter. Parallel wb processes will no longer '
                'coordinate rate limits. Set WB_RATE_LIMITER=memory to silence.',
                exc,
            )
