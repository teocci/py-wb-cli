"""Sliding-window rate limiter for WB API calls.

Provides :class:`RateLimiter`, a thread-safe preemptive throttle that keeps
call counts within documented API limits. Designed for injection into
:class:`wb.client.http.WbHttpClient` via the ``path_limiters`` parameter.

Usage::

    from wb.core.rate_limiter import RateLimiter
    limiter = RateLimiter(calls=3, period=60.0)
    limiter.acquire()   # blocks until a slot is available, then records the call
"""

from __future__ import annotations

import threading
import time
from collections import deque

__all__ = ['RateLimiter']


class RateLimiter:
    """Thread-safe sliding-window rate limiter.

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
