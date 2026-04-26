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

The swagger files in `docs/swagger/` carry the **full per-type table** (column header
is "Type", not "Token type") for every stratified endpoint — earlier reading missed
this and assumed swagger only had the Personal / Service variant. The R-5 catalog is
built directly from those tables.

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

See [R-5 phase doc](R-5-token-type-aware-rates.md) for the concretized implementation plan. In summary:

- **Token type is a profile field** (`Profile.token_type`, default `'base'`), settable via `wb auth login --token-type`. JWT auto-detection is deferred to a future R-6 phase pending a non-Base reference token.
- `ENDPOINT_LIMITS` gains a sibling `BASE_OVERRIDES` map; lookup goes through `select_prior(path, token_type)`. `WbHttpClient._pre_flight` uses it so first-call priors are Base-aware.
- **`wb rate probe` removed** as part of R-5. The command was vestigial since R-1..R-4 made the runtime header-driven, and on Base it could only be a 30-min footgun or a refusal. Replacements: `wb auth ping` for connectivity / token-validity (uniform `/ping` rate), `wb rate status` for budget visibility (no network).
- `wb rate status` displays `token_type` per token group. `wb auth whoami` (A-3) will surface it on the profile view.
- `wb-rate-guide` and `wb-rate-recover` skills get a "Base caveats" section; both now point at `wb auth ping` + `wb rate status` instead of probe.
- `RATE_LIMITS.md` gains a "Base override" column for stratified endpoints.

## Sequencing

R-5 lands **after** R-4 (so the metadata-driven substrate is in place) and **before** A-3 (which displays seller info via `whoami` and benefits from token-type detection landing first).
