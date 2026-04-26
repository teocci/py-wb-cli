"""Per-(token, endpoint) rate-limit budget driven by WB response headers.

The :class:`EndpointBudget` is the single source of truth for "may I call
this endpoint right now, and if not, how long must I wait?" It supersedes
the F-13 ``SellerCooldownLock`` (seller-wide short-circuit) and the static
seller-global limiter, replacing both with state derived from WB's own
``x-ratelimit-limit`` / ``x-ratelimit-remaining`` / ``x-ratelimit-reset``
headers as observed on every response.

Design summary
--------------

- One row per ``(token_fingerprint, endpoint)`` in a SQLite table named
  ``endpoint_budget``. Cross-process coordination via WAL on the same
  ``~/.wb-cli/rate_limits.db`` file used by :class:`SharedRateLimiter`.
- :meth:`reserve` is called before each request. When live header data
  exists for the bucket, it consumes a slot or sleeps until the bucket
  refills. When no live data exists yet (or the previous window has
  expired), it falls back to a static prior (the per-endpoint sliding
  window from :data:`wb.core.rate_limits.ENDPOINT_LIMITS`) implemented
  by :class:`SharedRateLimiter`.
- :meth:`observe` is called after every response (200 or 429) — it
  upserts the bucket state from the response headers. WB telling us
  ``remaining=0, reset=3499`` only locks *this* endpoint; other endpoints
  continue normally.
- :meth:`read_all` returns the full table for diagnostics
  (``wb rate status``).

On any ``sqlite3.Error`` at construction or during read/write, the
instance flips to an in-memory fallback dict — same pattern as
:class:`SellerCooldownLock`. A single module-level warning is emitted on
the first fallback per process.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

__all__ = [
    'BudgetRow',
    'EndpointBudget',
    'parse_int_header',
    'parse_rate_limit_wait',
]

logger = logging.getLogger(__name__)

_SQLITE_LOCK_TIMEOUT = 30.0
_FALLBACK_WARNED = False

# Header preference order for "how many seconds until the NEXT request is
# legal" (see docs/web/rate-limits.md):
#
# 1. ``x-ratelimit-retry`` — WB's official "you can retry the request in N
#    seconds" header. Smallest of the three on a 429 (e.g. 2 s in the doc's
#    example). Use this whenever present — it's the most precise.
# 2. ``Retry-After`` — HTTP standard fallback. WB doesn't send it, but other
#    intermediaries (proxies, gateways) might.
# 3. ``x-ratelimit-reset`` — WB's "full burst is back to max in N seconds"
#    header. Largest value (e.g. 29 s in the doc's example). Worst-case
#    fallback when neither of the above is present — over-waits but is
#    always safe.
#
# Walking the list in preference order and returning the first hit gives
# the most precise wait we can derive from what WB sent.
_WAIT_HEADERS = ('x-ratelimit-retry', 'Retry-After', 'x-ratelimit-reset')
_REMAINING_HEADERS = ('x-ratelimit-remaining',)
_LIMIT_HEADERS = ('x-ratelimit-limit',)


@dataclass(slots=True, frozen=True)
class BudgetRow:
    """One persisted bucket entry.

    Attributes:
        token_fp: SHA-256 prefix of the bearer token.
        endpoint: API endpoint path (constant from
            :mod:`wb.core.constants`).
        seller_id: Plaintext ``sid`` from the JWT, or ``None`` when the
            token has no extractable sid.
        bucket_limit: Last-seen ``x-ratelimit-limit`` value, or ``None``
            when WB never sent it.
        remaining: Last-seen ``x-ratelimit-remaining`` value, decremented
            in-place per call, or ``None`` when WB never sent it.
        reset_at: Wall-clock epoch seconds when the bucket refills.
        last_seen: Wall-clock epoch seconds when these headers were
            observed.
    """

    token_fp: str
    endpoint: str
    seller_id: str | None
    bucket_limit: int | None
    remaining: int | None
    reset_at: float
    last_seen: float


def parse_int_header(headers: 'httpx.Headers | dict[str, str]', names: tuple[str, ...]) -> int | None:
    """Return the first header value parsed as an int, or ``None``.

    Args:
        headers: A mapping with case-insensitive lookup (httpx.Headers is
            preferred but plain dicts work for tests).
        names: Header names to try in order.

    Returns:
        Parsed integer when present and parseable; otherwise ``None``.
    """
    for name in names:
        raw = headers.get(name)
        if raw is None:
            continue
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            continue
    return None


def parse_rate_limit_wait(headers: 'httpx.Headers | dict[str, str]') -> float | None:
    """Return the most precise "wait this long before next call" value.

    Walks the header preference list (see :data:`_WAIT_HEADERS`) and
    returns the first parseable positive number. ``X-Ratelimit-Retry``
    is preferred over ``X-Ratelimit-Reset`` because they encode different
    things — Retry is when the *next* request is legal, Reset is when
    the *full* burst is restored. Conflating them (the previous
    implementation did) over-waits significantly: the WB doc gives the
    example Retry=2 s vs Reset=29 s — a 14× over-wait.

    Args:
        headers: A mapping with case-insensitive lookup.

    Returns:
        Positive float seconds to wait; ``None`` when no header parsed.
    """
    for name in _WAIT_HEADERS:
        raw = headers.get(name)
        if not raw:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


class EndpointBudget:
    """Cross-process, header-driven rate-limit budget per (token, endpoint).

    Wraps the ``endpoint_budget`` SQLite table. Safe for parallel use
    from threads in the same process and from sibling ``wb`` processes
    sharing the same DB file.
    """

    def __init__(self, db_path: Path, *, force_memory: bool = False) -> None:
        """Initialise the budget store, creating the DB table on first use.

        Args:
            db_path: Shared SQLite database file (same file as
                :class:`wb.core.rate_limiter.SharedRateLimiter`).
            force_memory: When ``True``, skip the SQLite path entirely
                and use the in-memory fallback dict from the start.
                Lets the ``WB_RATE_LIMITER=memory`` diagnostic env var
                opt out of cross-process coordination without relying
                on a DB-failure trigger. ``False`` (the default) tries
                SQLite first and only flips to memory on
                ``sqlite3.Error`` / ``OSError``.
        """
        self._db_path = db_path
        self._fallback: dict[tuple[str, str], dict] | None = None
        self._fallback_lock = threading.Lock()
        self._bootstrap_limiters: dict[tuple[str, str], object] = {}
        self._bootstrap_lock = threading.Lock()

        if force_memory:
            with self._fallback_lock:
                self._fallback = {}
            return

        try:
            self._init_db()
        except (sqlite3.Error, OSError) as exc:
            self._activate_fallback(exc)

    def reserve(
            self,
            token_fp: str,
            endpoint: str,
            *,
            prior: tuple[int, float],
            seller_id: str | None = None,
            max_wait_seconds: float | None = None,
    ) -> None:
        """Block until a call slot is available.

        Behaviour, depending on stored state for ``(token_fp, endpoint)``:

        - **No row**: fall back to the static prior (per-endpoint sliding
          window via :class:`wb.core.rate_limiter.SharedRateLimiter`).
          Blocks via the limiter until a slot is available; no row is
          written until the next :meth:`observe` call populates it from
          real headers.
        - **Row present, ``remaining > 0``** (or ``remaining is None``
          but ``reset_at > now``): decrement provisionally and return
          immediately.
        - **Row present, ``remaining == 0``**: sleep until the larger of
          ``reset_at`` (the wait derived from WB's ``X-Ratelimit-Retry``
          when the last response carried it) and ``last_seen + interval``
          where ``interval = prior_period / prior_calls`` (conservative
          fallback per the WB doc's "interval = period/limit" formula —
          e.g. for 300/min the interval is 200 ms, not 60 s). After the
          sleep, re-evaluate.

        The conservative fallback exists because WB sends only
        ``X-Ratelimit-Remaining`` on 200 responses (no wait header);
        without a fallback the next :meth:`reserve` would treat the row
        as expired and fire a request that gets 429'd, escalating the
        penalty.

        Args:
            token_fp: SHA-256 prefix of the token.
            endpoint: API endpoint path constant.
            prior: ``(calls, period_seconds)`` static window. Used both
                for bootstrap and to derive the interval-based fallback
                wait (``period_seconds / calls``) when WB sends
                ``remaining=0`` without a wait header.
            seller_id: Plaintext ``sid`` from the token's JWT for
                future :meth:`observe` calls; not stored here because
                bootstrap doesn't write a row.
            max_wait_seconds: Optional ceiling on the time
                :meth:`reserve` may sleep before the next legal call.
                When the computed wait would exceed this, the method
                raises :class:`wb.core.exceptions.RateLimitError`
                with ``retry_after`` set to the actual wait — letting
                callers (e.g. the CLI) fail fast on multi-minute
                cooldowns instead of blocking the user. ``None``
                disables the ceiling and reverts to pure-blocking
                semantics.

        Raises:
            RateLimitError: When the required wait exceeds
                ``max_wait_seconds``. ``retry_after`` carries the wait.
        """
        del seller_id  # only used by observe(); reserve doesn't write rows
        interval = prior[1] / prior[0]
        while True:
            row = self._read_row(token_fp, endpoint)
            now = time.time()

            if row is None:
                self._bootstrap_acquire(token_fp, endpoint, prior)
                return

            if row.remaining is None or row.remaining > 0:
                if row.reset_at <= now:
                    # No active window — bootstrap. observe() will populate
                    # the row from the next response's headers.
                    self._bootstrap_acquire(token_fp, endpoint, prior)
                    return
                if row.remaining is not None:
                    self._decrement(token_fp, endpoint, now)
                return

            # remaining == 0: locked until the larger of WB's authoritative
            # wait (reset_at, derived from X-Ratelimit-Retry on 429) and
            # our interval-based fallback.
            deadline = max(row.reset_at, row.last_seen + interval)
            wait = deadline - now
            if wait <= 0:
                # Deadline already passed → bootstrap fresh.
                self._bootstrap_acquire(token_fp, endpoint, prior)
                return
            if max_wait_seconds is not None and wait > max_wait_seconds:
                from wb.core.exceptions import RateLimitError
                raise RateLimitError(
                    f'Endpoint {endpoint} locked for ~{wait:.0f}s '
                    f'(exceeds max_wait={max_wait_seconds:.0f}s)',
                    retry_after=wait,
                )
            time.sleep(wait)
            # Loop to re-evaluate.

    def observe(
            self,
            token_fp: str,
            endpoint: str,
            response: 'httpx.Response',
            *,
            seller_id: str | None = None,
    ) -> None:
        """Update the bucket state from a response's rate-limit headers.

        Called on every 2xx and 4xx response. When WB sends none of the
        rate-limit headers, this method is a no-op so prior state stays.

        Args:
            token_fp: SHA-256 prefix of the token that made the request.
            endpoint: API endpoint path constant.
            response: The httpx response (only ``.headers`` is read).
            seller_id: Plaintext ``sid`` for diagnostics; stored as a
                non-key column.
        """
        self._observe_headers(token_fp, endpoint, response.headers, seller_id)

    def observe_headers(
            self,
            token_fp: str,
            endpoint: str,
            headers: 'httpx.Headers | dict[str, str]',
            *,
            seller_id: str | None = None,
    ) -> None:
        """Variant of :meth:`observe` that takes a raw headers mapping.

        Useful for tests that don't want to construct a full ``Response``.
        """
        self._observe_headers(token_fp, endpoint, headers, seller_id)

    def _observe_headers(
            self,
            token_fp: str,
            endpoint: str,
            headers: 'httpx.Headers | dict[str, str]',
            seller_id: str | None,
    ) -> None:
        bucket_limit = parse_int_header(headers, _LIMIT_HEADERS)
        remaining = parse_int_header(headers, _REMAINING_HEADERS)
        wait_in = parse_rate_limit_wait(headers)

        if bucket_limit is None and remaining is None and wait_in is None:
            return

        now = time.time()
        # ``reset_at`` here means "soonest the next call is legal" —
        # derived from X-Ratelimit-Retry preferentially (see
        # :func:`parse_rate_limit_wait`). Falls back to ``now`` when WB
        # sent no wait header (typical for 200 responses); the
        # prior-based fallback in :meth:`reserve` covers that case.
        reset_at = now + (wait_in or 0.0)
        self._upsert(
            token_fp=token_fp,
            endpoint=endpoint,
            seller_id=seller_id,
            bucket_limit=bucket_limit,
            remaining=remaining,
            reset_at=reset_at,
            last_seen=now,
        )

    def read_all(self) -> list[BudgetRow]:
        """Return every persisted bucket row.

        Used by ``wb rate status`` to render the full per-(seller, token,
        endpoint) state without a per-token gating filter. Expired rows
        are still returned — the caller decides how to display them.

        Returns:
            All rows in the table (or fallback dict), unordered.
        """
        if self._fallback is not None:
            with self._fallback_lock:
                return [
                    BudgetRow(
                        token_fp=k[0],
                        endpoint=k[1],
                        seller_id=v.get('seller_id'),
                        bucket_limit=v.get('bucket_limit'),
                        remaining=v.get('remaining'),
                        reset_at=v['reset_at'],
                        last_seen=v['last_seen'],
                    )
                    for k, v in self._fallback.items()
                ]

        try:
            conn = sqlite3.connect(str(self._db_path), timeout=_SQLITE_LOCK_TIMEOUT)
            try:
                rows = conn.execute(
                    'SELECT token_fp, endpoint, seller_id, bucket_limit, '
                    'remaining, reset_at, last_seen FROM endpoint_budget'
                ).fetchall()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            self._activate_fallback(exc)
            return self.read_all()

        return [
            BudgetRow(
                token_fp=r[0],
                endpoint=r[1],
                seller_id=r[2],
                bucket_limit=r[3],
                remaining=r[4],
                reset_at=r[5],
                last_seen=r[6],
            )
            for r in rows
        ]

    # ── internals ──────────────────────────────────────────────────────

    def _read_row(self, token_fp: str, endpoint: str) -> BudgetRow | None:
        if self._fallback is not None:
            with self._fallback_lock:
                v = self._fallback.get((token_fp, endpoint))
            if v is None:
                return None
            return BudgetRow(
                token_fp=token_fp,
                endpoint=endpoint,
                seller_id=v.get('seller_id'),
                bucket_limit=v.get('bucket_limit'),
                remaining=v.get('remaining'),
                reset_at=v['reset_at'],
                last_seen=v['last_seen'],
            )

        try:
            conn = sqlite3.connect(str(self._db_path), timeout=_SQLITE_LOCK_TIMEOUT)
            try:
                row = conn.execute(
                    'SELECT seller_id, bucket_limit, remaining, reset_at, last_seen '
                    'FROM endpoint_budget WHERE token_fp = ? AND endpoint = ?',
                    (token_fp, endpoint),
                ).fetchone()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            self._activate_fallback(exc)
            return self._read_row(token_fp, endpoint)

        if row is None:
            return None
        return BudgetRow(
            token_fp=token_fp,
            endpoint=endpoint,
            seller_id=row[0],
            bucket_limit=row[1],
            remaining=row[2],
            reset_at=row[3],
            last_seen=row[4],
        )

    def _decrement(self, token_fp: str, endpoint: str, now: float) -> None:
        if self._fallback is not None:
            with self._fallback_lock:
                v = self._fallback.get((token_fp, endpoint))
                if v is None:
                    return
                if v.get('remaining') is not None and v['remaining'] > 0:
                    v['remaining'] -= 1
                v['last_seen'] = now
            return

        try:
            conn = sqlite3.connect(str(self._db_path), timeout=_SQLITE_LOCK_TIMEOUT)
            try:
                conn.execute(
                    'UPDATE endpoint_budget '
                    'SET remaining = MAX(remaining - 1, 0), last_seen = ? '
                    'WHERE token_fp = ? AND endpoint = ? AND remaining IS NOT NULL',
                    (now, token_fp, endpoint),
                )
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            self._activate_fallback(exc)
            self._decrement(token_fp, endpoint, now)

    def _upsert(
            self,
            *,
            token_fp: str,
            endpoint: str,
            seller_id: str | None,
            bucket_limit: int | None,
            remaining: int | None,
            reset_at: float,
            last_seen: float,
    ) -> None:
        if self._fallback is not None:
            with self._fallback_lock:
                self._fallback[(token_fp, endpoint)] = {
                    'seller_id': seller_id,
                    'bucket_limit': bucket_limit,
                    'remaining': remaining,
                    'reset_at': reset_at,
                    'last_seen': last_seen,
                }
            return

        try:
            conn = sqlite3.connect(str(self._db_path), timeout=_SQLITE_LOCK_TIMEOUT)
            try:
                conn.execute(
                    'INSERT INTO endpoint_budget '
                    '(token_fp, endpoint, seller_id, bucket_limit, remaining, reset_at, last_seen) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?) '
                    'ON CONFLICT(token_fp, endpoint) DO UPDATE SET '
                    'seller_id = COALESCE(excluded.seller_id, endpoint_budget.seller_id), '
                    'bucket_limit = COALESCE(excluded.bucket_limit, endpoint_budget.bucket_limit), '
                    'remaining = excluded.remaining, '
                    'reset_at = excluded.reset_at, '
                    'last_seen = excluded.last_seen',
                    (token_fp, endpoint, seller_id, bucket_limit, remaining, reset_at, last_seen),
                )
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            self._activate_fallback(exc)
            self._upsert(
                token_fp=token_fp,
                endpoint=endpoint,
                seller_id=seller_id,
                bucket_limit=bucket_limit,
                remaining=remaining,
                reset_at=reset_at,
                last_seen=last_seen,
            )

    def _bootstrap_acquire(
            self,
            token_fp: str,
            endpoint: str,
            prior: tuple[int, float],
    ) -> None:
        """Block on the static per-endpoint sliding window.

        Reuses :class:`wb.core.rate_limiter.SharedRateLimiter`, which
        writes to a separate ``rate_limit_log`` table on the same DB
        file. Cached per ``(token_fp, endpoint)`` so we don't reopen the
        DB schema on every call.
        """
        from wb.core.rate_limiter import SharedRateLimiter

        key = (token_fp, endpoint)
        with self._bootstrap_lock:
            limiter = self._bootstrap_limiters.get(key)
            if limiter is None:
                limiter = SharedRateLimiter(
                    calls=prior[0],
                    period=prior[1],
                    token_fingerprint=token_fp,
                    endpoint=endpoint,
                    db_path=self._db_path,
                )
                self._bootstrap_limiters[key] = limiter
        limiter.acquire()

    def _init_db(self) -> None:
        """Create the endpoint_budget table on first use (idempotent)."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path), timeout=_SQLITE_LOCK_TIMEOUT)
        try:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS endpoint_budget (
                    token_fp     TEXT NOT NULL,
                    endpoint     TEXT NOT NULL,
                    seller_id    TEXT,
                    bucket_limit INTEGER,
                    remaining    INTEGER,
                    reset_at     REAL NOT NULL,
                    last_seen    REAL NOT NULL,
                    PRIMARY KEY (token_fp, endpoint)
                );
            ''')
            conn.commit()
        finally:
            conn.close()

    def _activate_fallback(self, exc: Exception) -> None:
        """Swap to an in-memory dict after a DB failure.

        Mirrors :meth:`SellerCooldownLock._activate_fallback`. One
        process-wide warning is emitted on the first fallback.
        """
        global _FALLBACK_WARNED
        with self._fallback_lock:
            if self._fallback is None:
                self._fallback = {}
        if not _FALLBACK_WARNED:
            _FALLBACK_WARNED = True
            logger.warning(
                'Endpoint budget DB unavailable (%s); falling back to '
                'in-memory state. Cross-process budget coordination disabled '
                'for this process.',
                exc,
            )
