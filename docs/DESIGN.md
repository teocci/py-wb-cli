# WB CLI — Design Reference

> Architecture and decision guide. Endpoint constants: `src/wb/core/constants.py`. Authoritative API docs: `dev-wb-adv.md`.

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
wb stats campaign / campaigns [--ids ... | --status running|paused|active] / product-spend / daily-report

# Analytics (separate token)
wb analytics search-report main / groups
wb analytics sales-funnel products [--min-orders N] [--all] / history / grouped

# Reports (Phase 8A+)
wb report warehouse create / status / download / top / stock-runway

# Prices (Phase 8D)
wb prices list [--nm-ids ...] [--min-discount N]

# Optimization (Phase 5)
wb optimize plan / run / clusters / budget / negatives / portfolio

# Composite (Phase I-3)
wb product summary --nms ...
wb campaign overview --id ...

# Agent-native (Phase I-7)
wb assess [--nm ...] [--quick]
wb pulse --campaigns ...
```

---

## Global CLI Flags

| Flag | Purpose |
|------|---------|
| `--json` | Machine-readable output |
| `--compact` | Single-line JSON |
| `--fields a,b` | JSON field projection |
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

**Product roles:** Hero → Support → Experimental

**Cluster classification:** efficient+scalable / visible+weak / expensive+non-converting / inactive+promising / noisy+exclusion-worthy

---

## Authentication

### Credential Resolution Priority

```
CLI flags > Environment variables > .env file > ~/.wb-cli/profiles.json
```

### Auth Methods

1. **API Key** — raw JWT in `Authorization` header (no Bearer). 180-day validity.
2. **Portal Session** — `cookie + authorizev3` headers (both required).

---

## Reliability Rules

- Read rate-limit headers; use bounded exponential backoff with jitter
- Retry: 429, 500, 502, 503, 504 — up to `max_retries` (default 3)
- Non-retryable: 400, 401, 403, 404, 422
- Prefer read-before-write for dry-run diff generation
- Preemptive rate limiting via `RateLimiter` — no agent sleeps needed

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
| 9 | Local SQLite cache is explicit-only — never hidden state |
| 10 | SDK is a pure function facade — no try/except wrapping |

## Open Questions

| # | Question | Direction |
|---|----------|-----------|
| Q3 | Optimizer threshold config? | Per-profile with campaign-level overrides |
| Q4 | Campaign clone templates? | V1.5+ |
| Q5 | Scheduling / recurring runs? | External cron; not in CLI core |
