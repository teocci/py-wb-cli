# Fix F-13 — `SellerCooldownLock` short-circuit on known cooldown (v0.25.5)

**Date:** 2026-04-24
**Tests:** 1125/1126 (1 pre-existing env-isolation failure in `test_auth_list_empty`, unrelated)

## Problem

Even after F-12 makes a *single* `wb` call fail fast on a large `x-ratelimit-reset`, every *subsequent* `wb` invocation during the same cooldown window still makes an HTTP round-trip and gets 429'd. WB's leaky-bucket-with-penalty throttle then extends the window further — running `wb daily-report` three times during a 9-minute cooldown causes three additional penalty hits and can double the lockout.

## What Was Built

- **`SellerCooldownLock` class** in `src/wb/core/rate_limiter.py` — a TTL lock backed by a new `seller_cooldown` table in the existing `~/.wb-cli/rate_limits.db` (WAL mode, same file as `SharedRateLimiter`, separate table). Two methods:
  - `read_remaining(seller_fingerprint)` → positive seconds remaining, or `None` when no active lock (missing or expired).
  - `record(seller_fingerprint, cooldown_seconds)` → UPSERT a row with `expires_at = now + cooldown_seconds`. Overrides any existing row for the same seller, since the most recent WB response is authoritative.
- **Cross-process coordination.** The DB file is shared with F-10's `SharedRateLimiter`, so a lock written by one `wb` process is immediately visible to any other.
- **Transparent in-memory fallback** on `sqlite3.Error` at init, read, or record time — mirrors `SharedRateLimiter` with a single process-wide warning.
- **Factory wiring: `_build_cooldown_lock()`** in `src/wb/services/_factory.py`. Stateless (no per-token parameter), so a single builder suffices; seller fingerprint is supplied at read/record time.
- **HTTP client integration.** `WbHttpClient.__init__` accepts `cooldown_lock` + `seller_fingerprint`. Two new helpers:
  - `_check_cooldown_lock()` — called at the top of every `request` / `request_raw`, before any limiter acquire. Raises `RateLimitError(retry_after=remaining)` with no HTTP attempt when a lock is active.
  - `_record_cooldown(exc)` — called right after a 429 is caught; persists `exc.retry_after` (populated by F-12) to the lock before the retry decision.

## Files Changed

| File | Change |
|------|--------|
| `src/wb/core/rate_limiter.py` | Added `SellerCooldownLock` class (~135 LoC) with DB-backed and in-memory-fallback paths; added to `__all__` |
| `src/wb/services/_factory.py` | New `_build_cooldown_lock()` function; `ServiceContainer.http_client` constructs it and the seller fingerprint, passes both to `WbHttpClient` |
| `src/wb/client/http.py` | New `_check_cooldown_lock()` and `_record_cooldown()` methods; pre-flight check in both `request` and `request_raw` before limiter acquires; `__init__` accepts `cooldown_lock` + `seller_fingerprint`; `TYPE_CHECKING` import for the new class |
| `tests/unit/test_rate_limiter.py` | 9 new tests: 8 `TestSellerCooldownLock` (empty read, record+read, expired row, upsert-override, per-seller isolation, zero/negative ignore, corrupt-DB fallback, cross-process coordination) + 1 `TestCooldownLockFactory` (default returns a working `SellerCooldownLock`) |
| `tests/unit/test_http_client.py` | 5 new tests: active lock short-circuits without HTTP, cleared lock permits HTTP, 429-with-reset records to lock, 429-without-reset doesn't record, no-fingerprint skips the check |
| `docs/FIXES.md`, `docs/PROGRESS.md` | F-13 row flipped to ✅ DONE |

## Live Test Results

### Injected-lock smoke test (happy path)

Recorded a 30 s cooldown for the active seller directly via the `SellerCooldownLock` API, then immediately ran `wb --json --compact campaign list`:

```
Injected 30s cooldown for seller 589f628451e31cb7
read_remaining: 30.0s
=== Running wb campaign list (should short-circuit instantly) ===
2026-04-24 19:42:33 [WARNING] wb.client.http: Seller cooldown lock active — 29s remaining; skipping HTTP call
{"status": "error", "error": {"code": "RATE_LIMITED", "message": "Seller cooldown active — 29s remaining", "exit_code": 5, "retry_after": 29.41}}

real    0m0.611s
```

- **0.611 s total wall time** (was ~70 s without the lock).
- The log line confirms the pre-flight check fired before any HTTP attempt.
- JSON error carries the authoritative `retry_after` for agent scheduling.
- Fabricated lock cleared after the test; `wb campaign list` immediately succeeded afterwards.

### UPSERT semantics

`test_record_upserts` confirms a second `record(seller, 5.0)` after `record(seller, 60.0)` shrinks the lock — the latest WB response always wins, whether shorter or longer.

### Cross-process semantics

`test_cross_process_coordination` creates two independent `SellerCooldownLock` instances pointing at the same DB file. Writer records → reader sees the value. This is the core F-13 guarantee: a 429 in one `wb` process protects all subsequent `wb` processes until the deadline passes.

### Recovery after deadline

Since `expires_at` is a concrete timestamp, expired rows naturally read as `None` (`test_expired_row_reads_none`). No cleanup job is needed; the next `record` UPSERT overwrites stale data.

## Combined F-12 + F-13 behaviour

| Scenario | Pre-F-12 | After F-12 only | After F-12 + F-13 |
|---|---|---|---|
| Single call, 429 with reset=45 s | 4 retries (~13 s) | 1 retry at 45 s, then succeeds | Same as F-12 |
| Single call, 429 with reset=564 s | 4 retries (~13 s), still 429 | Immediate fail with `retry_after=564` | Same as F-12, plus lock persisted |
| Second `wb` call 10 s later | New full retry cycle, extends WB's penalty | New full retry cycle, extends penalty | **Instant `RATE_LIMITED` via lock, no HTTP** |
| 3× back-to-back `wb` calls in 3 min | 3× penalty compound → 9+ min lockout | Same (penalty still compounds across invocations) | 1st trips lock, calls 2 & 3 short-circuit — **no compounding** |
