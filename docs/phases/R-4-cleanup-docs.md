# Phase R-4 — Cleanup + docs

**Status:** 🔲 PLANNED · **Depends on:** R-3
**Plan:** [analyze-why-the-wb-gentle-lightning.md](../../../../Users/teocci/.claude/plans/analyze-why-the-wb-gentle-lightning.md)

## Goal

Delete the now-dead F-13 / seller-global code paths, refresh the public docs to describe the metadata-driven model, and mark F-14 / phases R-1..R-4 ✅ DONE.

## Changes

| File | Change |
|------|--------|
| `src/wb/core/rate_limiter.py` | Delete `SellerCooldownLock` class; delete `compute_seller_fingerprint` (unused). Keep `RateLimiter`, `SharedRateLimiter` (still used as `EndpointBudget`'s bootstrap window) and `compute_token_fingerprint`. |
| `src/wb/core/constants.py` | Delete `SELLER_GLOBAL_BUDGET`, `SELLER_GLOBAL_SCOPE_KEY`. |
| `tests/unit/test_rate_limiter.py` | Delete `TestSellerCooldownLock` and `TestCooldownLockFactory`. |
| `RATE_LIMITS.md` | Rewrite "How throttling works": `ENDPOINT_LIMITS` is now a bootstrap prior, not the cap; runtime authority is WB's `x-ratelimit-*` headers per `(token, endpoint)`. Update `wb rate status` example. |
| `docs/PROGRESS.md`, `docs/IMPROVEMENTS.md`, `docs/FIXES.md` | Flip R-1..R-4 + F-14 to ✅ DONE; assign final versions. |
| `bugs/2026-04-25-rate-status-misses-seller-cooldown.md` | Mark resolved with reference to F-14 phase file. |
| `CHANGELOG.md` | Release entry summarising the redesign + breaking JSON shape for `rate status --json`. |

## Out-of-scope follow-up (separate release)

- Drop the `seller_cooldown` SQLite table from `rate_limits.db` (DROP TABLE IF EXISTS) one cycle after R-4 ships. Keeps the migration non-destructive in case a stale process still writes to it during the rollout.

## Verification

- Full `pytest tests/unit/ -v --cov=wb` green.
- Manual end-to-end: rerun the daily-report script that originally triggered the bug. A 429 on `stats product-spend` no longer locks `stats orders`. `wb rate status` shows the precise endpoint and reset time.
