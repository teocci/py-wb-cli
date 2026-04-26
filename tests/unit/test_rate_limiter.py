"""Tests for wb.core.rate_limiter.RateLimiter and SharedRateLimiter."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from wb.core.rate_limiter import (
    RateLimiter,
    SellerCooldownLock,
    SharedRateLimiter,
    compute_seller_fingerprint,
    compute_token_fingerprint,
)
import wb.core.rate_limiter as rate_limiter_module


def _make_jwt(payload: dict) -> str:
    """Minimal JWT builder for tests: header.payload.sig (signature unverified)."""
    import base64
    import json

    def _b64(obj: dict) -> str:
        return base64.urlsafe_b64encode(
            json.dumps(obj, separators=(',', ':')).encode('utf-8')
        ).rstrip(b'=').decode('ascii')

    return f'{_b64({"alg": "HS256", "typ": "JWT"})}.{_b64(payload)}.sig'


class TestRateLimiterInit:
    """Validation of constructor arguments."""

    def test_valid_args_create_instance(self):
        limiter = RateLimiter(calls=3, period=60.0)
        assert limiter._calls == 3
        assert limiter._period == 60.0

    def test_zero_calls_raises(self):
        with pytest.raises(ValueError, match='calls must be >= 1'):
            RateLimiter(calls=0, period=60.0)

    def test_negative_calls_raises(self):
        with pytest.raises(ValueError, match='calls must be >= 1'):
            RateLimiter(calls=-1, period=60.0)

    def test_zero_period_raises(self):
        with pytest.raises(ValueError, match='period must be > 0'):
            RateLimiter(calls=3, period=0.0)

    def test_negative_period_raises(self):
        with pytest.raises(ValueError, match='period must be > 0'):
            RateLimiter(calls=3, period=-1.0)

    def test_minimum_valid_args(self):
        limiter = RateLimiter(calls=1, period=0.001)
        assert limiter._calls == 1


class TestRateLimiterAcquire:
    """Behaviour of acquire() under various conditions."""

    def test_calls_under_limit_do_not_sleep(self):
        """N calls within the limit should not block."""
        limiter = RateLimiter(calls=5, period=60.0)
        with patch('wb.core.rate_limiter.time.sleep') as mock_sleep:
            for _ in range(5):
                limiter.acquire()
            mock_sleep.assert_not_called()

    def test_single_call_does_not_sleep(self):
        limiter = RateLimiter(calls=1, period=60.0)
        with patch('wb.core.rate_limiter.time.sleep') as mock_sleep:
            limiter.acquire()
            mock_sleep.assert_not_called()

    def test_acquire_records_timestamp(self):
        limiter = RateLimiter(calls=3, period=60.0)
        limiter.acquire()
        assert len(limiter._timestamps) == 1

    def test_multiple_acquires_record_all_timestamps(self):
        limiter = RateLimiter(calls=5, period=60.0)
        for _ in range(5):
            limiter.acquire()
        assert len(limiter._timestamps) == 5

    def test_over_limit_sleeps(self):
        """The (N+1)th call must sleep until the oldest slot expires."""
        limiter = RateLimiter(calls=2, period=60.0)

        # Pre-fill the window manually so no real sleep occurs
        fake_now = 1000.0
        limiter._timestamps.append(fake_now - 10)  # 10 s ago, still in window
        limiter._timestamps.append(fake_now - 5)   # 5 s ago, still in window

        with patch('wb.core.rate_limiter.time.monotonic', return_value=fake_now):
            with patch('wb.core.rate_limiter.time.sleep') as mock_sleep:
                limiter.acquire()
                # oldest is 10 s ago, period=60 → sleep ≈ 50 s
                assert mock_sleep.called
                sleep_arg = mock_sleep.call_args[0][0]
                assert sleep_arg == pytest.approx(50.0, abs=0.1)

    def test_expired_timestamps_evicted_before_sleep_check(self):
        """Timestamps older than period are evicted; no sleep if window clears."""
        limiter = RateLimiter(calls=2, period=10.0)

        # Both timestamps are 15 s old — expired for period=10
        fake_now = 1000.0
        limiter._timestamps.append(fake_now - 15)
        limiter._timestamps.append(fake_now - 15)

        with patch('wb.core.rate_limiter.time.monotonic', return_value=fake_now):
            with patch('wb.core.rate_limiter.time.sleep') as mock_sleep:
                limiter.acquire()
                mock_sleep.assert_not_called()

    def test_acquire_after_window_clears_no_sleep(self):
        """After waiting for the period, calls should succeed without sleeping."""
        limiter = RateLimiter(calls=1, period=0.05)
        limiter.acquire()
        time.sleep(0.06)  # wait for window to expire
        with patch('wb.core.rate_limiter.time.sleep') as mock_sleep:
            limiter.acquire()
            mock_sleep.assert_not_called()

    def test_timestamps_deque_bounded_after_eviction(self):
        """After eviction, the deque should only hold in-window timestamps."""
        limiter = RateLimiter(calls=3, period=10.0)
        fake_now = 1000.0

        # Add 2 expired + 1 fresh
        limiter._timestamps.append(fake_now - 20)
        limiter._timestamps.append(fake_now - 15)
        limiter._timestamps.append(fake_now - 3)

        with patch('wb.core.rate_limiter.time.monotonic', return_value=fake_now):
            with patch('wb.core.rate_limiter.time.sleep'):
                limiter.acquire()

        # After eviction: the 2 expired are gone, 1 in-window + 1 new = 2
        assert len(limiter._timestamps) == 2


class TestRateLimiterThreadSafety:
    """Basic thread-safety smoke test."""

    def test_concurrent_acquires_do_not_exceed_limit(self):
        """Call count recorded must not exceed limit * 2 after 2 threads each acquire N times."""
        import threading

        limiter = RateLimiter(calls=100, period=1.0)
        results = []

        def worker():
            for _ in range(50):
                limiter.acquire()
                results.append(1)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 100


# ── Shared / SQLite-backed rate limiter ────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_fallback_warning_flag():
    """Ensure each test sees a fresh process-warning flag."""
    rate_limiter_module._FALLBACK_WARNED = False
    yield
    rate_limiter_module._FALLBACK_WARNED = False


def _make_shared(
        db_path: Path,
        *,
        calls: int,
        period: float,
        endpoint: str = '/adv/v3/fullstats',
        fingerprint: str = 'abcdef0123456789',
) -> SharedRateLimiter:
    return SharedRateLimiter(
        calls, period,
        token_fingerprint=fingerprint,
        endpoint=endpoint,
        db_path=db_path,
    )


class TestComputeTokenFingerprint:
    """Fingerprint helper round-trip and determinism."""

    def test_returns_16_hex_chars(self):
        fp = compute_token_fingerprint('abc')
        assert len(fp) == 16
        assert all(c in '0123456789abcdef' for c in fp)

    def test_deterministic(self):
        assert compute_token_fingerprint('x') == compute_token_fingerprint('x')

    def test_distinct_tokens_differ(self):
        assert compute_token_fingerprint('a') != compute_token_fingerprint('b')


class TestComputeSellerFingerprint:
    """Seller-scope fingerprint extracted from JWT ``sid`` claim."""

    def test_returns_16_hex_chars(self):
        token = _make_jwt({'sid': '173f8646-dc21-58c0-892e-ba069dc0a9cb'})
        fp = compute_seller_fingerprint(token)
        assert len(fp) == 16
        assert all(c in '0123456789abcdef' for c in fp)

    def test_deterministic_for_same_sid(self):
        token_a = _make_jwt({'sid': 'seller-uuid-1', 'iid': 1})
        token_b = _make_jwt({'sid': 'seller-uuid-1', 'iid': 1})
        assert compute_seller_fingerprint(token_a) == compute_seller_fingerprint(token_b)

    def test_same_sid_different_tokens_share_fingerprint(self):
        """Two tokens of the same seller (different iid/exp) collide — the point of F-10."""
        token_a = _make_jwt({'sid': 'seller-uuid-1', 'iid': 111, 'exp': 1000})
        token_b = _make_jwt({'sid': 'seller-uuid-1', 'iid': 222, 'exp': 9000})
        assert compute_seller_fingerprint(token_a) == compute_seller_fingerprint(token_b)

    def test_distinct_sid_differ(self):
        token_a = _make_jwt({'sid': 'seller-uuid-1'})
        token_b = _make_jwt({'sid': 'seller-uuid-2'})
        assert compute_seller_fingerprint(token_a) != compute_seller_fingerprint(token_b)

    def test_seller_fingerprint_differs_from_token_fingerprint(self):
        """sid-keyed fingerprint must NOT collide with plain token fingerprint."""
        token = _make_jwt({'sid': 'abc'})
        assert compute_seller_fingerprint(token) != compute_token_fingerprint(token)

    def test_malformed_jwt_falls_back_to_token_fingerprint(self):
        """Non-JWT string → fallback to token fingerprint (degrade gracefully)."""
        not_a_jwt = 'just-some-opaque-token-string'
        assert (
            compute_seller_fingerprint(not_a_jwt)
            == compute_token_fingerprint(not_a_jwt)
        )

    def test_jwt_missing_sid_falls_back(self):
        """JWT without `sid` claim falls back to token fingerprint."""
        token = _make_jwt({'iid': 1, 'uid': 2})  # no sid
        assert compute_seller_fingerprint(token) == compute_token_fingerprint(token)

    def test_jwt_sid_non_string_falls_back(self):
        """JWT with non-string sid falls back."""
        token = _make_jwt({'sid': 123})
        assert compute_seller_fingerprint(token) == compute_token_fingerprint(token)

    def test_jwt_malformed_payload_falls_back(self):
        """JWT with unparseable middle segment falls back without raising."""
        token = 'header.!!notbase64!!.sig'
        assert compute_seller_fingerprint(token) == compute_token_fingerprint(token)


class TestSharedRateLimiterInit:
    """Construction, validation, schema creation."""

    def test_invalid_calls_raises(self, tmp_path):
        with pytest.raises(ValueError, match='calls must be >= 1'):
            _make_shared(tmp_path / 'rl.db', calls=0, period=1.0)

    def test_invalid_period_raises(self, tmp_path):
        with pytest.raises(ValueError, match='period must be > 0'):
            _make_shared(tmp_path / 'rl.db', calls=1, period=0.0)

    def test_creates_db_and_table(self, tmp_path):
        db = tmp_path / 'rl.db'
        _make_shared(db, calls=1, period=1.0)
        assert db.exists()
        with sqlite3.connect(str(db)) as conn:
            tables = [
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
        assert 'rate_limit_log' in tables

    def test_creates_parent_directory(self, tmp_path):
        db = tmp_path / 'nested' / 'deeper' / 'rl.db'
        _make_shared(db, calls=1, period=1.0)
        assert db.exists()


class TestSharedRateLimiterAcquire:
    """Behaviour of acquire() on a fresh / populated DB."""

    def test_under_limit_does_not_sleep(self, tmp_path):
        lim = _make_shared(tmp_path / 'rl.db', calls=5, period=60.0)
        with patch('wb.core.rate_limiter.time.sleep') as mock_sleep:
            for _ in range(5):
                lim.acquire()
        mock_sleep.assert_not_called()

    def test_records_row_per_acquire(self, tmp_path):
        db = tmp_path / 'rl.db'
        lim = _make_shared(db, calls=10, period=60.0)
        for _ in range(3):
            lim.acquire()
        with sqlite3.connect(str(db)) as conn:
            count = conn.execute(
                'SELECT COUNT(*) FROM rate_limit_log'
            ).fetchone()[0]
        assert count == 3

    def test_prunes_stale_rows_on_acquire(self, tmp_path):
        db = tmp_path / 'rl.db'
        lim = _make_shared(db, calls=5, period=1.0)
        old_ts = time.time() - 3600.0  # 1h ago, well outside period=1
        with sqlite3.connect(str(db)) as conn:
            for _ in range(100):
                conn.execute(
                    'INSERT INTO rate_limit_log (token, endpoint, ts) '
                    'VALUES (?, ?, ?)',
                    (lim._token_fingerprint, lim._endpoint, old_ts),
                )
            conn.commit()
        lim.acquire()
        with sqlite3.connect(str(db)) as conn:
            count = conn.execute(
                'SELECT COUNT(*) FROM rate_limit_log'
            ).fetchone()[0]
        # All 100 stale rows pruned; only the fresh insert remains
        assert count == 1

    def test_over_limit_sleeps(self, tmp_path):
        """When the window is full, acquire should sleep until oldest expires."""
        db = tmp_path / 'rl.db'
        lim = _make_shared(db, calls=1, period=60.0)
        now = time.time()
        with sqlite3.connect(str(db)) as conn:
            conn.execute(
                'INSERT INTO rate_limit_log (token, endpoint, ts) '
                'VALUES (?, ?, ?)',
                (lim._token_fingerprint, lim._endpoint, now - 10.0),
            )
            conn.commit()
        sleeps: list[float] = []

        def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)
            # advance the DB state so the retry finds the window clear
            with sqlite3.connect(str(db)) as c:
                c.execute(
                    'DELETE FROM rate_limit_log WHERE token = ?',
                    (lim._token_fingerprint,),
                )
                c.commit()

        with patch('wb.core.rate_limiter.time.sleep', side_effect=fake_sleep):
            lim.acquire()

        assert len(sleeps) == 1
        # oldest is 10s ago, period 60 → sleep ~= 50
        assert 45.0 <= sleeps[0] <= 55.0

    def test_isolated_by_endpoint(self, tmp_path):
        """Two endpoints share the DB but not the budget."""
        db = tmp_path / 'rl.db'
        a = _make_shared(db, calls=1, period=60.0, endpoint='/a')
        b = _make_shared(db, calls=1, period=60.0, endpoint='/b')
        with patch('wb.core.rate_limiter.time.sleep') as mock_sleep:
            a.acquire()
            b.acquire()
        mock_sleep.assert_not_called()

    def test_isolated_by_token(self, tmp_path):
        """Two tokens share the DB but not the budget."""
        db = tmp_path / 'rl.db'
        t1 = _make_shared(db, calls=1, period=60.0, fingerprint='0' * 16)
        t2 = _make_shared(db, calls=1, period=60.0, fingerprint='1' * 16)
        with patch('wb.core.rate_limiter.time.sleep') as mock_sleep:
            t1.acquire()
            t2.acquire()
        mock_sleep.assert_not_called()


class TestSharedRateLimiterCrossProcess:
    """Cross-process serialisation via threads (threads share the SQLite file)."""

    def test_two_threads_serialise(self, tmp_path):
        """Two acquires on (1, period) can't both complete within `period`."""
        db = tmp_path / 'rl.db'
        period = 0.3
        lim_a = _make_shared(db, calls=1, period=period)
        lim_b = _make_shared(db, calls=1, period=period)

        start_barrier = threading.Barrier(2)
        finish_times: list[float] = []
        lock = threading.Lock()

        def worker(lim: SharedRateLimiter) -> None:
            start_barrier.wait()
            lim.acquire()
            with lock:
                finish_times.append(time.monotonic())

        t_start = time.monotonic()
        threads = [
            threading.Thread(target=worker, args=(lim_a,)),
            threading.Thread(target=worker, args=(lim_b,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(finish_times) == 2
        spread = max(finish_times) - min(finish_times)
        total = max(finish_times) - t_start
        # Second acquire must wait ~period for first row to age out
        assert spread >= period * 0.9
        assert total >= period * 0.9


class TestSharedRateLimiterFallback:
    """Graceful degradation when the DB is unusable."""

    # Note: the old `_build_limiters` and `_build_seller_limiter` helpers
    # were removed in R-2 (replaced by the single `EndpointBudget` factory
    # method `ServiceContainer.endpoint_budget()`). The env-var opt-out
    # behaviour for `WB_RATE_LIMITER=memory` is covered in
    # `tests/unit/test_endpoint_budget.py` and via `TestEndpointBudgetFactory`
    # at the end of this file.

    def test_corrupt_db_triggers_fallback(self, tmp_path, caplog):
        """A corrupt DB file at acquire time switches to the in-memory limiter."""
        db = tmp_path / 'rl.db'
        lim = _make_shared(db, calls=1, period=60.0)
        # Corrupt the file after schema init but before acquire
        db.write_bytes(b'not a sqlite db at all')

        with caplog.at_level('WARNING', logger='wb.core.rate_limiter'):
            lim.acquire()

        assert lim._fallback is not None
        assert isinstance(lim._fallback, RateLimiter)
        assert any('Shared rate limiter DB unavailable' in r.message
                   for r in caplog.records)

    def test_corrupt_db_at_init_triggers_fallback(self, tmp_path):
        """Pre-existing corrupt DB file falls back in the constructor."""
        db = tmp_path / 'rl.db'
        db.write_bytes(b'garbage')
        lim = _make_shared(db, calls=1, period=60.0)
        assert lim._fallback is not None
        # subsequent acquires go through the fallback cleanly
        lim.acquire()

    def test_fallback_warning_emitted_once_per_process(self, tmp_path, caplog):
        """Module-level flag ensures a single log per process."""
        db1 = tmp_path / 'a.db'
        db2 = tmp_path / 'b.db'
        db1.write_bytes(b'garbage')
        db2.write_bytes(b'garbage')
        with caplog.at_level('WARNING', logger='wb.core.rate_limiter'):
            lim1 = _make_shared(db1, calls=1, period=60.0)
            lim2 = _make_shared(db2, calls=1, period=60.0)
            lim1.acquire()
            lim2.acquire()
        warnings = [r for r in caplog.records
                    if 'Shared rate limiter DB unavailable' in r.message]
        assert len(warnings) == 1


class TestSellerCooldownLock:
    """F-13: TTL-based lock persisting WB-reported seller cooldowns."""

    def _reset_fallback_flag(self):
        rate_limiter_module._FALLBACK_WARNED = False

    def test_read_empty_returns_none(self, tmp_path):
        lock = SellerCooldownLock(db_path=tmp_path / 'rl.db')
        assert lock.read_remaining('seller-x') is None

    def test_record_then_read(self, tmp_path):
        lock = SellerCooldownLock(db_path=tmp_path / 'rl.db')
        lock.record('seller-x', cooldown_seconds=30.0)
        remaining = lock.read_remaining('seller-x')
        assert remaining is not None
        # Allow small slippage for test execution
        assert 29.0 < remaining <= 30.0

    def test_expired_row_reads_none(self, tmp_path, monkeypatch):
        lock = SellerCooldownLock(db_path=tmp_path / 'rl.db')
        import wb.core.rate_limiter as mod
        now = mod.time.time()
        # Fabricate an already-expired row via direct DB write
        import sqlite3
        conn = sqlite3.connect(str(tmp_path / 'rl.db'))
        conn.execute(
            'INSERT OR REPLACE INTO seller_cooldown VALUES (?, ?)',
            ('seller-x', now - 10.0),
        )
        conn.commit()
        conn.close()
        assert lock.read_remaining('seller-x') is None

    def test_record_upserts(self, tmp_path):
        lock = SellerCooldownLock(db_path=tmp_path / 'rl.db')
        lock.record('seller-x', cooldown_seconds=60.0)
        lock.record('seller-x', cooldown_seconds=5.0)  # shorter override
        remaining = lock.read_remaining('seller-x')
        assert remaining is not None and remaining <= 5.0

    def test_per_seller_isolation(self, tmp_path):
        lock = SellerCooldownLock(db_path=tmp_path / 'rl.db')
        lock.record('seller-a', cooldown_seconds=30.0)
        assert lock.read_remaining('seller-b') is None

    def test_record_zero_or_negative_ignored(self, tmp_path):
        lock = SellerCooldownLock(db_path=tmp_path / 'rl.db')
        lock.record('seller-x', cooldown_seconds=0)
        lock.record('seller-x', cooldown_seconds=-5)
        assert lock.read_remaining('seller-x') is None

    def test_corrupt_db_falls_back_at_init(self, tmp_path, caplog):
        """Corrupt DB file → in-memory fallback dict at construction time."""
        self._reset_fallback_flag()
        db = tmp_path / 'rl.db'
        db.write_bytes(b'not a sqlite db')
        with caplog.at_level('WARNING', logger='wb.core.rate_limiter'):
            lock = SellerCooldownLock(db_path=db)
        assert lock._fallback is not None
        # Record/read still works through the fallback
        lock.record('seller-x', cooldown_seconds=15.0)
        assert lock.read_remaining('seller-x') is not None

    def test_cross_process_coordination(self, tmp_path):
        """Two locks sharing the DB file see each other's records."""
        db = tmp_path / 'rl.db'
        writer = SellerCooldownLock(db_path=db)
        reader = SellerCooldownLock(db_path=db)
        writer.record('seller-x', cooldown_seconds=45.0)
        assert reader.read_remaining('seller-x') is not None


class TestEndpointBudgetFactory:
    """R-2: `ServiceContainer.endpoint_budget()` replaces the F-10/F-13 builders.

    `_build_limiters`, `_build_seller_limiter`, and `_build_cooldown_lock`
    were removed in R-2; their job is now done by a single
    :class:`wb.core.endpoint_budget.EndpointBudget` instance accessible
    via :meth:`wb.services._factory._Container.endpoint_budget`.
    """

    def test_default_returns_db_backed_budget(self, monkeypatch, tmp_path):
        from pathlib import Path as _Path
        from wb.core.constants import RATE_LIMITER_ENV_VAR
        from wb.core.endpoint_budget import EndpointBudget
        from wb.services._factory import ServiceContainer

        monkeypatch.delenv(RATE_LIMITER_ENV_VAR, raising=False)
        monkeypatch.setattr(_Path, 'home', lambda: tmp_path)
        ServiceContainer.reset()
        try:
            budget = ServiceContainer.endpoint_budget()
            assert isinstance(budget, EndpointBudget)
            # DB-backed mode → no in-memory fallback active.
            assert budget._fallback is None
        finally:
            ServiceContainer.reset()

    def test_env_opt_out_uses_in_memory_fallback(self, monkeypatch, tmp_path):
        from pathlib import Path as _Path
        from wb.core.constants import RATE_LIMITER_ENV_VAR
        from wb.core.endpoint_budget import EndpointBudget
        from wb.services._factory import ServiceContainer

        monkeypatch.setenv(RATE_LIMITER_ENV_VAR, 'memory')
        monkeypatch.setattr(_Path, 'home', lambda: tmp_path)
        ServiceContainer.reset()
        try:
            budget = ServiceContainer.endpoint_budget()
            assert isinstance(budget, EndpointBudget)
            # Force-memory mode → fallback dict active from init.
            assert budget._fallback is not None
        finally:
            ServiceContainer.reset()

    def test_singleton_within_process(self, monkeypatch, tmp_path):
        from pathlib import Path as _Path
        from wb.services._factory import ServiceContainer

        monkeypatch.setattr(_Path, 'home', lambda: tmp_path)
        ServiceContainer.reset()
        try:
            a = ServiceContainer.endpoint_budget()
            b = ServiceContainer.endpoint_budget()
            assert a is b
        finally:
            ServiceContainer.reset()
