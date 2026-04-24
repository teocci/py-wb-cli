"""Sliding-window rate limiters for WB API calls.

Two implementations share the :meth:`acquire` contract:

- :class:`RateLimiter` — in-memory, per-process. Thread-safe but ignores
  other CLI invocations sharing the same token.
- :class:`SharedRateLimiter` — SQLite-backed, cross-process. Two parallel
  ``wb`` processes coordinate through ``~/.wb-cli/rate_limits.db`` so WB
  sees a combined call rate that respects the documented budget.

Both implementations are dictionary-interchangeable at the call site
(:attr:`wb.client.http.WbHttpClient._path_limiters`). The factory in
:mod:`wb.services._factory` picks :class:`SharedRateLimiter` by default
and falls back to :class:`RateLimiter` when the DB cannot be used or the
user sets ``WB_RATE_LIMITER=memory``.
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
    'SellerCooldownLock',
    'compute_token_fingerprint',
    'compute_seller_fingerprint',
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


def compute_seller_fingerprint(token: str) -> str:
    """Return a fingerprint derived from the JWT ``sid`` (seller UUID) claim.

    WB's gateway throttles per seller across *all* endpoints and *all*
    tokens issued to the same seller. Keying the seller-scope limiter by
    the ``sid`` claim (extracted from the JWT payload) lets the
    promotion, analytics, and statistics tokens of the same seller
    coordinate their call rate through a single SQLite row family.

    If the token is not a standard three-part JWT, the payload cannot be
    base64url-decoded, the JSON is malformed, or the ``sid`` claim is
    missing / non-string, the function falls back to
    :func:`compute_token_fingerprint` — scoping silently degrades to
    per-token, which is still better than no global limiter at all.

    Args:
        token: Bearer token (never stored on disk, only its fingerprint).

    Returns:
        First 16 hex chars of the SHA-256 digest of the seller key
        (``'sid:<uuid>'``) when extractable; otherwise the token
        fingerprint as a fallback.
    """
    parts = token.split('.')
    if len(parts) != 3:
        return compute_token_fingerprint(token)
    payload_b64 = parts[1]
    padding = '=' * (-len(payload_b64) % 4)
    try:
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
        payload = json.loads(payload_bytes)
    except (ValueError, binascii.Error, json.JSONDecodeError):
        return compute_token_fingerprint(token)
    sid = payload.get('sid') if isinstance(payload, dict) else None
    if not isinstance(sid, str) or not sid:
        return compute_token_fingerprint(token)
    digest = hashlib.sha256(f'sid:{sid}'.encode('utf-8')).hexdigest()
    return digest[:_TOKEN_FINGERPRINT_LEN]


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


class SellerCooldownLock:
    """Cross-process TTL lock recording a known WB seller-scope cooldown.

    When WB returns a 429 with ``x-ratelimit-reset: N`` (see F-12), F-13
    persists ``(seller_fingerprint, expires_at_ts = now + N)`` to a shared
    SQLite table. Every subsequent ``WbHttpClient.request`` first calls
    :meth:`read_remaining` — if the lock hasn't expired, the HTTP call
    short-circuits with :class:`RateLimitError` carrying the remaining
    seconds. No network attempt is made, so WB's leaky-bucket penalty
    cannot extend.

    Uses the same ``rate_limits.db`` file as :class:`SharedRateLimiter`
    but a separate table (``seller_cooldown``) so the concerns stay
    independent. Rows are TTL-based — once ``expires_at_ts`` passes, a
    call to :meth:`read_remaining` returns ``None`` and subsequent calls
    see no lock. An UPSERT pattern replaces the row on each new 429 so
    the lock always reflects the most recent cooldown value.

    On any ``sqlite3.Error`` at init or during read/record, the instance
    transparently flips to an internal in-memory fallback dict. A single
    module-level warning is emitted per process on the first fallback.

    Attributes:
        db_path: Shared SQLite database file.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialise the lock, creating the DB table on first use.

        Args:
            db_path: Shared SQLite database file (same file as
                :class:`SharedRateLimiter`).
        """
        self._db_path = db_path
        self._fallback: dict[str, float] | None = None

        try:
            self._init_db()
        except (sqlite3.Error, OSError) as exc:
            self._activate_fallback(exc)

    def read_remaining(self, seller_fingerprint: str) -> float | None:
        """Return seconds remaining on the cooldown, or ``None`` if clear.

        An expired row is equivalent to no lock; the method returns
        ``None`` in that case and the stale row is left to be overwritten
        by the next :meth:`record` call.

        Args:
            seller_fingerprint: Output of ``compute_seller_fingerprint``
                for the token whose cooldown we're checking.

        Returns:
            Positive float seconds remaining when the lock is active;
            ``None`` when no active lock exists (either missing or
            expired).
        """
        if self._fallback is not None:
            expires_at = self._fallback.get(seller_fingerprint)
            if expires_at is None:
                return None
            remaining = expires_at - time.time()
            return remaining if remaining > 0 else None

        try:
            conn = sqlite3.connect(str(self._db_path), timeout=_SQLITE_LOCK_TIMEOUT)
            try:
                row = conn.execute(
                    'SELECT expires_at FROM seller_cooldown WHERE seller = ?',
                    (seller_fingerprint,),
                ).fetchone()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            self._activate_fallback(exc)
            return self.read_remaining(seller_fingerprint)

        if row is None:
            return None
        expires_at = row[0]
        remaining = expires_at - time.time()
        return remaining if remaining > 0 else None

    def record(self, seller_fingerprint: str, cooldown_seconds: float) -> None:
        """Store a cooldown deadline for the seller (UPSERT).

        Idempotent — a later call with a shorter cooldown overrides a
        longer one (the most recent WB response is always the authority).

        Args:
            seller_fingerprint: Seller scope key (see
                ``compute_seller_fingerprint``).
            cooldown_seconds: Value from ``x-ratelimit-reset``.
        """
        if cooldown_seconds <= 0:
            return
        expires_at = time.time() + cooldown_seconds
        if self._fallback is not None:
            self._fallback[seller_fingerprint] = expires_at
            return

        try:
            conn = sqlite3.connect(str(self._db_path), timeout=_SQLITE_LOCK_TIMEOUT)
            try:
                conn.execute(
                    'INSERT INTO seller_cooldown (seller, expires_at) '
                    'VALUES (?, ?) ON CONFLICT(seller) DO UPDATE SET '
                    'expires_at = excluded.expires_at',
                    (seller_fingerprint, expires_at),
                )
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            self._activate_fallback(exc)
            self._fallback[seller_fingerprint] = expires_at  # type: ignore[index]

    def _init_db(self) -> None:
        """Create the seller_cooldown table on first use (idempotent)."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path), timeout=_SQLITE_LOCK_TIMEOUT)
        try:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS seller_cooldown (
                    seller     TEXT PRIMARY KEY,
                    expires_at REAL NOT NULL
                );
            ''')
            conn.commit()
        finally:
            conn.close()

    def _activate_fallback(self, exc: Exception) -> None:
        """Swap to an in-memory dict after a DB failure.

        Mirrors :meth:`SharedRateLimiter._activate_fallback` — a single
        process-wide warning is emitted on the first fallback; future
        failures go silent to avoid log spam.
        """
        global _FALLBACK_WARNED
        self._fallback = {}
        if not _FALLBACK_WARNED:
            _FALLBACK_WARNED = True
            logger.warning(
                'Seller cooldown lock DB unavailable (%s); falling back to '
                'in-memory lock. Cross-process cooldown coordination disabled '
                'for this process.',
                exc,
            )
