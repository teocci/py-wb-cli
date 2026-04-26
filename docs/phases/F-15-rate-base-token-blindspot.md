# Fix F-15 — `wb rate` code & skills assume uniform endpoint limits (Base-token blindspot)

**Status:** 🔲 PLANNED — addressed by R-5
**Bug discovered:** 2026-04-26 during R-1 live testing
**Plan:** [R-5 phase doc](R-5-token-type-aware-rates.md)

## Problem

WB applies **per-token-type** rate limits on many advert endpoints. The live web docs show the breakdown explicitly (e.g. for `/adv/v1/balance`):

| Type     | Period | Limit      | Interval | Burst      |
|----------|--------|------------|----------|------------|
| Personal | 1 s    | 1 request  | 1 s      | 5 requests |
| Service  | 1 s    | 1 request  | 1 s      | 5 requests |
| Base     | 1 h    | 2 requests | 30 min   | 1 request  |
| Test     | …      | …          | …        | …          |

The swagger files in `docs/swagger/` only document the Personal / Service variant. Base-token limits are **dramatically tighter** but invisible from swagger alone.

**Impact in our code:**

1. **`wb rate probe`** currently calls `/adv/v1/balance` as "the safest single-call probe". For Base tokens, that single call exhausts the burst-1 bucket, and a second probe (or any other balance call) within 30 minutes returns HTTP 429 with `x-ratelimit-reset: 1800` — a 30-minute lockout.
2. **`ENDPOINT_LIMITS` priors** in `src/wb/core/rate_limits.py` are uniform per endpoint, so the metadata-driven `EndpointBudget` (R-1) bootstraps with the wrong window for Base tokens. Bootstrap → first call → 200 with `remaining=0` → interval-fallback → second call → 429.
3. **`rate status` doesn't show the token type**, so an operator can't tell from the diagnostic which bucket family their lock belongs to.
4. **Agent skills** (`.claude/skills/wb-rate-guide`, `.claude/skills/wb-rate-recover`) document `wb rate probe` as the recommended verification step. For Base-token sellers this guidance is dangerous.
5. **`RATE_LIMITS.md`** has no token-type column — same blindspot as the swagger files we generate it from.

## Live evidence

Two safe calls during R-1 live testing produced:
```
Call 2 → /adv/v1/balance → HTTP 429
  x-ratelimit-limit: 1
  x-ratelimit-reset: 1800
  x-ratelimit-retry: 1800
```
30-minute lockout from a 2-call test that the docs implied was within a 1/s budget.

A follow-up test on `/adv/v1/promotion/count` (swagger: 5/s, burst 5) returned `x-ratelimit-remaining: 0` after the very first call — the bail-out we added to the test script prevented a second 429 but confirmed Base limits apply broadly, not just to balance.

## Fix approach

See [R-5 phase doc](R-5-token-type-aware-rates.md) for the implementation plan. In summary:

- Detect token type from the JWT (the `t` claim or equivalent — needs investigation).
- Make `ENDPOINT_LIMITS` token-type-aware (Base override layer at minimum).
- Switch `rate probe` to a Base-friendlier endpoint OR refuse to probe when the type is Base and the chosen endpoint has tight limits.
- Add token type to `rate status` output and (in A-3) `wb auth whoami`.
- Refresh `wb-rate-guide` and `wb-rate-recover` skills to document Base-token caveats.
- Add a token-type column to `RATE_LIMITS.md` for endpoints with known stratification.

## Sequencing

R-5 lands **after** R-4 (so the metadata-driven substrate is in place) and **before** A-3 (which displays seller info via `whoami` and benefits from token-type detection landing first).
