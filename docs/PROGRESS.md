# WB CLI — Progress

Coding instructions: [CLAUDE.md](../CLAUDE.md) · Command reference: [AGENT.md](../AGENT.md) · Release history: [CHANGELOG.md](../CHANGELOG.md)

## Quick Status

| Metric | Value |
|--------|-------|
| **Current Version** | 0.30.0 |
| **Tests Passing** | 1169/1171 (1 pre-existing env test + 1 timing-flaky in-memory limiter test that passes solo) |
| **Phases Complete** | 43 |
| **Agent-Ready** | YES — JSON mode, `--compact`, `--sort-by`/`--top N`, composite reads, idempotent mutations, `--fields`, preemptive rate limiting |

## Phase Index

| Phase | Name | Status | Version |
|-------|------|--------|---------|
| 0 | Foundation | ✅ DONE | 0.1.0 |
| 1 | Read-only operational visibility | ✅ DONE | 0.2.0 |
| 2 | Core write controls | ✅ DONE | 0.3.0 |
| F-1 | Auth fix — dual auth, portal session, env var fallback | ✅ DONE | 0.3.1 |
| F-2 | API fix — full endpoint migration to current WB API | ✅ DONE | 0.3.2 |
| 3 | Search-cluster control | ✅ DONE | 0.4.0 |
| 4 | Analytics bridge | ✅ DONE | 0.5.0 |
| 5 | Optimization workflows | ✅ DONE | 0.6.0 |
| 6 | Agent platform support — Python SDK | ✅ DONE | 0.7.0 |
| 7 | Local SQLite cache + historical snapshots | ✅ DONE | 0.8.0 |
| F-3 | Agent-critical fixes — JSON errors, per-NM stats, nm_ids | ✅ DONE | 0.9.0 |
| 8A | Warehouse inventory reports | ✅ DONE | 0.10.0 |
| 8B | Stock runway (days-until-stockout) | ✅ DONE | 0.11.0 |
| 8C | Report caching & multi-seller storage | ✅ DONE | 0.12.0 |
| 8D | Prices & Discounts command | ✅ DONE | 0.13.0 |
| I-1 | Batch operations — multi-ID, auto-chunking, --fields | ✅ DONE | 0.14.0 |
| I-2 | Per-product cost tracking — product-spend, booster stats | ✅ DONE | 0.15.0 |
| I-3 | Composite commands — product summary (1 call = all data) | ✅ DONE | 0.16.0 |
| I-4 | Rate limiting & resilience — RateLimiter, auto-pagination | ✅ DONE | 0.17.0 |
| I-5 | Polish & ergonomics — --compact, --sort-by/--top N, AGENT.md | ✅ DONE | 0.18.0 |
| I-6 | Full token category support — 11 categories, --category all | ✅ DONE | 0.19.0 |
| I-7 | Agent skills — wb assess/pulse + 7 Claude Code skills | ✅ DONE | 0.20.0 |
| F-4 | UTF-8 pipe fix — stdout reconfigure + centralized console | ✅ DONE | 0.20.2 |
| F-5 | Budget unit fix (rubles) + unified bid_type | ✅ DONE | 0.20.3 |
| F-6 | TTY-aware ANSI output — no escape codes when piped | ✅ DONE | 0.20.4 |
| F-7 | campaign list --fields projection fix | ✅ DONE | 0.20.5 |
| F-8 | Empty PaymentType crash fix | ✅ DONE | 0.20.6 |
| I-8 | stats campaigns --status filter (running / paused / active) | ✅ DONE | 0.21.0 |
| I-9 | stats daily-report — ad spend + total orders; wb-daily-report skill | ✅ DONE | 0.22.0 |
| I-10 | sales-funnel products: --min-orders filter + --all auto-pagination | ✅ DONE | 0.23.0 |
| I-11 | Response cache for past-day stats/analytics + 5xx/429 retry split | ✅ DONE | 0.24.0 |
| I-12 | SQLite-backed cross-process rate limiter | ✅ DONE | 0.25.0 |
| F-9 | Patient 429 backoff on seller-global throttle | ✅ DONE | 0.25.1 |
| F-10 | Seller-scope global rate limiter (JWT `sid`-keyed) | ✅ DONE | 0.25.2 |
| F-11 | Dedup `list_campaigns` in `stats daily-report` | ✅ DONE | 0.25.3 |
| F-12 | Honor `x-ratelimit-reset` header (60 s bail-out) | ✅ DONE | 0.25.4 |
| F-13 | `SellerCooldownLock` short-circuit on known cooldown | ✅ DONE | 0.25.5 |
| I-13 | `wb rate-status` diagnostic command | ✅ DONE | 0.26.0 |
| I-14 | `wb rate probe` — single-call cooldown probe | ✅ DONE | 0.27.0 |
| F-14 | `rate status` misses seller cooldown — superseded by R-1..R-4 | ✅ DONE | 0.30.0 |
| R-1 | `EndpointBudget` state layer (header-driven, per-(token, endpoint)) | ✅ DONE | 0.28.0 |
| R-2 | HTTP client integration — drop F-13 lock + seller-global limiter | ✅ DONE | 0.28.0 |
| R-3 | `wb rate status` overhaul — read `endpoint_budget`, group by seller | ✅ DONE | 0.29.0 |
| R-4 | Cleanup — drop `SellerCooldownLock`, `SELLER_GLOBAL_BUDGET`, docs | ✅ DONE | 0.30.0 |
| F-15 | `wb rate` + skills assume uniform endpoint limits — Base tokens trip 30-min penalty | 🔲 PLANNED | TBD |
| R-5 | Token-type-aware rate handling + `wb rate` overhaul + skill refresh | 🔲 PLANNED | TBD |
| A-1 | `wb auth login --profile NAME` env bootstrap (non-breaking) | 🔲 PLANNED | TBD |
| A-2 | Drop runtime env fallback — profile becomes mandatory (BREAKING) | 🔲 PLANNED | TBD |
| A-3 | `wb auth whoami` + docs sweep for new auth model | 🔲 PLANNED | TBD |

Phase detail files: [docs/phases/](phases/)

**Active redesign:** [analyze-why-the-wb-gentle-lightning.md](../../../../Users/teocci/.claude/plans/analyze-why-the-wb-gentle-lightning.md) — metadata-driven rate-limit redesign (R-1..R-4), with [auth-homogenization.md](../../../../Users/teocci/.claude/plans/auth-homogenization.md) as the follow-up.

## How to Continue

```bash
source .venv/Scripts/activate   # Windows
pytest tests/unit/ -v
python -m wb --help
```

Say **NEXT** to implement the next pending phase.
