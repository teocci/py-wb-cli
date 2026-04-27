"""Per-(token, endpoint, params) HTTP-layer response cache.

Pairs with :mod:`wb.core.cache_policy` (which decides eligibility, TTL,
and invalidation) and :mod:`wb.client.http` (which integrates the cache
into the request flow).

Storage shape
-------------

One SQLite file at ``~/.wb-cli/request_cache.db`` (WAL). The schema:

.. code-block:: sql

   CREATE TABLE request_cache (
       token_fp     TEXT NOT NULL,
       endpoint     TEXT NOT NULL,
       params_hash  TEXT NOT NULL,
       payload      BLOB NOT NULL,
       cached_at    REAL NOT NULL,
       expires_at   REAL NOT NULL,
       PRIMARY KEY (token_fp, endpoint, params_hash)
   ) WITHOUT ROWID;

WAL mode lets multiple ``wb`` processes read/write the same file; the
PRIMARY KEY enforces single-row-per-call so ``INSERT OR REPLACE`` is
idempotent across concurrent writers.

On any ``sqlite3.Error`` at construction or during read/write, the
instance flips to an in-memory fallback dict — so the cache never blocks
the HTTP path. A single warning is emitted on the first fallback per
process. The fallback is also accessible via ``force_memory=True`` for
tests and the ``WB_REQUEST_CACHE=disabled`` diagnostic env path.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

__all__ = ['CacheRow', 'RequestCache']

logger = logging.getLogger(__name__)

_SQLITE_LOCK_TIMEOUT = 30.0
_FALLBACK_WARNED = False


@dataclass(slots=True, frozen=True)
class CacheRow:
    """One persisted cache row.

    Attributes:
        token_fp: SHA-256 prefix of the bearer token.
        endpoint: API endpoint path.
        params_hash: Canonical hash of (params, body) — see
            :func:`wb.core.cache_policy.canonical_hash`.
        payload: Cached response body bytes.
        cached_at: Wall-clock epoch seconds when the row was written.
        expires_at: Wall-clock epoch seconds when the row should be
            treated as expired.
    """

    token_fp: str
    endpoint: str
    params_hash: str
    payload: bytes
    cached_at: float
    expires_at: float


class RequestCache:
    """Cross-process HTTP response cache with cooldown-tied TTL.

    Wraps the ``request_cache`` SQLite table. Safe for parallel use from
    threads in the same process and from sibling ``wb`` processes
    sharing the same DB file.
    """

    def __init__(self, db_path: Path, *, force_memory: bool = False) -> None:
        """Initialise the cache, creating the DB table on first use.

        Args:
            db_path: SQLite database file. Parent dirs are created.
            force_memory: When ``True``, skip SQLite entirely and use the
                in-process fallback dict from the start. Lets the
                ``WB_REQUEST_CACHE=disabled`` diagnostic path opt out of
                cross-process state without relying on a DB-failure
                trigger. ``False`` (default) tries SQLite first and
                only flips to memory on ``sqlite3.Error`` / ``OSError``.
        """
        self._db_path = db_path
        self._fallback: dict[tuple[str, str, str], CacheRow] | None = None
        self._fallback_lock = threading.Lock()

        if force_memory:
            with self._fallback_lock:
                self._fallback = {}
            return

        try:
            self._init_db()
        except (sqlite3.Error, OSError) as exc:
            self._activate_fallback(exc)

    # ── Public API ─────────────────────────────────────────────────────

    def get(
            self,
            token_fp: str,
            endpoint: str,
            params_hash: str,
            *,
            max_age_seconds: float,
    ) -> bytes | None:
        """Return cached payload bytes when fresh, else ``None``.

        A row is fresh when both:

        - its ``expires_at`` is in the future, **and**
        - ``now - cached_at <= max_age_seconds``.

        The second clause lets the caller cap how stale a cached entry
        may be regardless of the row's own TTL — useful when the policy
        derives a tighter TTL than the row was originally written with
        (e.g. token type changed). Pass ``max_age_seconds=float('inf')``
        to ignore the second clause.

        Side effect: prunes other expired rows for the same
        ``(token_fp, endpoint)`` opportunistically. Bounded growth.

        Args:
            token_fp: Token fingerprint.
            endpoint: API path.
            params_hash: Canonical hash of (params, body).
            max_age_seconds: Maximum acceptable age in seconds.

        Returns:
            The payload bytes, or ``None`` when no fresh entry exists.
        """
        now = time.time()
        if self._fallback is not None:
            return self._get_fallback(
                token_fp, endpoint, params_hash, now, max_age_seconds,
            )
        try:
            conn = sqlite3.connect(str(self._db_path), timeout=_SQLITE_LOCK_TIMEOUT)
            try:
                row = conn.execute(
                    'SELECT payload, cached_at, expires_at '
                    'FROM request_cache '
                    'WHERE token_fp = ? AND endpoint = ? AND params_hash = ?',
                    (token_fp, endpoint, params_hash),
                ).fetchone()
                # Opportunistic prune of *other* expired rows for the
                # same (token, endpoint). Single statement, scoped tight.
                conn.execute(
                    'DELETE FROM request_cache '
                    'WHERE token_fp = ? AND endpoint = ? AND expires_at <= ?',
                    (token_fp, endpoint, now),
                )
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            self._activate_fallback(exc)
            return self.get(
                token_fp, endpoint, params_hash,
                max_age_seconds=max_age_seconds,
            )

        if row is None:
            return None
        payload, cached_at, expires_at = row
        if expires_at <= now:
            return None
        if now - cached_at > max_age_seconds:
            return None
        return bytes(payload)

    def put(
            self,
            token_fp: str,
            endpoint: str,
            params_hash: str,
            payload: bytes,
            *,
            ttl_seconds: float,
    ) -> None:
        """Insert or replace a cache entry.

        Args:
            token_fp: Token fingerprint.
            endpoint: API path.
            params_hash: Canonical hash of (params, body).
            payload: Response body bytes (the JSON or binary content).
            ttl_seconds: Lifetime in seconds. Non-positive values are a
                no-op (the entry would be expired-on-write).
        """
        if ttl_seconds <= 0:
            return
        now = time.time()
        expires_at = now + ttl_seconds
        if self._fallback is not None:
            with self._fallback_lock:
                self._fallback[(token_fp, endpoint, params_hash)] = CacheRow(
                    token_fp=token_fp,
                    endpoint=endpoint,
                    params_hash=params_hash,
                    payload=bytes(payload),
                    cached_at=now,
                    expires_at=expires_at,
                )
            return

        try:
            conn = sqlite3.connect(str(self._db_path), timeout=_SQLITE_LOCK_TIMEOUT)
            try:
                conn.execute(
                    'INSERT INTO request_cache '
                    '(token_fp, endpoint, params_hash, payload, cached_at, expires_at) '
                    'VALUES (?, ?, ?, ?, ?, ?) '
                    'ON CONFLICT(token_fp, endpoint, params_hash) DO UPDATE SET '
                    'payload = excluded.payload, '
                    'cached_at = excluded.cached_at, '
                    'expires_at = excluded.expires_at',
                    (token_fp, endpoint, params_hash, sqlite3.Binary(payload), now, expires_at),
                )
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            self._activate_fallback(exc)
            self.put(
                token_fp, endpoint, params_hash, payload,
                ttl_seconds=ttl_seconds,
            )

    def invalidate(self, token_fp: str, endpoint: str) -> int:
        """Drop every cache entry for ``(token_fp, endpoint)``.

        Called by the HTTP client after a successful mutation to clear
        downstream reads (see
        :data:`wb.core.cache_policy.MUTATION_INVALIDATES`). Scope is the
        acting token only.

        Args:
            token_fp: Token fingerprint.
            endpoint: API path of the read endpoint to invalidate.

        Returns:
            Number of rows removed (zero on fallback / on error).
        """
        if self._fallback is not None:
            with self._fallback_lock:
                keys = [
                    k for k in self._fallback
                    if k[0] == token_fp and k[1] == endpoint
                ]
                for k in keys:
                    del self._fallback[k]
                return len(keys)

        try:
            conn = sqlite3.connect(str(self._db_path), timeout=_SQLITE_LOCK_TIMEOUT)
            try:
                cur = conn.execute(
                    'DELETE FROM request_cache '
                    'WHERE token_fp = ? AND endpoint = ?',
                    (token_fp, endpoint),
                )
                conn.commit()
                return cur.rowcount
            finally:
                conn.close()
        except sqlite3.Error as exc:
            self._activate_fallback(exc)
            return self.invalidate(token_fp, endpoint)

    def clear(
            self,
            *,
            token_fp: str | None = None,
            endpoint: str | None = None,
    ) -> int:
        """Remove rows; scope by token, by endpoint, both, or all.

        Args:
            token_fp: When set, restrict to this token.
            endpoint: When set, restrict to this endpoint.

        Returns:
            Number of rows removed.
        """
        if self._fallback is not None:
            with self._fallback_lock:
                keys = [
                    k for k in self._fallback
                    if (token_fp is None or k[0] == token_fp)
                    and (endpoint is None or k[1] == endpoint)
                ]
                for k in keys:
                    del self._fallback[k]
                return len(keys)

        clauses: list[str] = []
        params: list[object] = []
        if token_fp is not None:
            clauses.append('token_fp = ?')
            params.append(token_fp)
        if endpoint is not None:
            clauses.append('endpoint = ?')
            params.append(endpoint)
        where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''

        try:
            conn = sqlite3.connect(str(self._db_path), timeout=_SQLITE_LOCK_TIMEOUT)
            try:
                cur = conn.execute(
                    'DELETE FROM request_cache' + where, tuple(params),
                )
                conn.commit()
                return cur.rowcount
            finally:
                conn.close()
        except sqlite3.Error as exc:
            self._activate_fallback(exc)
            return self.clear(token_fp=token_fp, endpoint=endpoint)

    def read_all(self) -> list[CacheRow]:
        """Return every persisted cache row.

        Used by ``wb api-cache status``. Expired rows are still returned
        — the caller decides how to display them. Bounded by the
        opportunistic prune in :meth:`get`.

        Returns:
            All rows in the table (or fallback dict), unordered.
        """
        if self._fallback is not None:
            with self._fallback_lock:
                return list(self._fallback.values())

        try:
            conn = sqlite3.connect(str(self._db_path), timeout=_SQLITE_LOCK_TIMEOUT)
            try:
                rows = conn.execute(
                    'SELECT token_fp, endpoint, params_hash, payload, '
                    'cached_at, expires_at FROM request_cache'
                ).fetchall()
            finally:
                conn.close()
        except sqlite3.Error as exc:
            self._activate_fallback(exc)
            return self.read_all()

        return [
            CacheRow(
                token_fp=r[0],
                endpoint=r[1],
                params_hash=r[2],
                payload=bytes(r[3]),
                cached_at=r[4],
                expires_at=r[5],
            )
            for r in rows
        ]

    # ── Internals ──────────────────────────────────────────────────────

    def _init_db(self) -> None:
        """Create the table and set WAL mode on first use."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path), timeout=_SQLITE_LOCK_TIMEOUT)
        try:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS request_cache (
                    token_fp     TEXT NOT NULL,
                    endpoint     TEXT NOT NULL,
                    params_hash  TEXT NOT NULL,
                    payload      BLOB NOT NULL,
                    cached_at    REAL NOT NULL,
                    expires_at   REAL NOT NULL,
                    PRIMARY KEY (token_fp, endpoint, params_hash)
                ) WITHOUT ROWID;
                CREATE INDEX IF NOT EXISTS idx_request_cache_expires
                    ON request_cache (expires_at);
            ''')
            conn.commit()
        finally:
            conn.close()

    def _get_fallback(
            self,
            token_fp: str,
            endpoint: str,
            params_hash: str,
            now: float,
            max_age_seconds: float,
    ) -> bytes | None:
        """In-memory fallback get — same semantics as the SQLite path."""
        with self._fallback_lock:
            row = self._fallback.get((token_fp, endpoint, params_hash))
            # Prune other expired rows for (token, endpoint).
            stale = [
                k for k in self._fallback
                if k[0] == token_fp
                and k[1] == endpoint
                and k != (token_fp, endpoint, params_hash)
                and self._fallback[k].expires_at <= now
            ]
            for k in stale:
                del self._fallback[k]
        if row is None:
            return None
        if row.expires_at <= now:
            return None
        if now - row.cached_at > max_age_seconds:
            return None
        return row.payload

    def _activate_fallback(self, exc: Exception) -> None:
        """Flip to the in-memory fallback dict on any persistent error."""
        global _FALLBACK_WARNED
        with self._fallback_lock:
            if self._fallback is None:
                self._fallback = {}
        if not _FALLBACK_WARNED:
            logger.warning(
                'RequestCache SQLite path %s unavailable (%s); '
                'falling back to in-memory cache. Cross-process sharing '
                'is disabled for the rest of this process.',
                self._db_path, exc,
            )
            _FALLBACK_WARNED = True
