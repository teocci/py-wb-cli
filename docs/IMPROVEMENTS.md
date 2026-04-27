# WB CLI — Improvement Index

Tracks planned and in-progress improvements. Completed phases: [docs/phases/](phases/) · Release history: [CHANGELOG.md](../CHANGELOG.md)

## Improvement Index

| Version | Phase | Status | Theme |
|---------|-------|--------|-------|
| 0.1.0 | 0 | ✅ DONE | Foundation — [detail](phases/0-foundation.md) |
| 0.2.0 | 1 | ✅ DONE | Read-only visibility — [detail](phases/1-read-only.md) |
| 0.3.0 | 2 | ✅ DONE | Core write controls — [detail](phases/2-write-controls.md) |
| 0.4.0 | 3 | ✅ DONE | Search-cluster control — [detail](phases/3-cluster-control.md) |
| 0.5.0 | 4 | ✅ DONE | Analytics bridge — [detail](phases/4-analytics.md) |
| 0.6.0 | 5 | ✅ DONE | Optimization workflows — [detail](phases/5-optimization.md) |
| 0.7.0 | 6 | ✅ DONE | Agent platform support — [detail](phases/6-sdk.md) |
| 0.8.0 | 7 | ✅ DONE | Local SQLite cache — [detail](phases/7-cache.md) |
| 0.10.0 | 8A | ✅ DONE | Warehouse inventory reports — [detail](phases/8A-warehouse.md) |
| 0.11.0 | 8B | ✅ DONE | Stock runway — [detail](phases/8B-stock-runway.md) |
| 0.12.0 | 8C | ✅ DONE | Report caching & multi-seller — [detail](phases/8C-report-cache.md) |
| 0.13.0 | 8D | ✅ DONE | Prices & Discounts command — [detail](phases/8D-prices.md) |
| 0.14.0 | I-1 | ✅ DONE | Batch operations — [detail](phases/I-1-batch.md) |
| 0.15.0 | I-2 | ✅ DONE | Per-product cost tracking — [detail](phases/I-2-product-spend.md) |
| 0.16.0 | I-3 | ✅ DONE | Composite commands — [detail](phases/I-3-composite.md) |
| 0.17.0 | I-4 | ✅ DONE | Rate limiting & resilience — [detail](phases/I-4-rate-limiting.md) |
| 0.18.0 | I-5 | ✅ DONE | Polish & ergonomics — [detail](phases/I-5-polish.md) |
| 0.19.0 | I-6 | ✅ DONE | Full token category support — [detail](phases/I-6-token-categories.md) |
| 0.20.0 | I-7 | ✅ DONE | Agent skills — [detail](phases/I-7-agent-skills.md) |
| 0.21.0 | I-8 | ✅ DONE | stats campaigns --status filter — [detail](phases/I-8-stats-status.md) |
| 0.22.0 | I-9 | ✅ DONE | stats daily-report — [detail](phases/I-9-daily-report.md) |
| 0.23.0 | I-10 | ✅ DONE | sales-funnel --min-orders + --all — [detail](phases/I-10-sales-funnel.md) |
| 0.24.0 | I-11 | ✅ DONE | Response cache + retry split — [detail](phases/I-11-response-cache.md) |
| 0.25.0 | I-12 | ✅ DONE | SQLite-backed cross-process rate limiter — [detail](phases/I-12-shared-rate-limiter.md) |
| 0.26.0 | I-13 | ✅ DONE | `wb rate-status` diagnostic command — [detail](phases/I-13-rate-status-command.md) |
| 0.27.0 | I-14 | ✅ DONE | `wb rate probe` — single-call cooldown probe — [detail](phases/I-14-rate-probe-command.md) |
| 0.28.0 | R-1  | ✅ DONE | `EndpointBudget` state layer — [detail](phases/R-1-endpoint-budget-state.md) |
| 0.28.0 | R-2  | ✅ DONE | HTTP client integration (drops F-13 + seller-global limiter from runtime) — [detail](phases/R-2-http-client-integration.md) |
| 0.29.0 | R-3  | ✅ DONE | `wb rate status` overhaul — [detail](phases/R-3-rate-status-overhaul.md) |
| 0.30.0 | R-4  | ✅ DONE | Cleanup + docs (deletes `SellerCooldownLock`) — [detail](phases/R-4-cleanup-docs.md) |
| 0.31.0 | R-5  | ✅ DONE | Token-type-aware rate handling + `wb rate probe` removal + skill refresh — [detail](phases/R-5-token-type-aware-rates.md) |
| 0.32.0 | I-15 | ✅ DONE | Cooldown-tied HTTP-layer request cache + `wb api-cache` diag (renamed to `wb cache` in I-16) — [detail](phases/I-15-request-cache.md) |
| 0.33.0 | I-16 | ✅ DONE | Rename `cache` → `snapshot` and `api-cache` → `cache` (BREAKING) — [detail](phases/I-16-rename-cache-snapshot.md) |
| TBD    | A-1  | 🔲 PLANNED | `wb auth login --profile NAME` env bootstrap — [detail](phases/A-1-auth-login-env-bootstrap.md) |
| TBD    | A-2  | 🔲 PLANNED | Drop runtime env fallback (BREAKING) — [detail](phases/A-2-drop-runtime-env-fallback.md) |
| TBD    | A-3  | 🔲 PLANNED | `wb auth whoami` + docs sweep — [detail](phases/A-3-auth-whoami-docs.md) |

---

## Best Practices for AI Agent CLIs

### 1. Token Efficiency

- **Compact output** — `--compact` for single-line JSON.
- **Field selection** — `--fields spend,orders,views` to return only what's needed.
- **Batch everything** — Every command that accepts a single ID should also accept comma-separated IDs.

### 2. Structured Output

- **JSON errors** — When `--json` is active, errors must be JSON, not colored text.
- **Machine-readable error codes** — `VALIDATION_ERROR`, `RATE_LIMITED`, not just messages.

### 3. Batch Operations

- **Array inputs** — `--ids 1,2,3`, `--nms 100525085,227403075`.
- **Auto-chunking** — Automatically split inputs exceeding API limits, merge results.
- **N+1 elimination** — Never loop single API calls when a batch endpoint exists.

### 4. No Interactive Prompts

- **Never block on stdin** — No `prompt=True`.
- **`--yes` flag** — Skip confirmation. When `--json` is active, auto-skip.
- **Fail fast** — Return a structured error immediately on missing required values.

### 5. Idempotent Operations

- `campaign start` on an already-running campaign returns `{"already_applied": true}`.

### 6. Composite Commands

- `product summary --nms 100525085` returns sales + ad spend + clusters + bids in one call.

---

## Current Issues (Open)

### HIGH

| Issue | Location | Impact |
|-------|----------|--------|
| N+1 in set_item_bids (legacy path) | `src/wb/services/bids.py` | May still exist in edge case |
| Hardcoded exit codes | Some CLI files | Inconsistent machine-readable codes |

### MEDIUM

| Issue | Location | Impact |
|-------|----------|--------|
| Analytics NM ID limit (20), no auto-chunking in history | `src/wb/services/analytics.py:114` | Silent truncation possible |
| No booster stats / search position | API returns `boosterStats[]` | Useful data discarded |

---

## How to Add an Improvement

1. Add a row to the index table above (status = 🔲 PLANNED)
2. Create a stub in [docs/phases/](phases/) with goal + steps
3. Update [docs/PROGRESS.md](PROGRESS.md) phase index
4. Implement (say **NEXT**)
5. When done: run `phase-complete` skill to finalize
