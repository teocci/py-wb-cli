# Fix F-9 — Patient 429 backoff on seller-global throttle (v0.25.1)

**Date:** 2026-04-24
**Tests:** 1089/1090 (1 pre-existing env-isolation failure in `test_auth_list_empty`, unrelated)

## Problem

When WB's gateway returned HTTP 429 with body `"Limited by global limiter, per seller <uuid>"` and no `Retry-After` header, the HTTP client fell back to the standard exponential schedule (`DEFAULT_RETRY_BASE_DELAY * 2^attempt` ≈ 1.5 / 3 / 6 s + jitter). Seller-level throttles actually need multiple seconds-to-tens-of-seconds to clear, so all four attempts burned inside the throttle window and the CLI exited `RATE_LIMITED` (5) every time. Pre-fix live log:

```
Rate limited (attempt 1/4), retrying in 1.5s
Rate limited (attempt 2/4), retrying in 2.8s
Rate limited (attempt 3/4), retrying in 5.8s
```

## What Was Built

- **`RateLimitError` carries the response body.** `response_body` field added to the exception in `src/wb/core/exceptions.py`. The HTTP client populates it from `response.text` at the 429 raise site in `_check_error_status`. The raw body is the only reliable signal for seller-global throttle detection — `Retry-After` isn't sent by the WB gateway in the seller-global case.
- **Body-aware delay branch.** New helper `_is_seller_global_throttle(exc)` in `src/wb/client/http.py` matches the marker substring `'global limiter'` (case-insensitive) in the response body. `_calculate_delay` ORs this check with the existing `_is_upstream_error` check, so both 5xx errors and seller-global 429s take the patient schedule (`UPSTREAM_RETRY_BASE_DELAY * UPSTREAM_RETRY_MULTIPLIER^attempt` ≈ 5 / 15 / 45 s + jitter).
- **Retry-After still wins.** `_retry_or_raise` preserves `delay = retry_after or self._calculate_delay(...)` — a server-supplied `Retry-After` value overrides the local schedule regardless of body content.
- **Per-endpoint 429s unchanged.** A 429 with no `'global limiter'` marker (e.g. a future per-endpoint throttle) still uses the 1 / 2 / 4 s schedule, because the patient schedule is wasted overkill for a short per-endpoint window.

## Files Changed

| File | Change |
|------|--------|
| `src/wb/core/exceptions.py` | Added `response_body` kwarg + attribute to `RateLimitError`; docstring extended |
| `src/wb/client/http.py` | New `_SELLER_GLOBAL_THROTTLE_MARKER` constant, `_is_seller_global_throttle` helper; `_calculate_delay` branches on it; `_check_error_status` passes `response.text` into `RateLimitError`; docstring updated |
| `tests/unit/test_http_client.py` | 4 new tests: `test_rate_limit_captures_response_body`, `test_seller_global_429_uses_patient_schedule`, `test_plain_429_uses_short_schedule`, `test_retry_after_header_overrides_patient_schedule` |
| `docs/FIXES.md`, `docs/PROGRESS.md` | F-9 row flipped to ✅ DONE |

## Live Test Results

Ran `wb --json --compact stats daily-report --date 2026-04-23` while the seller was currently 429'd. Log output:

```
2026-04-24 12:20:21 [WARNING] wb.client.http: Rate limited (attempt 1/4), retrying in 5.2s
2026-04-24 12:20:27 [WARNING] wb.client.http: Rate limited (attempt 2/4), retrying in 15.4s
2026-04-24 12:20:44 [WARNING] wb.client.http: Rate limited (attempt 3/4), retrying in 49.1s
{"status": "error", "error": {"code": "RATE_LIMITED", "message": "Rate limited by WB API", "exit_code": 5}}
```

5.2 / 15.4 / 49.1 s matches `UPSTREAM_RETRY_BASE_DELAY * UPSTREAM_RETRY_MULTIPLIER^attempt` (5 / 15 / 45 s + ≤50% jitter) exactly. Total wall time ~70 s across 4 attempts vs. ~13 s pre-fix.

The command still eventually exits `RATE_LIMITED` because *all three endpoints* were seller-throttled at once — F-9 on its own does not prevent 429s, only makes retries patient enough to ride out transient throttle windows. Preemptive avoidance lands in F-10.
