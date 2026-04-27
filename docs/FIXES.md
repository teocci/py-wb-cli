# WB CLI — Fix Index

Tracks planned and in-progress bug fixes. Completed fixes: [docs/phases/](phases/) · Release history: [CHANGELOG.md](../CHANGELOG.md)

## Fix Index

| Fix | Name | Status | Scope | Version | Notes |
|-----|------|--------|-------|---------|-------|
| F-1 | Auth fix — dual auth, portal session | ✅ DONE | auth, profiles | 0.3.1 | [detail](phases/F-1-auth-fix.md) |
| F-2 | API fix — endpoint migration | ✅ DONE | constants, clients | 0.3.2 | [detail](phases/F-2-api-migration.md) |
| F-3 | Agent-critical fixes | ✅ DONE | JSON errors, per-NM stats | 0.9.0 | [detail](phases/F-3-agent-fixes.md) |
| F-4 | UTF-8 pipe fix | ✅ DONE | cli/app.py + 7 CLI modules | 0.20.2 | [detail](phases/F-4-utf8-pipe.md) |
| F-5 | Budget unit + unified bid_type | ✅ DONE | services/budgets.py, models | 0.20.3 | [detail](phases/F-5-budget-unit.md) |
| F-6 | TTY-aware ANSI output | ✅ DONE | core/output.py | 0.20.4 | [detail](phases/F-6-tty-ansi.md) |
| F-7 | campaign list --fields projection | ✅ DONE | cli/campaign.py | 0.20.5 | [detail](phases/F-7-fields-projection.md) |
| F-8 | Empty PaymentType crash | ✅ DONE | domain/models.py | 0.20.6 | [detail](phases/F-8-payment-type.md) |
| F-9 | Patient 429 backoff on seller-global throttle | ✅ DONE | client/http.py | 0.25.1 | [detail](phases/F-9-patient-429-backoff.md) |
| F-10 | Seller-scope global rate limiter (JWT `sid`-keyed) | ✅ DONE | core/rate_limiter.py, services/_factory.py, client/http.py | 0.25.2 | [detail](phases/F-10-seller-global-limiter.md) |
| F-11 | Dedup `list_campaigns` in daily-report | ✅ DONE | services/stats.py | 0.25.3 | [detail](phases/F-11-dedup-list-campaigns.md) |
| F-12 | Honor `x-ratelimit-reset` header (60 s bail-out) | ✅ DONE | client/http.py | 0.25.4 | [detail](phases/F-12-ratelimit-reset-header.md) |
| F-13 | `SellerCooldownLock` short-circuit on known cooldown | ✅ DONE | core/rate_limiter.py, services/_factory.py, client/http.py | 0.25.5 | [detail](phases/F-13-seller-cooldown-lock.md) |
| F-14 | `rate status` misses seller cooldown (astronomic compounded cooldowns) | ✅ DONE | core/endpoint_budget.py, cli/rate.py, client/http.py | 0.30.0 | [detail](phases/F-14-rate-status-misses-cooldown.md) — resolved by metadata-driven redesign R-1..R-4 |
| F-15 | Base tokens trip 30-min penalty — uniform-rate assumption | ✅ DONE | core/rate_limits.py, auth/profiles.py, cli/auth.py, cli/rate.py, client/http.py, services/_factory.py, .claude/skills/wb-rate-*, RATE_LIMITS.md | 0.31.0 | [detail](phases/F-15-rate-base-token-blindspot.md) — resolved by R-5 |
| F-16 | `generate_daily_wb_report.py` — `/api/advert/v2/adverts` 1-hour lockout on Base tokens | ✅ DONE | scripts/generate_daily_wb_report.py | 0.32.1 | [detail](phases/F-16-product-spend-rate-handling.md) — resolved by I-15 + script hygiene |
| F-17 | CLI hardcoded `'default'` profile fallback + `cache list` table render | ✅ DONE | cli/_helpers.py, cli/cache.py, cli/budget.py, cli/bid.py, cli/campaign.py, cli/cluster.py | 0.32.2 | [detail](phases/F-17-profile-fallback.md) |

### In Progress

- **F-14** is being addressed by the rate-limit redesign. See phases R-1..R-4 in [IMPROVEMENTS.md](IMPROVEMENTS.md). The redesign deletes F-13's `SellerCooldownLock` (whose blast radius caused the astronomic compounded cooldowns) and replaces it with per-(token, endpoint) buckets driven by WB's own `x-ratelimit-*` response headers.
- **F-15** is being addressed by R-5 (token-type-aware rates + `wb rate` overhaul + skill refresh). Discovered during R-1 live testing on 2026-04-26 — the WB live web docs reveal Base-token limits that swagger files don't show (e.g. `/adv/v1/balance` is 2 req/HOUR for Base, not 1/s). `wb rate probe` and the `wb-rate-*` skills currently treat all token types uniformly, which is why two probe-style calls cost the seller a 30-minute lockout.

## How to Add a Fix

1. Add a row to the table above (status = 🔲 PLANNED)
2. Create a stub in [docs/phases/](phases/) with goal + steps
3. Update [docs/PROGRESS.md](PROGRESS.md) phase index
4. Implement (say **NEXT**)
5. When done: run `phase-complete` skill to finalize
