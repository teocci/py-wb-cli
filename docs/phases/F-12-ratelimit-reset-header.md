# Fix F-12 — Honor `x-ratelimit-reset` header on 429 (v0.25.4)

**Date:** 2026-04-24
**Tests:** 1111/1112 (1 pre-existing env-isolation failure in `test_auth_list_empty`, unrelated)

## Problem

WB's gateway sends three undocumented headers on 429 responses (absent from the swagger 429 schema at [docs/swagger/01-general.yaml:1243-1283](../swagger/01-general.yaml#L1243)):

```
x-ratelimit-reset: 564        ← seconds until cooldown clears
x-ratelimit-retry: 564        ← same value (alternative name)
x-ratelimit-limit:   1        ← limit that was hit
```

The HTTP client previously read only the standard `Retry-After` (which WB never sends), so F-9's 5/15/45 s schedule was used even when WB authoritatively reported 564 s of remaining cooldown. Worse, each doomed retry hitting WB during an active window **extended** the penalty (leaky-bucket-with-penalty pattern), turning a recoverable 60-second throttle into a 9-minute one over a test session.

## What Was Built

- **`_parse_rate_limit_reset(response)`.** New helper in `src/wb/client/http.py` that reads the first positive numeric value from `Retry-After` → `x-ratelimit-reset` → `x-ratelimit-retry`, in that order. Standard `Retry-After` still wins when present; WB's undocumented headers fill in when it isn't. Returns `None` when no usable value is available.
- **`_RETRY_AFTER_BAIL_OUT_SECONDS = 60.0` threshold.** New constant. Any `retry_after` larger than this signals a seller-scope penalty rather than a per-endpoint window; retrying would only extend the cooldown.
- **Bail-out in `_retry_or_raise`.** When a `RateLimitError`'s `retry_after` exceeds the 60 s threshold, skip every remaining retry and re-raise immediately. A warning log line makes the bail-out explicit: `cooldown too large to retry (reset=564s > 60s), bailing out with retry_after=564`. Small resets (≤ 60 s) still get the normal retry treatment — genuine per-endpoint windows like fullstats 20 s or funnel 60 s recover cleanly on the next attempt.
- **Existing plumbing reused.** `RateLimitError.to_dict` already serializes `retry_after` into CLI JSON error output; now it's populated with WB's authoritative value rather than the missing `Retry-After`. No serializer changes needed.

## Files Changed

| File | Change |
|------|--------|
| `src/wb/client/http.py` | Added `_RATELIMIT_RESET_HEADERS`, `_RETRY_AFTER_BAIL_OUT_SECONDS`, `_parse_rate_limit_reset()`; `_check_error_status` now uses the helper; `_retry_or_raise` bails out on large resets; docstring updated |
| `tests/unit/test_http_client.py` | 5 new tests: `test_x_ratelimit_reset_populates_retry_after`, `test_x_ratelimit_retry_populates_retry_after`, `test_retry_after_standard_header_still_preferred`, `test_large_retry_after_bails_out_without_retry`, `test_small_retry_after_still_retries`; 1 updated test (`test_retry_after_header_overrides_patient_schedule` — value 120 → 45 to stay under the new threshold) |
| `docs/FIXES.md`, `docs/PROGRESS.md` | F-12 row flipped to ✅ DONE |

## Live Test Results

### Undocumented headers are real

Direct probe of `https://advert-api.wildberries.ru/api/advert/v2/adverts` while the seller was throttled confirmed the gateway actually sends these headers (not in any swagger):

```
status: 429
x-ratelimit-reset: 564
x-ratelimit-retry: 564
x-ratelimit-limit: 1
```

On successful calls, the gateway also sends `x-ratelimit-remaining: N` — a preemptive budget hint used later by I-13.

### Happy path unaffected

After the seller cooldown cleared, `wb --json --compact campaign list` returned a full 49 KB JSON payload in a few seconds — confirms F-12 doesn't regress the normal flow.

### Fail-fast path (unit-tested)

The 564 s seller-scope bail-out is tested directly in `test_large_retry_after_bails_out_without_retry` — the test fixes `respx` to a mocked 429 with `x-ratelimit-reset: 564`, configures `max_retries=3`, then asserts:

- **Exactly one HTTP call attempted** (no retries)
- **`sleeps == []`** (no backoff waits)
- **`exc.retry_after == 564.0`** (value surfaced for the CLI error JSON)

Live demonstration would require deliberately re-tripping the WB throttle, which would have compounded the penalty we spent this session paying down — unit tests are authoritative for this path.

### Small-reset retry still works

`test_small_retry_after_still_retries` confirms that `x-ratelimit-reset: 20` (a per-endpoint window) triggers one retry at 20 s and then succeeds — the intended behaviour for fullstats / funnel throttles that recover quickly.
