# Fix F-13 — `SellerCooldownLock` short-circuit on known cooldown (v0.25.5)

**Status:** 🔲 PLANNED
**Scope:** `src/wb/core/rate_limiter.py`, `src/wb/services/_factory.py`, `src/wb/client/http.py`

## Problem

Even with F-12 making *one* `wb` call fail fast on a large `x-ratelimit-reset`, every *subsequent* `wb` invocation during the same cooldown window still makes an HTTP round-trip, gets 429'd, and extends WB's leaky-bucket penalty further. A user running `wb daily-report` three times during a 9-minute cooldown causes three additional penalty hits, potentially doubling the lockout.

## Solution

**Layer B of the two-layer rate-limit integration.** Add a `SellerCooldownLock` class in `rate_limiter.py` backed by a new SQLite row family in the existing `~/.wb-cli/rate_limits.db` (separate table, same DB file for atomicity with the rest of the rate-limit state). The lock stores `(seller_fingerprint, cooldown_until_ts)` — a pure TTL, no cleanup job needed because rows expire implicitly.

Wire the lock into `WbHttpClient.__init__` alongside `seller_limiter`. At the top of `request` / `request_raw`, consult the lock: if `cooldown_until_ts > now`, raise `RateLimitError` immediately with `retry_after = cooldown_until_ts - now` and skip every HTTP attempt.

When a 429 response carries `x-ratelimit-reset: N`, write `cooldown_until_ts = now + N` to the lock (F-12 reads the header; F-13 persists the deadline).

## Steps

- [ ] Add `SellerCooldownLock` class in `src/wb/core/rate_limiter.py` — schema creation, `read_remaining(fingerprint) -> float | None`, `record(fingerprint, cooldown_seconds)`. Fallback to in-memory dict when `WB_RATE_LIMITER=memory` or DB unavailable, mirroring `SharedRateLimiter`.
- [ ] Extend `_build_seller_limiter` in `_factory.py` to also return (or co-build) the lock; `ServiceContainer.http_client` passes both to `WbHttpClient`.
- [ ] `WbHttpClient.__init__` accepts optional `cooldown_lock`; pre-flight check in `request` / `request_raw` before `seller_limiter.acquire()`.
- [ ] On 429 with a populated `retry_after` (from F-12), call `cooldown_lock.record(fingerprint, retry_after)` before raising.
- [ ] Unit tests: lock short-circuits before any HTTP call; lock writes on 429; lock auto-expires past `cooldown_until_ts`; cross-process (two in-memory conns hitting the same DB) coordination; memory fallback.
- [ ] Live test: inject a mocked 429 (respx) with `x-ratelimit-reset: 30` → first call raises after HTTP; second call within 30 s raises instantly with `retry_after` remaining; after 30 s, third call proceeds normally.
