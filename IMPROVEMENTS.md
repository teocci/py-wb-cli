# WB CLI — AI Agent Improvement Roadmap

This document tracks improvements to make the WB CLI optimally usable by AI agents.
Discovered during real agent sessions (2026-04-03) where the CLI's limitations forced
the agent to bypass it and call raw HTTP endpoints.

## 🚀 Quick Status (for AI Agents)

Phase legend: `N` = core phase · `NA` = sub-phase · `F-N` = fix · `I-N` = improvement

| Version | Phase | Status | Theme | Files | Date |
|---------|-------|--------|-------|-------|------|
| 0.1.0 | 0 | ✅ DONE | Foundation | core setup | 2026-01-15 |
| 0.2.0 | 1 | ✅ DONE | Read-only visibility | campaign/stats | 2026-01-20 |
| 0.3.0 | 2 | ✅ DONE | Core write controls | campaign mutations | 2026-02-01 |
| 0.3.1 | F-1 | ✅ DONE | Auth fix — dual auth, portal session | auth, profiles | 2026-03-19 |
| 0.3.2 | F-2 | ✅ DONE | API fix — endpoint migration | constants, clients | 2026-04-02 |
| 0.4.0 | 3 | ✅ DONE | Search-cluster control | cluster commands | 2026-02-10 |
| 0.5.0 | 4 | ✅ DONE | Analytics bridge | analytics commands | 2026-02-20 |
| 0.6.0 | 5 | ✅ DONE | Optimization workflows | optimize commands | 2026-03-01 |
| 0.7.0 | 6 | ✅ DONE | Agent platform support | SDK | 2026-03-10 |
| 0.8.0 | 7 | ✅ DONE | Local SQLite cache | storage/cache | 2026-03-20 |
| 0.9.0 | F-3 | ✅ DONE | Agent-critical fixes | JSON errors, per-NM stats | 2026-03-28 |
| 0.10.0 | 8A | ✅ DONE | Warehouse inventory reports | report commands | 2026-04-04 |
| 0.11.0 | 8B | ✅ DONE | Stock runway analysis | days-until-stockout | 2026-04-04 |
| 0.12.0 | 8C | ✅ DONE | Report caching & multi-seller | file cache + SQLite | 2026-04-04 |
| 0.13.0 | 8D | ✅ DONE | Prices & Discounts command | wb prices list | 2026-04-06 |
| 0.14.0 | I-1 | ✅ DONE | Batch operations | multi-ID support, auto-chunking | 2026-04-06 |
| 0.15.0 | I-2 | ✅ DONE | Per-product cost tracking | product-spend command | 2026-04-06 |
| 0.16.0 | I-3 | ✅ DONE | Composite commands | product summary, campaign overview | 2026-04-06 |
| 0.17.0 | I-4 | ✅ DONE | Rate limiting & resilience | RateLimiter, RATE_LIMITS.md, paginate_all, _Container | 2026-04-07 |
| 0.18.0 | I-5 | ✅ DONE | Polish & ergonomics | --compact, --sort-by/--top N, AGENT.md | 2026-04-07 |

**Current:** v0.18.0 — **18 phases complete**, 0 planned. **918 tests passing**.

---

## Best Practices for AI Agent CLIs

### 1. Token Efficiency

- **Compact output** — Agents pay per-token; offer `--compact` for single-line JSON.
- **Field selection** — `--fields spend,orders,views` to return only what's needed.
- **Batch everything** — Every command that accepts a single ID should also accept
  comma-separated IDs. One call returning 50 results is cheaper than 50 calls.

### 2. Structured Output

- **Response envelope** — Every response (success or error) follows:
  ```json
  {"status": "ok|error", "data": ..., "meta": {"count": N, "timestamp": "..."}}
  ```
- **JSON errors** — When `--json` is active, errors must be JSON, not colored text.
- **Machine-readable error codes** — `VALIDATION_ERROR`, `RATE_LIMITED`, not just messages.

### 3. Batch Operations

- **Array inputs** — `--ids 1,2,3`, `--nms 100525085,227403075`.
- **Auto-chunking** — When input exceeds API limits (e.g., 50 campaigns for fullstats),
  automatically split into chunks, call the API for each, and merge results.
- **N+1 elimination** — Never loop single API calls when a batch endpoint exists.

### 4. No Interactive Prompts

- **Never block on stdin** — Remove `prompt=True` from CLI options.
- **`--yes` flag** — Skip confirmation prompts. When `--json` is active, auto-skip.
- **Fail fast** — If a required value is missing, return a structured error immediately.

### 5. Idempotent Operations

- **Safe retries** — `campaign start` on an already-running campaign returns
  `{"already_applied": true}` instead of an error.
- **Consistent state** — Same input always produces same output.

### 6. Composite Commands

- **Reduce round-trips** — `product summary --nms 100525085` returns sales + ad spend +
  clusters + bids in one call instead of 4 separate commands.

---

## Current Issues Found

### CRITICAL

| Issue | Location | Impact |
|-------|----------|--------|
| Errors are colored text, not JSON, even with `--json` | `src/wb/cli/app.py:79-80` | Agents can't parse errors |
| Interactive prompts block agents | `src/wb/cli/auth.py:30` (`prompt=True`) | Agent hangs on stdin |
| CampaignStats loses per-NM breakdown | `src/wb/domain/models.py:262-307` | Agent must bypass CLI for per-product spend |
| Campaign model drops product NM IDs | `src/wb/domain/models.py:66-81` | Agent can't discover which products are in a campaign |

### HIGH

| Issue | Location | Impact |
|-------|----------|--------|
| N+1 in set_item_bids | `src/wb/services/bids.py:125-127` | N HTTP calls instead of 1 batch call |
| No multi-campaign start/pause/stop | `src/wb/cli/campaign.py` | Agent must loop one-at-a-time |
| Hardcoded exit codes | `src/wb/cli/auth.py`, `bid.py`, etc. | Inconsistent machine-readable codes |
| No structured error codes in exceptions | `src/wb/core/exceptions.py` | No programmatic error matching |
| set_item_bid wraps single in array | `src/wb/client/promotion.py:385-391` | Forces N+1 at service layer |

### MEDIUM

| Issue | Location | Impact |
|-------|----------|--------|
| Batch size limits scattered | Multiple service files | Not auto-chunked |
| Analytics NM ID limit (20), no auto-chunking | `src/wb/services/analytics.py:114` | Silent truncation |
| Cache not auto-queried by services | `src/wb/storage/cache.py` | Redundant API calls |
| No per-product ad spend command | — | #1 agent question unanswerable in one call |
| No booster stats / search position | API returns `boosterStats[]` | Useful data discarded |
| Bid mutations require file input | `src/wb/cli/bid.py:172` | Agent must write temp files |

### LOW

| Issue | Location | Impact |
|-------|----------|--------|
| No rate-limit-aware batching | `src/wb/client/http.py` | Fullstats is 3 calls/min |
| DI patterns simplistic | `src/wb/services/_factory.py` | Re-reads config every call |

---

## Phased Improvement Roadmap

### F-3 — Agent-Critical Fixes (v0.9.0)

**Theme:** Make the CLI reliably usable by AI agents without workarounds.

| Task | Files | Description |
|------|-------|-------------|
| Structured JSON errors | `exceptions.py`, `output.py`, `app.py` | Add `error_code` to exceptions, emit JSON errors when `--json` is active |
| No interactive prompts | `auth.py`, `bid.py`, `budget.py` | Remove `prompt=True`, add `--yes` flag, auto-skip confirms in JSON mode |
| Campaign NM IDs | `models.py`, `campaign.py` | Add `nm_ids: list[int]` to Campaign, parse from `nm_settings[]` |
| Per-NM stats breakdown | `models.py`, `stats.py` | Add `NmStats`/`DayStats`, parse `days[].apps[].nms[]` from fullstats |
| Exit code consistency | All CLI files | Replace hardcoded integers with `ExitCode` enum |
| Shared CLI helpers | `_helpers.py` (new) | Extract `_get_renderer`, `_get_profile`, `_confirm_or_abort` |

---

### I-1 — Batch Operations (v0.14.0)

**Theme:** Make every operation batch-aware; eliminate N+1 patterns.

| Task | Files | Description |
|------|-------|-------------|
| Batch item bids | `promotion.py`, `bids.py` | Add `set_item_bids(list)`, single PATCH call |
| Multi-campaign actions | `campaign.py`, `campaigns.py` | `--ids 1,2,3` for start/pause/stop/delete |
| Inline bid mutations | `bid.py` | `--bids '[{"nm_id":123,"cpm":450}]'` (no file needed) |
| Centralize batch limits | `constants.py`, `batching.py` (new) | `chunk()` generator, limits in constants |
| Auto-chunking | `analytics.py` | Split large NM lists into API-sized chunks |
| Field selection | `app.py`, `output.py` | `--fields spend,orders,views` global flag |

---

### I-2 — Per-Product Cost Tracking (v0.15.0)

**Theme:** Answer the #1 agent question: "how much did we spend on ads for product X?"

| Task | Files | Description |
|------|-------|-------------|
| `stats product-spend` | `models.py`, `stats.py`, CLI | New command: per-NM ad spend across all campaigns |
| Booster stats | `models.py`, `stats.py` | Parse `boosterStats[]` (avg_position per NM) |
| Cache auto-populate | `stats.py`, `campaigns.py` | Write-through to SQLite cache on API calls |

---

### I-3 — Composite Commands (v1.0.0)

**Theme:** High-level commands that reduce agent round-trips. The 1.0 release.

| Task | Files | Description |
|------|-------|-------------|
| `product summary` | `product.py` (new), `product_service.py` (new) | Sales + ad spend + clusters + bids in one call |
| `campaign overview` | `campaign.py` | Details + budget + stats + per-NM + clusters |
| Idempotent mutations | `models.py`, `campaigns.py` | `already_applied: bool` on MutationResult |
| SDK parity | `sdk.py` | Every CLI command has a Python SDK function |

---

### I-4 — Rate Limiting & Resilience (v0.17.0) ✅ DONE 2026-04-07

**Theme:** Production-grade reliability for long-running agent sessions.

| Task | Files | Status | Description |
|------|-------|--------|-------------|
| Rate-limit-aware batching | `rate_limits.py` (new), `rate_limiter.py` (new), `http.py` | ✅ | `RateLimiter` sliding-window class; 30-entry swagger-sourced endpoint→limit map; `path_limiters` injected into `WbHttpClient` |
| Documentation | `RATE_LIMITS.md` (new) | ✅ | Agent-optimized reference: CLI command → endpoint → limit → source; burst/spacing guidance |
| Auto-pagination | `batching.py`, `prices.py` | ✅ | `paginate_all(fetch, page_size)` helper; `PricesService` refactored to use it |
| Service container | `_factory.py` | ✅ | `_Container` / `ServiceContainer` caches `Settings` + HTTP clients per process |

---

### I-5 — Polish & Ergonomics (v1.2.0)

**Theme:** Quality-of-life improvements that compound agent efficiency.

| Task | Files | Description |
|------|-------|-------------|
| Compact JSON | `app.py` | `--compact` flag: single-line JSON output |
| Cache auto-query | Services | Check cache first (with TTL), fall back to API |
| Agent documentation | `AGENT.md` (new) | Command reference, response format, workflows |

---

### Phase 8C — Report Caching & Multi-Seller Storage (v0.12.0)

**Theme:** Eliminate repeated 30–120 s API round-trips for report commands and
give each seller account its own isolated storage namespace.

#### Key design invariant

`WB_API_TOKEN` is unique per seller — only the owner can generate it.
Therefore **Profile → Seller is a 1:1 mapping** and the profile name is the
correct isolation key. No extra `seller_id` routing is required.
`seller_id` appears only as optional metadata (display, audit).

#### Storage layout (Option D — Hybrid)

```
~/.wb-cli/
  profiles.json
  cache.db                                    ← shared SQLite; report_cache table
  <profile_name>/
    reports/
      warehouse_remains_YYYY-MM-DD.json       # raw API download, TTL-guarded
      sales_<N>d_YYYY-MM-DD.json              # raw sales window, TTL-guarded
```

Raw report files are human-inspectable, easy to backup, and scoped per seller.
The SQLite `report_cache` table stores metadata (`profile_name`, `seller_id`,
`report_type`, `date`, `payload_path`, `computed_at`) so agents can query
"show all sellers with critical runway today" without re-reading every file.

#### Tasks

| Task | Files | Description |
|------|-------|-------------|
| `seller_id` in profile (optional) | `auth/profiles.py` | Add optional `seller_id: str \| None` field — metadata only, never a routing key |
| `reports_dir(profile_name)` | `core/config.py` | New `Settings` method returning `config_dir / profile_name / "reports"`, creates dir on first call |
| Cache constants | `core/constants.py` | `REPORT_CACHE_TTL_HOURS = 6`, `REPORTS_DIR_NAME = 'reports'` |
| `report_cache` table | `storage/cache.py` | New table: `(profile_name, seller_id, report_type, date, payload_path, computed_at)` |
| File-cache read/write | `services/reports.py` | Before API call: check for same-day file ≤ TTL; after download: write JSON to `reports_dir` |
| `--cache/--no-cache` flag | `cli/report.py` | Default `--cache`; `--no-cache` forces fresh API call; show `[cached]` label in non-JSON output |
| Factory wiring | `services/_factory.py` | Pass `reports_dir` from `Settings` into `ReportsService` and `StatisticsClient` wrappers |
| Tests | `tests/unit/` | `test_report_cache.py` — TTL logic, miss/hit, multi-profile isolation |

---

### Phase 8D — Prices & Discounts Command (v0.13.0)

**Theme:** First-class `wb prices` command so agents always get base price, seller discount %,
and final buyer-facing price in one call — no raw HTTP workarounds needed.

Discovered during a live agent session (2026-04-05) where `wb portal products` only returned
the base price (1,190 ₽) and the agent had to bypass the CLI to call
`discounts-prices-api.wildberries.ru` directly.

| Task | Files | Description |
|------|-------|-------------|
| Constants | `core/constants.py` | `PRICES_BASE_URL`, `EP_PRICES_GOODS_FILTER` |
| Domain models | `domain/models.py` | `ProductPriceSize`, `ProductPrice` with `base_price`, `final_price`, `club_price` properties |
| HTTP client | `client/prices.py` | `PricesClient.list_goods(limit, offset, filter_nm_id)` |
| Service | `services/prices.py` | `PricesService.get_prices()` with auto-pagination + client-side filter |
| Factory | `services/_factory.py` | `create_prices_service()` via promotion token |
| CLI | `cli/prices.py` | `wb prices list --nm-ids --min-discount --json` |
| App | `cli/app.py` | Register `prices_app` after `portal_app` |
| Tests | `tests/unit/` | `test_prices_client.py` (8 tests), `test_prices_service.py` (20 tests) |

**Output format** (`wb prices list --nm-ids 227403075,100510938,100525085`):
```
┌───────────────┬─────────────┬────────────┬──────────┬─────────────┬──────────┐
│        NM ID  │ Vendor Code │ Base Price │ Discount │ Final Price │ Currency │
├───────────────┼─────────────┼────────────┼──────────┼─────────────┼──────────┤
│     100510938 │ 00-0002064  │  1,190 ₽   │   -27%   │     869 ₽   │   RUB    │
│     100525085 │ 00-0002261  │  1,490 ₽   │   -28%   │   1,073 ₽   │   RUB    │
│     227403075 │ 28447       │  1,190 ₽   │   -27%   │     869 ₽   │   RUB    │
└───────────────┴─────────────┴────────────┴──────────┴─────────────┴──────────┘
```
Club Price column appears automatically when any product has a WB Club discount.

**Future:** `--enrich` flag to cross-reference titles from the portal (requires separate
portal credentials; omitted in v0.13.0 to keep the command API-token-only).

---

## Version Scheme

Phase naming: `N` = core phase · `NA` = sub-phase of N · `F-N` = fix · `I-N` = improvement

| Version | Phase | Milestone |
|---------|-------|-----------|
| 0.9.0 | F-3 | Agent-critical fixes — JSON errors, per-NM stats |
| 0.10.0 | 8A | Warehouse inventory reports |
| 0.11.0 | 8B | Stock runway (days-until-stockout) |
| 0.12.0 | 8C | Report caching & multi-seller storage |
| 0.13.0 | 8D | Prices & Discounts command |
| 0.14.0 | I-1 | Batch operations — multi-ID, auto-chunking, --fields |
| 0.15.0 | I-2 | Per-product cost tracking — product-spend, booster stats |
| 1.0.0 | I-3 | Composite commands (stable release) |
| 1.1.0 | I-4 | Rate limiting & resilience |
| 1.2.0 | I-5 | Polish & agent ergonomics |
