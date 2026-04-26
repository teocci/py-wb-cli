# Phase R-5 — Token-type-aware rate handling + `wb rate` overhaul + skill refresh

**Status:** 🔲 PLANNED · **Depends on:** R-4 (metadata-driven substrate must be in place)
**Resolves:** F-15
**Plan:** [analyze-why-the-wb-gentle-lightning.md](../../../../Users/teocci/.claude/plans/analyze-why-the-wb-gentle-lightning.md) (out-of-scope follow-up)

## Goal

Eliminate the Base-token blindspot in our rate-limit subsystem. After R-5, `wb rate probe` no longer triggers a 30-minute lockout for Base tokens, `rate status` shows token type, `ENDPOINT_LIMITS` priors are token-type-aware, and the agent skills (`wb-rate-guide`, `wb-rate-recover`) document the new model so agents don't blindly run `wb rate probe` on Base credentials.

## What needs investigation first

- **Which JWT claim signals token type?** WB's docs distinguish Personal / Service / Base / Test, but `dev-wb-adv.md` doesn't say which JWT claim carries that info. R-5 starts with a small spike: dump the claims from a known Base token vs a known Personal token and identify the discriminator. Likely candidates: `t`, `tt`, `type`, `tokenType`, `oid`, or a scope-derived signal.
- **Which endpoints actually differ for Base?** `/adv/v1/balance` is documented (in the live web docs). `/adv/v1/promotion/count` empirically returns `remaining=0` after one call for Base, so it's also affected. Need a comprehensive sweep against the live web docs (NOT the swagger) for every endpoint our CLI uses. Capture in a new `RATE_LIMITS_BY_TYPE.md` or extend `RATE_LIMITS.md` with a token-type column.

## Changes

### Code

| File | Change |
|------|--------|
| `src/wb/core/rate_limiter.py` | New `compute_token_type(token) -> Literal['personal', 'service', 'base', 'test', 'unknown']` helper extracting the type from the JWT claim identified during the spike. |
| `src/wb/core/rate_limits.py` | `ENDPOINT_LIMITS` becomes a dict-of-dicts keyed by `(endpoint, token_type)` OR a primary table + a `BASE_TOKEN_OVERRIDES` map. Decision based on how many endpoints actually differ. |
| `src/wb/core/endpoint_budget.py` | `reserve(..., prior=...)` callers (in R-2's HTTP client integration) start passing the type-resolved prior. The class itself doesn't change — priors are still `(calls, period_seconds)`. |
| `src/wb/services/_factory.py` | Wiring change: when constructing the prior for a request, look up `ENDPOINT_LIMITS[endpoint][token_type]`. |
| `src/wb/cli/rate.py` `rate_probe` | Pick endpoint based on detected token type. For Base, use a less penalty-prone endpoint (or refuse to probe and emit a diagnostic); for Personal/Service, keep `/adv/v1/balance`. |
| `src/wb/cli/rate.py` `rate_status` | Display detected token type per token in the output (already grouping by seller in R-3). |

### Skills

| File | Change |
|------|--------|
| `.claude/skills/wb-rate-guide/SKILL.md` | Add a "Token-type caveats" section. Note that the rates in the table are for Personal/Service tokens; Base tokens are tighter on advert endpoints. Recommend `wb auth whoami` to confirm token type. |
| `.claude/skills/wb-rate-recover/SKILL.md` | Update the probe section: for Base tokens, *do not run `wb rate probe`* unless the operator accepts a 30-minute lockout. Replace the F-12/F-13 references with the new metadata-driven model. Update the decision tree. |
| `.claude/skills/wb-pulse/SKILL.md`, `.claude/skills/wb-assess/SKILL.md`, `.claude/skills/wb-daily-report/SKILL.md` | Sweep for assumptions about uniform rates / `rate probe` safety. |

### Docs

| File | Change |
|------|--------|
| `RATE_LIMITS.md` | Add a "Token type" column where stratification exists. Cross-reference the live web docs as the source of truth (not swagger). |
| `docs/web/rate-limits.md` | Already imported. Reference it from `RATE_LIMITS.md`. |
| `docs/PROGRESS.md`, `docs/IMPROVEMENTS.md`, `docs/FIXES.md` | Flip R-5 + F-15 to ✅ DONE; assign final versions. |

### Tests

- `tests/unit/test_rate_limiter.py` — coverage for `compute_token_type` against synthetic JWTs (one per type plus malformed).
- `tests/unit/test_factory.py` — assert the prior selected for a Base token differs from Personal on a known stratified endpoint.
- `tests/unit/test_cli_rate.py` (new or existing) — `rate probe` chooses the type-appropriate endpoint; `rate status` shows token type.

## Verification

- **Spike:** dump claims from a Base token (`def07bba…`) — confirm which claim signals "Base".
- **Unit:** full suite green.
- **Manual:** `wb auth whoami` (will exist after A-3) shows token type. `wb rate probe` against a Base token does NOT lock the seller for 30 minutes. `wb rate status` displays token type per token.
- **Skills:** read each updated skill end-to-end, then run a representative agent prompt to verify the guidance produces sensible behaviour.

## Risks / unknowns

- **The JWT claim might not carry token type explicitly.** If WB derives type from server-side state, we may need to *infer* from a minimal probe call's headers. Worst case: store the inferred type on `Profile.token_type` after first observation.
- **The Base-token catalog might be incomplete.** New endpoints discovered later may have hidden Base limits. The metadata-driven `EndpointBudget` from R-1..R-4 is the safety net: even when the prior is wrong, the first 429 corrects course.

## Out of scope

- Token-type-specific rate tuning beyond Base (Test tokens are not in production use here; Personal vs Service are equivalent in the docs we've seen).
- Detecting type changes mid-session (a token's type is set at issuance — we can cache it).
