"""Read-through SQLite cache for idempotent historical WB API responses.

Responses whose date range is strictly in the past are immutable — caching
them eliminates repeat API calls across parallel CLI invocations (the cache
file is naturally cross-process via SQLite WAL mode).

The cache is keyed by ``(endpoint, token_fingerprint, canonical_params)``.
Token values are never stored — only a SHA-256 prefix. Current-day or
future-date queries bypass the cache entirely: see :func:`is_past_day_range`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from datetime import date as date_cls
from pathlib import Path
from typing import Any

__all__ = [
    'ResponseCache',
    'is_past_day_range',
    'make_cache_key',
    'token_fingerprint',
]

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1
_FINGERPRINT_LEN = 16


class ResponseCache:
    """Persistent SQLite response cache for past-day WB queries.

    Attributes:
        db_path: Absolute path to the SQLite database file.
        retention_days: Entries older than this are dropped on prune().
    """

    def __init__(self, db_path: Path, retention_days: int) -> None:
        """Initialise the cache, creating the DB file if absent.

        Args:
            db_path: SQLite database path. Parent directories are created.
            retention_days: Entries older than this many days are evicted
                when :meth:`prune` runs.
        """
        self._db_path = db_path
        self._retention_days = retention_days
        self._init_db()

    def get(self, key: str) -> Any | None:
        """Look up a cached value by key.

        Args:
            key: Canonical cache key produced by :func:`make_cache_key`.

        Returns:
            Parsed value if present, otherwise ``None``.
        """
        sql = 'SELECT value FROM response_cache WHERE key = ?'
        try:
            with self._connect() as conn:
                row = conn.execute(sql, (key,)).fetchone()
        except sqlite3.Error as exc:
            logger.warning('Response cache read failed: %s', exc)
            return None
        if row is None:
            return None
        try:
            return json.loads(row[0])
        except (TypeError, json.JSONDecodeError) as exc:
            logger.warning('Response cache value decode failed: %s', exc)
            return None

    def put(self, key: str, value: Any) -> None:
        """Store a value under the given key.

        Args:
            key: Canonical cache key produced by :func:`make_cache_key`.
            value: JSON-serialisable payload.
        """
        sql = (
            'INSERT OR REPLACE INTO response_cache (key, value, created_at) '
            'VALUES (?, ?, ?)'
        )
        try:
            payload = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            logger.warning('Response cache value encode failed: %s', exc)
            return
        try:
            with self._connect() as conn:
                conn.execute(sql, (key, payload, time.time()))
        except sqlite3.Error as exc:
            logger.warning('Response cache write failed: %s', exc)

    def prune(self) -> int:
        """Delete entries older than ``retention_days``.

        Returns:
            Number of rows removed.
        """
        cutoff = time.time() - self._retention_days * 86400.0
        sql = 'DELETE FROM response_cache WHERE created_at < ?'
        try:
            with self._connect() as conn:
                cur = conn.execute(sql, (cutoff,))
                return cur.rowcount
        except sqlite3.Error as exc:
            logger.warning('Response cache prune failed: %s', exc)
            return 0

    # ── Internals ───────────────────────────────────────────────────────

    def _init_db(self) -> None:
        """Create the table and set schema version on first use."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            version = conn.execute('PRAGMA user_version').fetchone()[0]
            if version < _SCHEMA_VERSION:
                conn.executescript('''
                    CREATE TABLE IF NOT EXISTS response_cache (
                        key        TEXT PRIMARY KEY,
                        value      TEXT NOT NULL,
                        created_at REAL NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_response_cache_created_at
                        ON response_cache (created_at);
                ''')
                conn.execute(f'PRAGMA user_version = {_SCHEMA_VERSION}')

    def _connect(self) -> sqlite3.Connection:
        """Open a WAL-mode connection; callers use ``with`` to auto-commit."""
        conn = sqlite3.connect(str(self._db_path), timeout=5.0)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        return conn


def is_past_day_range(
        date_from: str,
        date_to: str,
        today: date_cls | None = None,
) -> bool:
    """Return True when both dates are strictly before ``today``.

    Current-day and future ranges are never cached because their values
    may still change. Invalid inputs return False so the caller falls
    through to the live API call and surfaces a clearer error.

    Args:
        date_from: Start date (YYYY-MM-DD).
        date_to: End date (YYYY-MM-DD).
        today: Reference 'today' date — defaults to :meth:`date.today`.

    Returns:
        True when the range is fully in the past and cacheable.
    """
    today = today or date_cls.today()
    try:
        d_from = date_cls.fromisoformat(date_from)
        d_to = date_cls.fromisoformat(date_to)
    except ValueError:
        return False
    return d_from < today and d_to < today


def token_fingerprint(token: str) -> str:
    """Return a stable, non-reversible prefix of the token for cache keys.

    Args:
        token: Bearer token (not stored in the cache).

    Returns:
        First ``_FINGERPRINT_LEN`` hex chars of the SHA-256 digest.
    """
    digest = hashlib.sha256(token.encode('utf-8')).hexdigest()
    return digest[:_FINGERPRINT_LEN]


def make_cache_key(
        endpoint: str,
        token: str,
        params: dict[str, Any],
) -> str:
    """Build a canonical cache key from endpoint + token + params.

    Params are serialised with sorted keys so semantically equal calls
    hit the same row regardless of argument ordering or list order for
    non-semantic fields (list values are sorted when they hold primitives).

    Args:
        endpoint: Endpoint path or logical method identifier.
        token: Bearer token — only its fingerprint enters the key.
        params: Call parameters; must be JSON-serialisable.

    Returns:
        Canonical cache key string.
    """
    canonical = _canonicalise(params)
    payload = json.dumps(
        [endpoint, token_fingerprint(token), canonical],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _canonicalise(value: Any) -> Any:
    """Recursively normalise params for stable JSON serialisation."""
    if isinstance(value, dict):
        return {k: _canonicalise(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple, set)):
        items = [_canonicalise(v) for v in value]
        if all(isinstance(v, (str, int, float, bool)) for v in items):
            return sorted(items, key=_sort_key)
        return items
    return value


def _sort_key(value: Any) -> tuple[int, Any]:
    """Stable ordering across heterogeneous primitives."""
    if isinstance(value, bool):
        return (0, value)
    if isinstance(value, (int, float)):
        return (1, value)
    return (2, str(value))
