"""Tests for wb.storage.response_cache."""

from __future__ import annotations

import sqlite3
import time
from datetime import date, timedelta

import pytest

from wb.storage.response_cache import (
    ResponseCache,
    is_past_day_range,
    make_cache_key,
    token_fingerprint,
)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def cache(tmp_path):
    """ResponseCache rooted at a tmp DB with a generous retention window."""
    return ResponseCache(
        db_path=tmp_path / 'cache.db',
        retention_days=90,
    )


# ── is_past_day_range ─────────────────────────────────────────────────

class TestIsPastDayRange:
    """Date-range gate that decides whether a query is cacheable."""

    def test_range_strictly_in_past_is_cacheable(self):
        today = date(2026, 4, 24)
        assert is_past_day_range('2026-04-22', '2026-04-23', today) is True

    def test_to_date_equal_today_is_not_cacheable(self):
        today = date(2026, 4, 24)
        assert is_past_day_range('2026-04-23', '2026-04-24', today) is False

    def test_to_date_in_future_is_not_cacheable(self):
        today = date(2026, 4, 24)
        assert is_past_day_range('2026-04-24', '2026-04-25', today) is False

    def test_from_date_equal_today_is_not_cacheable(self):
        today = date(2026, 4, 24)
        assert is_past_day_range('2026-04-24', '2026-04-30', today) is False

    def test_from_after_to_still_evaluates_on_endpoints(self):
        today = date(2026, 4, 24)
        # Both strictly before today — returns True even if invalid order.
        assert is_past_day_range('2026-04-23', '2026-04-22', today) is True

    def test_invalid_date_returns_false(self):
        today = date(2026, 4, 24)
        assert is_past_day_range('not-a-date', '2026-04-22', today) is False
        assert is_past_day_range('2026-04-22', 'nope', today) is False

    def test_today_defaults_to_date_today(self):
        result = is_past_day_range('1900-01-01', '1900-01-02')
        assert result is True


# ── token_fingerprint & make_cache_key ─────────────────────────────────

class TestCacheKey:
    """Cache-key derivation — stability and semantic properties."""

    def test_token_fingerprint_is_deterministic(self):
        a = token_fingerprint('my-secret-token')
        b = token_fingerprint('my-secret-token')
        assert a == b
        assert len(a) == 16

    def test_token_fingerprint_differs_for_different_tokens(self):
        assert token_fingerprint('tok-a') != token_fingerprint('tok-b')

    def test_token_not_in_cache_key(self):
        key = make_cache_key('ep', 'supersecret-jwt-xyz', {'a': 1})
        assert 'supersecret' not in key
        assert 'jwt' not in key

    def test_param_order_does_not_change_key(self):
        k1 = make_cache_key('ep', 'tok', {'a': 1, 'b': 2})
        k2 = make_cache_key('ep', 'tok', {'b': 2, 'a': 1})
        assert k1 == k2

    def test_list_order_does_not_change_key_for_primitives(self):
        k1 = make_cache_key('ep', 'tok', {'nm_ids': [1, 2, 3]})
        k2 = make_cache_key('ep', 'tok', {'nm_ids': [3, 1, 2]})
        assert k1 == k2

    def test_different_tokens_produce_different_keys(self):
        k1 = make_cache_key('ep', 'tok-a', {'a': 1})
        k2 = make_cache_key('ep', 'tok-b', {'a': 1})
        assert k1 != k2

    def test_different_endpoints_produce_different_keys(self):
        k1 = make_cache_key('endpoint-a', 'tok', {'a': 1})
        k2 = make_cache_key('endpoint-b', 'tok', {'a': 1})
        assert k1 != k2


# ── ResponseCache.get / put ───────────────────────────────────────────

class TestResponseCacheGetPut:
    """get/put round-trips and basic behaviours."""

    def test_get_missing_returns_none(self, cache):
        assert cache.get('no-such-key') is None

    def test_round_trip_dict(self, cache):
        cache.put('k1', {'hello': 'world', 'n': 42})
        assert cache.get('k1') == {'hello': 'world', 'n': 42}

    def test_round_trip_list(self, cache):
        cache.put('k1', [{'nm_id': 1}, {'nm_id': 2}])
        assert cache.get('k1') == [{'nm_id': 1}, {'nm_id': 2}]

    def test_put_replaces_existing(self, cache):
        cache.put('k1', {'v': 1})
        cache.put('k1', {'v': 2})
        assert cache.get('k1') == {'v': 2}

    def test_non_json_value_logs_and_skips(self, cache, caplog):
        cache.put('k1', {'obj': object()})
        assert cache.get('k1') is None
        assert any('encode' in r.message for r in caplog.records)


# ── ResponseCache.prune ───────────────────────────────────────────────

class TestResponseCachePrune:
    """Retention-based pruning."""

    def test_prune_removes_old_rows(self, tmp_path):
        cache = ResponseCache(tmp_path / 'cache.db', retention_days=1)
        cache.put('k-old', {'v': 1})

        # Manually age the row to beyond retention (1 day).
        aged = time.time() - (2 * 86400)
        with sqlite3.connect(str(tmp_path / 'cache.db')) as conn:
            conn.execute(
                'UPDATE response_cache SET created_at = ? WHERE key = ?',
                (aged, 'k-old'),
            )

        cache.put('k-fresh', {'v': 2})

        removed = cache.prune()
        assert removed == 1
        assert cache.get('k-old') is None
        assert cache.get('k-fresh') == {'v': 2}

    def test_prune_returns_zero_when_nothing_old(self, cache):
        cache.put('k1', {'v': 1})
        cache.put('k2', {'v': 2})
        assert cache.prune() == 0


# ── Persistence & cross-process safety ────────────────────────────────

class TestResponseCachePersistence:
    """Two ResponseCache instances on the same file share data."""

    def test_second_instance_sees_writes_from_first(self, tmp_path):
        db = tmp_path / 'cache.db'
        ResponseCache(db, retention_days=90).put('k1', {'v': 1})
        other = ResponseCache(db, retention_days=90)
        assert other.get('k1') == {'v': 1}

    def test_wal_mode_enabled(self, tmp_path):
        db = tmp_path / 'cache.db'
        ResponseCache(db, retention_days=90).put('k', {'v': 1})
        # WAL creates a `-wal` sidecar file after the first write.
        assert db.with_suffix('.db-wal').exists()

    def test_sqlite_error_on_read_returns_none(self, cache, monkeypatch, caplog):
        """Unexpected SQLite failure during read returns None, not an exception."""
        def boom(*args, **kwargs):
            raise sqlite3.OperationalError('database is locked')

        monkeypatch.setattr(cache, '_connect', boom)
        assert cache.get('k') is None
        assert any('read failed' in r.message for r in caplog.records)

    def test_sqlite_error_on_write_is_swallowed(self, cache, monkeypatch, caplog):
        """Unexpected SQLite failure during write logs but does not raise."""
        def boom(*args, **kwargs):
            raise sqlite3.OperationalError('disk I/O error')

        monkeypatch.setattr(cache, '_connect', boom)
        cache.put('k', {'v': 1})  # must not raise
        assert any('write failed' in r.message for r in caplog.records)
