# Fix F-14 — `rate status` misses seller cooldown / astronomic compounded cooldowns

**Status:** 🔲 PLANNED — superseded by metadata-driven redesign R-1..R-4.
**Bug filed:** [bugs/2026-04-25-rate-status-misses-seller-cooldown.md](../../bugs/2026-04-25-rate-status-misses-seller-cooldown.md)
**Plan:** [analyze-why-the-wb-gentle-lightning.md](../../../../Users/teocci/.claude/plans/analyze-why-the-wb-gentle-lightning.md)

## Problem

Two related symptoms with one root cause:

1. **`wb rate status` reports "clear"** while the very next command immediately fails with `Seller cooldown active - 3499s remaining`. `rate_status()` reads exactly one row from `seller_cooldown` keyed by the resolved token's seller fingerprint; if the resolved token differs from the one that armed the lock (different env/profile context, non-JWT token without `sid`), the row is missed and the diagnostic silently lies.
2. **`stats product-spend` produces "astronomic" cooldowns** (1700–3500 s). When WB returns one 429 with `x-ratelimit-reset: 3499`, F-13's `SellerCooldownLock` writes a *seller-wide* deadline. Every subsequent `wb` command — to *any* endpoint — short-circuits until that deadline, even endpoints whose buckets aren't actually full. F-13 trades fewer 429s for hour-long dead time.

## Root cause

F-13's lock is seller-wide; WB's actual penalties are per-endpoint. The static `SELLER_GLOBAL_BUDGET = (30, 60.0)` is also a guess about WB's gateway behaviour rather than a fact derived from response headers.

## Fix approach

Replace F-13 (`SellerCooldownLock`) and the static seller-global limiter with a metadata-driven `EndpointBudget`: per-`(token_fingerprint, endpoint)` state populated from WB's own `x-ratelimit-limit` / `x-ratelimit-remaining` / `x-ratelimit-reset` headers on every response (200 *and* 429). Other endpoints stay usable when one is locked. `rate status` reads the new table without per-token gating, so the diagnostic mismatch is impossible by construction.

See R-1..R-4 in [IMPROVEMENTS.md](../IMPROVEMENTS.md) for the phased rollout.
