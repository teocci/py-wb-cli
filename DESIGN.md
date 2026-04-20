# WB CLI - Design Reference

> Condensed architecture and decision guide. Full spec: `wb_cli_implementation_plan.md`

---

## What This Is

A **command-line control plane** for Wildberries advertising operations.
Not a custom ad engine — WB runs the auction. We control the inputs:
campaigns, bids, search clusters, minus phrases, budgets, and statistics.

Two user classes must both be satisfied:
- **Human operator** — readable commands, tables, helpful defaults
- **AI agent** — deterministic JSON I/O, stable exit codes, dry-run safety

---

## Architecture

```
CLI Layer (Typer)
    → Service Layer (use-cases)
        → WB Client Layer (HTTP + auth + retries)
        → Domain Model (campaigns, bids, clusters, stats)
    → Output Layer (tables / json / errors)
    → Local Storage (profiles, audit log, cache)
```

### Layers and their files

| Layer | Package | Responsibility |
|-------|---------|---------------|
| CLI | `wb.cli.*` | Typer commands, flag parsing, output dispatch |
| Service | `wb.services.*` | Use-cases, orchestration, mutation planning |
| Client | `wb.client.*` | HTTP, auth headers, retries, rate limits |
| Domain | `wb.domain.*` | Normalized models and enums |
| Auth | `wb.auth.*` | Multi-profile token storage, validation |
| Core | `wb.core.*` | Constants, exceptions, config, output rendering |
| Storage | `wb.storage.*` | Audit log, optional local cache |

---

## Command Taxonomy

```bash
# Auth
wb auth login / logout / list / use / status / ping / categories
wb auth login-portal / generate-token

# Portal
wb portal products

# Campaigns
wb campaign list / get / create / rename / delete
wb campaign start / pause / stop / clone
wb campaign eligible-subjects / eligible-items
wb campaign add-items / remove-items / set-placements

# Item bids
wb bid recommend / minimum / get-items / set-item / set-items

# Search clusters
wb cluster list / active / inactive / bids
wb cluster set-bids / delete-bids / stats / stats-daily
wb cluster minus list / set / clear

# Budget
wb budget balance / get / topup / history

# Statistics
wb stats campaign / campaigns [--ids ... | --status running|paused|active] / product-spend

# Analytics (Phase 4, separate token)
wb analytics search-report main / groups
wb analytics sales-funnel products
wb analytics csv create / list / download

# Reports (Phase 8A+)
wb report warehouse create / status / download / top

# Optimization (Phase 5)
wb optimize plan / run / clusters / budget / negatives / portfolio
```

---

## Global CLI Flags

Every command supports:

| Flag | Purpose |
|------|---------|
| `--json` | Machine-readable output |
| `--quiet` / `-q` | Suppress non-essential output |
| `--verbose` / `-v` | Debug-level logging |
| `--profile` / `-p` | Use a named profile |
| `--dry-run` | (mutating commands) Plan without executing |
| `--yes` | Skip confirmation prompts |

---

## Domain Concepts

**The three-level operational unit:**
1. **Campaign** — lifecycle and budget container
2. **Product card** — selling entity receiving traffic
3. **Search cluster** — practical approximation of query intent

Performance problems happen at any of these three levels, so the CLI and optimizer reason at all three.

**Product roles:** Hero → Support → Experimental

**Cluster classification:** efficient+scalable / visible+weak / expensive+non-converting / inactive+promising / noisy+exclusion-worthy

---

## WB API Endpoints

### Promotion (Phase 1-3, primary token)
- `GET /adv/v1/promotion/adverts` — list campaigns
- `GET /adv/v2/fullstats` — campaign statistics
- `GET /adv/v1/auto/active-words` — active search clusters
- `GET /adv/v1/auto/words` — all clusters + bids
- `POST /adv/v1/auto/set-bid` — set cluster bids
- `POST /adv/v1/auto/del-excluded-words` — clear cluster bids
- `GET /adv/v2/auto/stat-words` — cluster statistics
- `GET /adv/v1/budget` — campaign budget
- `POST /adv/v1/budget/deposit` — top up budget
- `GET /adv/v1/account/balance` — account balance
- `GET /adv/v2/promotion/recommended_cpm` — recommended bids
- `POST /adv/v0/start` / `pause` / `stop` — lifecycle

### Analytics (Phase 4, separate token)
- `POST /api/v1/paid_acceptance` — search queries per item
- Sales funnel and CSV report endpoints

### Seller Portal (JSON-RPC, session auth)
- `POST seller.wildberries.ru/ns/suppliers-auth/suppliers-portal-core/auth/token` — portal session auth
- `POST seller-content.wildberries.ru/ns/suppliers-auth-tokens/suppliers-portal-core/api/v1/tokensjrpc` — token generation

### Connection Check
- `GET <domain>/ping` — per-category connection check (e.g., `advert-api.wildberries.ru/ping`)

---

## Authentication

### Credential Resolution Priority

All credentials follow the same chain (highest to lowest):
```
CLI flags > Environment variables > .env file > ~/.wb-cli/profiles.json
```

### Auth Methods

1. **API Key** (official) — JWT token in `Authorization` header (no Bearer prefix). Created via seller portal UI. 180-day validity.
2. **Portal Session** (reverse-engineered) — `cookie + authorizev3` headers together (both required). Enables portal-only data access (product cards, token generation).

See `wb_portal_authentication_notes.md` for detailed test results on which header combinations work.

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `WB_API_TOKEN` | API token (fallback for profile token) |
| `WB_AUTHORIZEV3` | Portal authorizev3 key |
| `WB_PORTAL_COOKIE` | Portal browser cookie |
| `WB_USER_ID` | Seller user ID |
| `WB_TOKEN_EXPIRATION` | Token expiration timestamp |

---

## Reliability Rules

- Read rate-limit headers; use bounded exponential backoff with jitter
- Retry: 429, 500, 502, 503, 504 — up to `max_retries` (default 3)
- Non-retryable: 400, 401, 403, 404, 422
- Prefer read-before-write for dry-run diff generation
- No aggressive parallelism by default

---

## Key Decisions (Closed)

| # | Decision |
|---|----------|
| 1 | CLI is an ads operations control plane, not just a campaign wrapper |
| 2 | Target is profitable visibility under constraints, not just first-page presence |
| 3 | Search clusters are central, not secondary |
| 4 | Promotion = execution core; Analytics = discovery extension |
| 5 | Optimizer is recommendation-first in V1 (no auto-mutation) |
| 6 | Multi-profile is foundational, not optional |
| 7 | Budget handling is part of optimization logic |
| 8 | Dry-run is mandatory on all write operations |

## Open Questions

| # | Question | Direction |
|---|----------|-----------|
| Q1 | Local SQLite cache? | Yes, explicit cache only — never hidden state |
| Q2 | Agent adapters: subprocess or Python SDK? | Start subprocess-safe; evaluate SDK later |
| Q3 | Optimizer threshold config? | Per-profile with campaign-level overrides |
| Q4 | Campaign clone templates? | V1.5+ |
| Q5 | Scheduling / recurring runs? | External cron; not in CLI core |
