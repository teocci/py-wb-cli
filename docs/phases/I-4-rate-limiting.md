# Phase I-4 — Rate Limiting & Resilience (v0.17.0)

**Date:** 2026-04-07 | **Tests:** 901 passed (+25)

## What Was Built

- `RATE_LIMITS.md`: CLI command → endpoint constant → path → limit → source
- `core/rate_limits.py`: `ENDPOINT_LIMITS` dict mapping 30 endpoint constants to `(calls, period_seconds)` tuples (sourced from swagger YAML files)
- `core/rate_limiter.py`: Thread-safe sliding-window `RateLimiter` (`collections.deque` + `threading.Lock`). `acquire()` evicts expired timestamps, sleeps until slot opens, records call
- `core/batching.py`: Added `paginate_all(fetch, page_size)` — offset-based pagination helper
- `client/http.py`: `path_limiters: dict[str, RateLimiter] | None` param; preemptive `acquire()` before retry loop
- `services/_factory.py`: `_Container` / `ServiceContainer` caching `Settings` + HTTP clients per `(base_url, token)` key; `_build_limiters()` injected into promotion + analytics clients

## Key Design Decisions

- Per-path limiters, not per-client: different endpoints have different limits
- Preemptive over reactive: `acquire()` runs before HTTP call; 429 retry remains as safety net
- Burst=1 → interval encoding: `(1, 20.0)` for fullstats enforces spacing
- `ServiceContainer.reset()` for test isolation
