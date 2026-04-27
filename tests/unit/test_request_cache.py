"""Tests for the I-15 SQLite request cache."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from wb.storage.request_cache import RequestCache


def _make_cache(tmp_path: Path) -> RequestCache:
    return RequestCache(db_path=tmp_path / 'req.db')


class TestGetPut:
    def test_get_miss_when_empty(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        result = cache.get('tok', '/ep', 'h', max_age_seconds=3600)
        assert result is None

    def test_put_then_get_returns_payload(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        cache.put('tok', '/ep', 'h', b'hello', ttl_seconds=10)
        result = cache.get('tok', '/ep', 'h', max_age_seconds=3600)
        assert result == b'hello'

    def test_get_returns_none_when_token_differs(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        cache.put('tokA', '/ep', 'h', b'A', ttl_seconds=10)
        assert cache.get('tokB', '/ep', 'h', max_age_seconds=3600) is None

    def test_get_returns_none_when_endpoint_differs(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        cache.put('tok', '/a', 'h', b'A', ttl_seconds=10)
        assert cache.get('tok', '/b', 'h', max_age_seconds=3600) is None

    def test_get_returns_none_when_params_differ(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        cache.put('tok', '/ep', 'hA', b'A', ttl_seconds=10)
        assert cache.get('tok', '/ep', 'hB', max_age_seconds=3600) is None

    def test_put_replaces_existing_row(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        cache.put('tok', '/ep', 'h', b'first', ttl_seconds=10)
        cache.put('tok', '/ep', 'h', b'second', ttl_seconds=10)
        assert cache.get('tok', '/ep', 'h', max_age_seconds=3600) == b'second'

    def test_put_with_zero_ttl_is_noop(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        cache.put('tok', '/ep', 'h', b'x', ttl_seconds=0)
        assert cache.get('tok', '/ep', 'h', max_age_seconds=3600) is None

    def test_put_with_negative_ttl_is_noop(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        cache.put('tok', '/ep', 'h', b'x', ttl_seconds=-1)
        assert cache.get('tok', '/ep', 'h', max_age_seconds=3600) is None


class TestExpiry:
    def test_expired_row_returns_none(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        cache.put('tok', '/ep', 'h', b'x', ttl_seconds=0.001)
        time.sleep(0.05)
        assert cache.get('tok', '/ep', 'h', max_age_seconds=3600) is None

    def test_max_age_bounds_freshness(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        cache.put('tok', '/ep', 'h', b'x', ttl_seconds=3600)
        # Row is fresh per its own TTL but caller demands age <= 0 s.
        time.sleep(0.05)
        assert cache.get('tok', '/ep', 'h', max_age_seconds=0.0) is None

    def test_inf_max_age_disables_caller_bound(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        cache.put('tok', '/ep', 'h', b'x', ttl_seconds=3600)
        time.sleep(0.05)
        assert cache.get(
            'tok', '/ep', 'h', max_age_seconds=float('inf'),
        ) == b'x'

    def test_get_prunes_other_expired_rows(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        # Row A: long TTL, the one we'll fetch.
        cache.put('tok', '/ep', 'A', b'a', ttl_seconds=3600)
        # Rows B/C: short TTL, will expire.
        cache.put('tok', '/ep', 'B', b'b', ttl_seconds=0.001)
        cache.put('tok', '/ep', 'C', b'c', ttl_seconds=0.001)
        # Row D: same token, different endpoint — should NOT be pruned.
        cache.put('tok', '/other', 'D', b'd', ttl_seconds=0.001)
        time.sleep(0.05)
        cache.get('tok', '/ep', 'A', max_age_seconds=3600)
        rows = cache.read_all()
        endpoints = {(r.endpoint, r.params_hash) for r in rows}
        # A still present; B/C pruned (same (token, endpoint));
        # D NOT pruned (different endpoint, prune is scoped).
        assert ('/ep', 'A') in endpoints
        assert ('/ep', 'B') not in endpoints
        assert ('/ep', 'C') not in endpoints
        assert ('/other', 'D') in endpoints


class TestInvalidate:
    def test_invalidate_drops_token_endpoint_rows(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        cache.put('tok', '/ep', 'A', b'a', ttl_seconds=3600)
        cache.put('tok', '/ep', 'B', b'b', ttl_seconds=3600)
        cache.put('tok', '/other', 'C', b'c', ttl_seconds=3600)
        cache.put('other_tok', '/ep', 'D', b'd', ttl_seconds=3600)

        deleted = cache.invalidate('tok', '/ep')
        assert deleted == 2

        # /ep entries for tok are gone.
        assert cache.get('tok', '/ep', 'A', max_age_seconds=3600) is None
        assert cache.get('tok', '/ep', 'B', max_age_seconds=3600) is None
        # Other endpoint for same token survives.
        assert cache.get('tok', '/other', 'C', max_age_seconds=3600) == b'c'
        # Same endpoint for other token survives.
        assert cache.get('other_tok', '/ep', 'D', max_age_seconds=3600) == b'd'

    def test_invalidate_unknown_returns_zero(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        assert cache.invalidate('tok', '/none') == 0


class TestClear:
    def test_clear_all(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        for i in range(3):
            cache.put(f't{i}', '/ep', str(i), b'x', ttl_seconds=3600)
        assert cache.clear() == 3
        assert cache.read_all() == []

    def test_clear_by_token(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        cache.put('tok', '/a', '1', b'x', ttl_seconds=3600)
        cache.put('tok', '/b', '2', b'y', ttl_seconds=3600)
        cache.put('other', '/a', '3', b'z', ttl_seconds=3600)
        deleted = cache.clear(token_fp='tok')
        assert deleted == 2
        assert len(cache.read_all()) == 1

    def test_clear_by_endpoint(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        cache.put('a', '/x', '1', b'x', ttl_seconds=3600)
        cache.put('b', '/x', '2', b'y', ttl_seconds=3600)
        cache.put('c', '/y', '3', b'z', ttl_seconds=3600)
        deleted = cache.clear(endpoint='/x')
        assert deleted == 2

    def test_clear_by_token_and_endpoint(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        cache.put('tok', '/x', '1', b'x', ttl_seconds=3600)
        cache.put('tok', '/y', '2', b'y', ttl_seconds=3600)
        cache.put('other', '/x', '3', b'z', ttl_seconds=3600)
        deleted = cache.clear(token_fp='tok', endpoint='/x')
        assert deleted == 1


class TestReadAll:
    def test_empty_returns_empty_list(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        assert cache.read_all() == []

    def test_returns_all_rows_including_expired(self, tmp_path: Path) -> None:
        cache = _make_cache(tmp_path)
        cache.put('tok', '/a', '1', b'x', ttl_seconds=3600)
        cache.put('tok', '/b', '2', b'y', ttl_seconds=0.001)
        time.sleep(0.05)
        rows = cache.read_all()
        # Expired rows are still surfaced — caller decides display.
        assert len(rows) == 2


class TestCrossProcess:
    def test_second_connection_sees_committed_rows(self, tmp_path: Path) -> None:
        cache_a = _make_cache(tmp_path)
        cache_a.put('tok', '/ep', 'h', b'hello', ttl_seconds=3600)

        # Independent connection / cache instance — simulates a sibling
        # `wb` process opening the same DB file.
        cache_b = RequestCache(db_path=tmp_path / 'req.db')
        result = cache_b.get('tok', '/ep', 'h', max_age_seconds=3600)
        assert result == b'hello'

    def test_concurrent_put_replaces_atomically(self, tmp_path: Path) -> None:
        cache_a = _make_cache(tmp_path)
        cache_b = RequestCache(db_path=tmp_path / 'req.db')
        cache_a.put('tok', '/ep', 'h', b'first', ttl_seconds=3600)
        cache_b.put('tok', '/ep', 'h', b'second', ttl_seconds=3600)
        # Either cache instance now sees 'second'.
        assert cache_a.get('tok', '/ep', 'h', max_age_seconds=3600) == b'second'
        assert cache_b.get('tok', '/ep', 'h', max_age_seconds=3600) == b'second'

    def test_writes_use_wal(self, tmp_path: Path) -> None:
        # WAL mode means a -wal sidecar appears on first write.
        cache = _make_cache(tmp_path)
        cache.put('tok', '/ep', 'h', b'x', ttl_seconds=3600)
        assert (tmp_path / 'req.db').exists()
        # The WAL file may exist or have been checkpointed away — its
        # mere existence isn't guaranteed across all SQLite versions, but
        # journal_mode should report 'wal' when queried.
        with sqlite3.connect(str(tmp_path / 'req.db')) as conn:
            mode = conn.execute('PRAGMA journal_mode').fetchone()[0]
            assert mode.lower() == 'wal'


class TestForceMemory:
    def test_force_memory_skips_disk(self, tmp_path: Path) -> None:
        cache = RequestCache(db_path=tmp_path / 'never.db', force_memory=True)
        cache.put('tok', '/ep', 'h', b'x', ttl_seconds=3600)
        assert cache.get('tok', '/ep', 'h', max_age_seconds=3600) == b'x'
        # No DB file was ever written.
        assert not (tmp_path / 'never.db').exists()

    def test_memory_invalidate_works(self, tmp_path: Path) -> None:
        cache = RequestCache(db_path=tmp_path / 'never.db', force_memory=True)
        cache.put('tok', '/ep', 'h', b'x', ttl_seconds=3600)
        cache.put('tok', '/ep', 'h2', b'y', ttl_seconds=3600)
        assert cache.invalidate('tok', '/ep') == 2

    def test_memory_clear_works(self, tmp_path: Path) -> None:
        cache = RequestCache(db_path=tmp_path / 'never.db', force_memory=True)
        cache.put('a', '/x', '1', b'x', ttl_seconds=3600)
        cache.put('b', '/y', '2', b'y', ttl_seconds=3600)
        assert cache.clear() == 2


class TestMaxAgeOverride:
    def test_max_age_smaller_than_ttl_invalidates_cache(self, tmp_path: Path) -> None:
        # Scenario: a row was written with a 1-hour TTL, but the caller
        # is now using a tighter token-type prior whose interval is 1 s.
        # The row's expires_at is fine but the caller's policy says the
        # row is too old to trust.
        cache = _make_cache(tmp_path)
        cache.put('tok', '/ep', 'h', b'x', ttl_seconds=3600)
        time.sleep(0.05)
        result = cache.get('tok', '/ep', 'h', max_age_seconds=0.01)
        assert result is None
