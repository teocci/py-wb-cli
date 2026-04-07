"""Tests for wb.core.rate_limiter.RateLimiter."""

from __future__ import annotations

import time
from unittest.mock import call, patch

import pytest

from wb.core.rate_limiter import RateLimiter


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
