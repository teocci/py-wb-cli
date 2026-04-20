# WB CLI - Implementation Progress

## 🚀 Quick Status Dashboard (for AI Agents)

| Metric | Value | Status |
|--------|-------|--------|
| **Current Version** | 0.23.0 | ✅ Latest |
| **Phases Complete** | 20/20 | 100% |
| **Tests Passing** | 990/991 | ✅ 99.9% |
| **API Fixes** | 10/10 | ✅ Complete |
| **Commands** | 22+ | ✅ Ready |
| **Core Files** | 55+ | ✅ Stable |
| **Latest Feature** | I-10 — sales-funnel products: --min-orders filter + --all auto-pagination | ✅ 2026-04-21 |
| **Agent-Ready** | YES | ✅ JSON mode, --compact, --sort-by/--top N, composite reads, idempotent mutations, --fields filtering, preemptive rate limiting |

### Command Groups Available

| Group | Commands | Status | Example |
|-------|----------|--------|---------|
| `auth` | login, logout, list, use, status, ping, categories, login-portal, generate-token | ✅ Ready | `wb auth login --token <JWT>` |
| `campaign` | list, get, create, clone, start, pause, stop, rename, delete | ✅ Ready | `wb campaign list --json` |
| `bid` | set, get, min | ✅ Ready | `wb bid set --nm 12345 --cpm 450` |
| `budget` | get, deposit | ✅ Ready | `wb budget get` |
| `stats` | campaign, campaigns, product-spend | ✅ Ready | `wb stats product-spend --nms 100525085 --from 2026-04-01 --to 2026-04-06` |
| `cluster` | list, get-bids, set-bids, get-minus, set-minus, stats | ✅ Ready | `wb cluster list --nm 12345` |
| `portal` | products | ✅ Ready | `wb portal products --limit 100` |
| `prices` | list | ✅ Ready | `wb prices list --nm-ids 227403075,100510938` |
| `analytics` | sales-funnel, search-report, csv | ✅ Ready | `wb analytics sales-funnel products --from 2026-04-01 --sort-by orders --top 10` |
| `optimize` | recommend, apply | ✅ Ready | `wb optimize recommend --dry-run` |
| `report` | warehouse, cache | ✅ Ready | `wb report warehouse stock-runway` |
| `product` | summary | ✅ Ready | `wb product summary --nms 100525085,227403075 --json` |
| `assess` | snapshot | ✅ Ready | `wb assess --json --compact` |
| `pulse` | intraday | ✅ Ready | `wb pulse --campaigns 123 --json --compact` |

---

## Version History

| Version | Phase | Date | Description |
|---------|-------|------|-------------|
| 0.1.0 | 0 | 2026-03-18 | Foundation - CLI scaffold, config, auth, HTTP client, audit |
| 0.2.0 | 1 | 2026-03-18 | Read-only visibility - campaigns, budgets, bids, stats, clusters |
| 0.3.0 | 2 | 2026-03-18 | Core write controls - lifecycle, items, bids, budget, placements |
| 0.3.1 | F-1 | 2026-03-19 | Dual auth - portal session support, env var fallback, /ping fix |
| 0.3.2 | F-2 | 2026-04-02 | Full API migration - all dead endpoints replaced with current WB API |
| 0.4.0 | 3 | 2026-04-02 | Search-cluster control - cluster bid mutations, minus phrases, daily stats |
| 0.5.0 | 4 | 2026-04-03 | Analytics bridge - sales funnel, search reports, CSV exports |
| 0.6.0 | 5 | 2026-04-03 | Optimization workflows - recommendation engine, guarded apply |
| 0.8.0 | 7 | 2026-04-03 | Local SQLite cache - historical snapshots, wb budget history |
| 0.9.0 | F-3 | 2026-04-03 | Agent-critical fixes - JSON errors, per-NM stats, Campaign nm_ids |
| 0.10.0 | 8A | 2026-04-04 | Warehouse inventory reports — async report lifecycle + top products |
| 0.11.0 | 8B | 2026-04-04 | Stock runway — days-until-stockout via Statistics API sales velocity |
| 0.12.0 | 8C | 2026-04-04 | Report caching & multi-seller storage — 6h TTL file cache + SQLite metadata |
| 0.13.0 | 8D | 2026-04-06 | Prices & Discounts command — base price, discount %, final buyer price via discounts-prices-api |
| 0.14.0 | I-1 | 2026-04-06 | Batch operations — N+1 elimination, --ids multi-campaign, --bids inline JSON, auto-chunk analytics, --fields output filtering |
| 0.15.0 | I-2 | 2026-04-06 | Per-product cost tracking — wb stats product-spend, booster avg_position, fullstats auto-chunking, stats cache write-through |
| 0.16.0 | I-3 | 2026-04-06 | Composite commands — wb product summary, wb campaign overview, idempotent mutations, SDK parity (rename, delete, stats, prices) |
| 0.17.0 | I-4 | 2026-04-07 | Rate limiting & resilience — RateLimiter (sliding window), RATE_LIMITS.md, paginate_all helper, _Container service cache, swagger-sourced limits |
| 0.18.0 | I-5 | 2026-04-07 | Polish & agent ergonomics — --compact single-line JSON, --sort-by/--top N on funnel products, AGENT.md command reference |
| 0.19.0 | I-6 | 2026-04-08 | Full token category support — 11 categories, --category all, wb auth categories command |
| 0.20.0 | I-7 | 2026-04-17 | Agent skills — wb assess/pulse native commands + 7 Claude Code skills (wb-launch, wb-optimize, wb-manage, wb-keywords, wb-calibrate) |
| 0.20.2 | F-4 | 2026-04-17 | UTF-8 pipe fix — sys.stdout.reconfigure at startup + centralized _stdout_console across all CLI modules |
| 0.20.3 | F-5 | 2026-04-19 | Budget unit fix (rubles not kopecks) + unified bid_type omits placement_types |
| 0.20.4 | F-6 | 2026-04-19 | TTY-aware ANSI output — force_terminal=sys.stdout.isatty(); plain text when piped |
| 0.20.5 | F-7 | 2026-04-19 | campaign list --fields projection — route through renderer.display(); column/key filtering now honored |
| 0.20.6 | F-8 | 2026-04-20 | Empty PaymentType crash fix — guard null payment_type in campaign list |
| 0.21.0 | I-8 | 2026-04-21 | stats campaigns --status filter — running/paused/active virtual alias, get_stats_by_status() service method |
| 0.22.0 | I-9 | 2026-04-21 | stats daily-report — per-product ad spend + total platform orders joined from Analytics funnel; wb-daily-report skill |
| 0.23.0 | I-10 | 2026-04-21 | sales-funnel products: --min-orders filter + --all auto-pagination (paginate_all, page_size=1000) |

## Current Version: 0.22.0

## Phase Status

| Phase | Name | Status | Version |
|-------|------|--------|---------|
| 0 | Foundation | COMPLETED | 0.1.0 |
| 1 | Read-only operational visibility | COMPLETED | 0.2.0 |
| 2 | Core write controls | COMPLETED | 0.3.0 |
| F-1 | Auth fix — dual auth, portal session, env var fallback | COMPLETED | 0.3.1 |
| F-2 | API fix — full endpoint migration to current WB API | COMPLETED | 0.3.2 |
| 3 | Search-cluster control | COMPLETED | 0.4.0 |
| 4 | Analytics bridge | COMPLETED | 0.5.0 |
| 5 | Optimization workflows | COMPLETED | 0.6.0 |
| 6 | Agent platform support | COMPLETED | 0.7.0 |
| 7 | Local SQLite cache + historical snapshots | COMPLETED | 0.8.0 |
| F-3 | Agent-critical fixes — JSON errors, per-NM stats, nm_ids | COMPLETED | 0.9.0 |
| 8A | Warehouse inventory reports | COMPLETED | 0.10.0 |
| 8B | Stock runway (days-until-stockout) | COMPLETED | 0.11.0 |
| 8C | Report caching & multi-seller storage | COMPLETED | 0.12.0 |
| 8D | Prices & Discounts command | COMPLETED | 0.13.0 |
| I-1 | Batch operations — multi-ID, auto-chunking, --fields | COMPLETED | 0.14.0 |
| I-2 | Per-product cost tracking — product-spend, booster stats | COMPLETED | 0.15.0 |
| I-3 | Composite commands — product summary (1 call = all data) | COMPLETED | 0.16.0 |
| I-4 | Rate limiting & resilience — RateLimiter, auto-pagination | COMPLETED | 0.17.0 |
| I-5 | Polish & ergonomics — --compact, --sort-by/--top N, AGENT.md | COMPLETED | 0.18.0 |
| I-6 | Full token category support — 11 categories, --category all, wb auth categories | COMPLETED | 0.19.0 |
| I-7 | Agent skills — wb assess/pulse native commands + 7 Claude Code skills | COMPLETED | 0.20.0 |
| F-4 | UTF-8 pipe fix — stdout reconfigure + centralized console | COMPLETED | 0.20.2 |
| F-5 | Budget unit fix (rubles) + unified bid_type omits placement_types | COMPLETED | 0.20.3 |
| F-6 | TTY-aware ANSI output — no escape codes when piped | COMPLETED | 0.20.4 |
| F-7 | campaign list --fields projection fix | COMPLETED | 0.20.5 |
| F-8 | Empty PaymentType crash fix | COMPLETED | 0.20.6 |
| I-8 | stats campaigns --status filter (running / paused / active) | COMPLETED | 0.21.0 |
| I-9 | stats daily-report — ad spend + total orders joined; wb-daily-report skill | COMPLETED | 0.22.0 |
| I-10 | sales-funnel products: --min-orders filter + --all auto-pagination | COMPLETED | 0.23.0 |

---

## Phase 0 - Foundation (v0.1.0) - COMPLETED

### What was built

- **Project scaffolding**: pyproject.toml, src/wb package structure, pytest config
- **Core constants**: API URLs, exit codes (IntEnum), default values
- **Exception hierarchy**: WbCliError base, ValidationError, AuthenticationError, RateLimitError, ApiError, ConfigError - each with proper exit codes
- **Domain enums**: CampaignStatus, CampaignType, PaymentType, PlacementType, BidType, OutputFormat, VerbosityLevel
- **Domain models**: Campaign, ProductCard, ItemBid, SearchCluster, ClusterBid, BudgetSnapshot, CampaignStats, ClusterStats, MinusPhraseSet, OptimizationDecision
- **Config system**: Pydantic BaseSettings with env var support (WB_ prefix), config dir management
- **Output rendering**: JSON/table/quiet output via Rich, OutputRenderer class
- **HTTP client**: httpx-based with exponential backoff, jitter, rate-limit header parsing, retry logic for 429/5xx
- **Auth/profiles**: Multi-profile token storage (JSON file), per-category tokens (promotion/analytics), profile CRUD
- **Token validation**: Lightweight WB API ping for promotion tokens
- **Audit logging**: Append-only JSONL audit trail for mutating operations
- **CLI layer**: Typer-based with global options (--verbose, --quiet, --json, --profile)
- **Auth commands**: login, logout, list, use, status, ping, categories, login-portal, generate-token

### Test results

- **149 tests passed** (0 failures)

---

## Phase 1 - Read-only Operational Visibility (v0.2.0) - COMPLETED

### What was built

- **Endpoint constants**: 10 Promotion API path constants in `constants.py`
- **Domain model updates**: `from_api()` class methods on ProductCard, ItemBid, SearchCluster, BudgetSnapshot, CampaignStats, ClusterStats
- **New domain models**: AccountBalance (balance/net/bonus), RecommendedBid (campaign_id/nm_id/recommended/minimum)
- **Promotion API client** (`client/promotion.py`): Typed wrapper around WbHttpClient with 11 read methods — list_campaigns, get_campaign, get_eligible_subjects, get_eligible_items, get_balance, get_budget, get_campaign_stats, get_recommended_bids, get_active_clusters, get_all_clusters, get_cluster_stats
- **Service layer**: 5 service classes + factory module
  - `CampaignService` — list/get campaigns, eligible subjects/items
  - `BudgetService` — account balance, campaign budget
  - `StatsService` — campaign stats (single/multi), cluster stats with date validation
  - `ClusterService` — list/active/inactive/bids clusters
  - `BidService` — recommended/minimum/item bids
  - `_factory.py` — create_*_service() helpers for CLI integration
- **CLI commands**: 5 new command groups (16 commands total)
  - `wb campaign list|get|eligible-subjects|eligible-items`
  - `wb bid recommend|minimum|get-items`
  - `wb budget balance|get`
  - `wb stats campaign|campaigns`
  - `wb cluster list|active|inactive|bids|stats`
- All commands support `--json` for machine-readable output

### File structure

```
src/wb/
  __init__.py              # __version__ = '0.2.0'
  __main__.py              # python -m wb entry point
  cli/
    app.py                 # Main Typer app + 6 sub-app registrations
    auth.py                # Auth subcommands
    campaign.py            # Campaign list/get/eligible commands
    bid.py                 # Bid recommend/minimum/get-items commands
    budget.py              # Budget balance/get commands
    stats.py               # Stats campaign/campaigns commands
    cluster.py             # Cluster list/active/inactive/bids/stats commands
  core/
    constants.py           # URLs, exit codes, defaults, endpoint paths
    exceptions.py          # Exception hierarchy
    config.py              # Settings (pydantic-settings)
    output.py              # Output rendering (Rich tables, JSON, quiet)
  domain/
    enums.py               # CampaignStatus, PaymentType, OutputFormat, etc.
    models.py              # All domain models with from_api() methods
  auth/
    profiles.py            # Profile and ProfileStore classes
    token_validation.py    # Token validation via WB API
  client/
    http.py                # WbHttpClient with retries and rate limiting
    promotion.py           # PromotionClient (typed Promotion API wrapper)
  services/
    _factory.py            # Service factory helpers
    campaigns.py           # CampaignService
    budgets.py             # BudgetService
    stats.py               # StatsService
    clusters.py            # ClusterService
    bids.py                # BidService
  storage/
    audit.py               # AuditLogger, AuditEntry (JSONL)
```

### Test results

- **249 tests passed** (0 failures)
- 100 new tests covering: domain model from_api(), promotion client, all 5 services, all CLI commands
- Test coverage areas: models, promotion client (mock HTTP), services (mock client), CLI commands (mock services, CliRunner)

---

## Phase 2 - Core Write Controls (v0.3.0) - COMPLETED

### What was built

- **WbHttpClient.delete()**: HTTP DELETE method added to base HTTP client
- **New endpoint constants**: 9 write-path constants (start, pause, stop, rename, create, items, placements, budget deposit, bid set)
- **New domain models**: `MutationResult` (dry-run aware result), `CampaignCreate` (campaign params + `to_api()`), `BidMutation` (CPM bid + `to_api()`), `PlacementConfig` (search/catalog flags + `to_api()`)
- **PromotionClient write methods**: `start_campaign`, `pause_campaign`, `stop_campaign`, `rename_campaign`, `delete_campaign`, `create_campaign`, `add_items`, `remove_items`, `set_placements`, `deposit_budget`, `set_item_bid`
- **CampaignService write methods**: `create_campaign`, `start_campaign`, `pause_campaign`, `stop_campaign`, `rename_campaign`, `delete_campaign`, `add_items`, `remove_items`, `set_placements` — all with `dry_run` support
- **BudgetService.topup()**: Deposits funds, validates positive amount, dry-run support
- **BidService write methods**: `set_item_bid`, `set_item_bids` — validates CPM > 0, dry-run support
- **Factory**: `create_audit_logger()` helper added
- **CLI commands** (all with `--dry-run` and `--yes`, audit logging on execute):
  - `wb campaign create --name --daily-budget --nms [--type] [--subject]`
  - `wb campaign start <id>`
  - `wb campaign pause <id>`
  - `wb campaign stop <id>`
  - `wb campaign rename <id> --name`
  - `wb campaign delete <id>`
  - `wb campaign add-items <id> --nms`
  - `wb campaign remove-items <id> --nms`
  - `wb campaign set-placements <id> [--search/--no-search] [--catalog/--no-catalog]`
  - `wb bid set-item --campaign --nm --cpm [--subject]`
  - `wb bid set-items --campaign --file bids.json`
  - `wb budget topup --campaign --sum`
- **OutputRenderer.is_json** property added (used to auto-skip confirmation prompts in JSON mode)

### File structure additions

```
src/wb/
  cli/
    campaign.py      # +9 write commands, _confirm_or_abort, _log_mutation helpers
    bid.py           # +set-item, set-items commands
    budget.py        # +topup command
  client/
    http.py          # +delete() method
    promotion.py     # +11 write methods
  core/
    constants.py     # +9 write endpoint constants
    output.py        # +is_json property on OutputRenderer
  domain/
    models.py        # +MutationResult, CampaignCreate, BidMutation, PlacementConfig
  services/
    _factory.py      # +create_audit_logger()
    campaigns.py     # +9 write methods
    budgets.py       # +topup()
    bids.py          # +set_item_bid(), set_item_bids()
tests/unit/
  test_promotion_client_write.py  # 14 tests
  test_service_write.py           # 37 tests
  test_cli_write.py               # 26 tests
```

### Test results

- **326 tests passed** (0 failures)
- 77 new tests covering: PromotionClient write methods, service write methods, domain models, CLI write commands, dry-run paths, validation errors

---

## Auth Enhancement (v0.3.1) - COMPLETED

### What was built

- **Portal constants**: Seller portal base URLs, auth headers (`authorizev3`, `wb-seller-lk`), JRPC endpoint paths
- **Env var support**: `WB_API_TOKEN`, `WB_USER_ID`, `WB_TOKEN_EXPIRATION` via `.env` / environment
- **Portal session storage**: `portal_session` field on Profile dataclass with `get/set/has_portal_session()` methods, backward-compatible serialization
- **Token validation fix**: Changed ping path from `/adv/v1/promotion/count` to official `/ping` endpoint
- **Portal HTTP client** (`client/portal.py`): `PortalClient` with two-step JRPC auth chain — `authenticate()` → `generate_token()`
- **Unified auth priority chain**: CLI flags > env vars > .env > profiles.json — applies to both API tokens and portal credentials
- **Factory updates**: `create_portal_client()` and `_get_promotion_token()` both follow the unified priority chain
- **CLI commands**:
  - `wb auth login-portal --authorizev3 <key> [--cookie <str>]` — authenticate with seller portal
  - `wb auth generate-token` — generate API token via portal JRPC
  - `wb auth status` — now shows portal session info

### File structure additions

```
src/wb/
  client/
    portal.py          # PortalClient, PortalSession (JSON-RPC)
  core/
    constants.py       # +portal URLs, headers, endpoints, PING_PATH
    config.py          # +api_token, user_id, token_expiration, authorizev3, portal_cookie env vars
  auth/
    profiles.py        # +portal_session field and methods
    token_validation.py # Fixed ping path to /ping
  services/
    _factory.py        # +create_portal_client(), env var fallback
  cli/
    auth.py            # +login-portal, generate-token commands
tests/unit/
  test_portal_client.py  # 19 tests
  test_profiles.py       # +10 tests (portal_session)
```

### Portal auth discovery (2026-03-19)

Testing revealed that **cookie + authorizev3** is the real auth pair for all portal endpoints. The `wb-seller-lk` session token is NOT required. PortalClient was simplified to remove session token management.

Added:
- `wb portal products` command — lists product cards from seller portal (tableListv6)
- `PortalProductCard` domain model with `from_portal()` factory
- `list_products()` method on PortalClient
- Cookie made required (was optional) — both cookie + authorizev3 needed
- `wb_portal_authentication_notes.md` — detailed auth combo test results

### Test results

- **355 tests passed** (0 failures, 1 pre-existing env-dependent skip)
- Portal client tests cover: auth, generate_token, list_products, cookie validation, JRPC counter

---

## API Fix (v0.3.2) - COMPLETED

### What happened

Live testing on 2026-04-02 revealed that **10 of 12 endpoint paths** in the codebase return HTTP 404. WB migrated their entire Promotion API without deprecation notice. Only `/ping` and `/adv/v1/budget` survived.

### What was fixed

- **Constants**: All 14 dead `EP_*` constants replaced with current paths from `dev-wb-adv.md`
- **8 new normquery constants** added for search cluster API (`EP_NQ_LIST`, `EP_NQ_GET_BIDS`, etc.)
- **Domain models**: Campaign, AccountBalance, BudgetSnapshot, CampaignStats, SearchCluster, ClusterStats — all `from_api()` rewritten for new response shapes
- **CampaignCreate, BidMutation, PlacementConfig** — `to_api()` rewritten for new request formats
- **MinusPhraseSet** — added `from_api()` and `to_api()` methods
- **HTTP client**: Added `put()` and `patch()` methods
- **PromotionClient**: All methods rewritten — new endpoints, HTTP methods (POST→GET, GET→POST), payload shapes
- **Cluster read commands**: Migrated from dead `auto/*` API to working `normquery/*` API with required `--nm` parameter
- **ClusterService**: Complete rewrite for normquery API (list, active, inactive, bids, stats, minus phrases)
- **StatsService**: Removed dead `get_cluster_stats` (moved to ClusterService)
- **All CLI commands**: Updated for new model fields and signatures
- **CLAUDE.md**: Added API documentation rule (only use `dev-wb-adv.md`)
- **FIXES.md**: Created fix progress log

### Endpoint migration summary

| Count | Change |
|-------|--------|
| 10 | Dead paths replaced |
| 3 | HTTP method changes (POST→GET, GET→POST, DELETE→GET) |
| 8 | New normquery endpoints added |
| 2 | New HTTP methods (put, patch) in client |

### Write endpoint verification (campaign 35495276)

| Endpoint | Result |
|---|---|
| `POST /adv/v2/seacat/save-ad` | 200 — created |
| `GET /adv/v0/start` | 400 — expected (no budget) |
| `GET /adv/v0/pause` | 400 — expected (not active) |
| `POST /adv/v0/rename` | 200 — renamed |
| `GET /adv/v0/stop` | 400 — expected (not active) |
| `GET /adv/v0/delete` | 200 — deleted |

### Test results

- **366 tests passed** (0 failures)

---

## Phase 3 - Search-cluster Control (v0.4.0) - COMPLETED

### What was built

- **New domain model**: `ClusterBidMutation` (nm_id, norm_query, bid + `to_api()`) — replaces unused `ClusterBid`
- **PromotionClient write methods**: `set_cluster_bids`, `delete_cluster_bids`, `set_minus_phrases`
- **ClusterService write methods**: `set_cluster_bids`, `delete_cluster_bids`, `set_minus_phrases`, `clear_minus_phrases` — all with dry-run support and validation (max 100 bids, max 1000 phrases, positive bids)
- **ClusterService read addition**: `get_cluster_stats_daily` — daily breakdown stats via normquery v1 API
- **CLI write commands** (all with `--dry-run` and `--yes`, audit logging on execute):
  - `wb cluster set-bids --campaign --nm --query --bid` — set single cluster bid
  - `wb cluster set-bids-file --campaign --file` — batch set from JSON file
  - `wb cluster delete-bids --campaign --nm --query --bid` — delete single cluster bid
  - `wb cluster delete-bids-file --campaign --file` — batch delete from JSON file
  - `wb cluster stats-daily --campaign --nm --from --to` — daily stats
- **Minus phrase sub-app** (`wb cluster minus ...`):
  - `wb cluster minus list --campaign --nm` — list current minus phrases
  - `wb cluster minus set --campaign --nm --phrases` — set minus phrases (comma-separated)
  - `wb cluster minus clear --campaign --nm` — clear all minus phrases

### File structure additions

```
src/wb/
  domain/
    models.py        # +ClusterBidMutation, -ClusterBid (replaced)
  client/
    promotion.py     # +set_cluster_bids, delete_cluster_bids, set_minus_phrases
  services/
    clusters.py      # +5 methods (set/delete bids, set/clear minus, stats-daily)
  cli/
    cluster.py       # +8 commands, minus_app sub-app, _confirm_or_abort, _log_mutation
tests/unit/
  test_promotion_client_write.py  # +5 tests
  test_cluster_service.py         # +20 tests
  test_cli_cluster.py             # +14 tests
```

### Test results

- **405 tests passed** (0 failures)
- 39 new tests covering: client write methods, service write methods (dry-run, execute, validation), CLI write commands, minus phrase commands, daily stats

---

## Phase 4 - Analytics Bridge (v0.5.0) - COMPLETED

### What was built

- **New `AnalyticsClient`** (`client/analytics.py`): Typed wrapper for Analytics API with 12 methods — 3 sales funnel, 5 search report, 4 CSV report operations
- **New domain models** (`domain/analytics_models.py`): 7 dataclasses (`ProductFunnelStats`, `FunnelHistoryDay`, `ProductFunnelHistory`, `SearchReportProduct`, `SearchReportGroup`, `SearchTextEntry`, `CsvReportStatus`) + 2 enums (`ReportType`, `AggregationLevel`)
- **New `AnalyticsService`** (`services/analytics.py`): 12 service methods with validation (nm_ids 1-20 for history, limit max 1000), UUID generation for CSV tasks, file download
- **WbHttpClient.request_raw()**: Binary download method for ZIP files; refactored `_handle_response` to use shared `_check_error_status`
- **Analytics token support**: `WB_ANALYTICS_TOKEN` env var, `_get_analytics_token()` priority chain, `create_analytics_client/service` factories
- **12 CLI commands** across 3 nested sub-apps:
  - `wb analytics sales-funnel products|history|grouped`
  - `wb analytics search-report main|groups|details|search-texts|orders`
  - `wb analytics csv create|list|retry|download`
- All endpoints use separate Analytics token (bit 2), base URL `seller-analytics-api.wildberries.ru`

### File structure additions

```
src/wb/
  domain/
    analytics_models.py   # NEW: 7 dataclasses + 2 enums
  client/
    analytics.py          # NEW: AnalyticsClient (12 methods)
    http.py               # +request_raw(), +_check_error_status()
  services/
    analytics.py          # NEW: AnalyticsService (12 methods)
    _factory.py           # +_get_analytics_token, create_analytics_client/service
  cli/
    analytics.py          # NEW: 12 commands, 3 sub-apps
    app.py                # +analytics_app registration
  core/
    constants.py          # +12 analytics endpoint constants
    config.py             # +analytics_token env var
tests/unit/
  test_analytics_models.py    # 20 tests
  test_analytics_client.py    # 22 tests
  test_analytics_service.py   # 19 tests
  test_cli_analytics.py       # 12 tests
```

### API endpoints integrated

| Endpoint | Method | Purpose | Rate Limit |
|----------|--------|---------|------------|
| `/api/analytics/v3/sales-funnel/products` | POST | Product stats per period | 3/min |
| `/api/analytics/v3/sales-funnel/products/history` | POST | Product stats per days | 3/min |
| `/api/analytics/v3/sales-funnel/grouped/history` | POST | Grouped stats per days | 3/min |
| `/api/v2/search-report/report` | POST | Main search report | 3/min |
| `/api/v2/search-report/table/groups` | POST | Groups pagination | 3/min |
| `/api/v2/search-report/table/details` | POST | Product details | 3/min |
| `/api/v2/search-report/product/search-texts` | POST | Top search texts | 3/min |
| `/api/v2/search-report/product/orders` | POST | Orders by texts | 3/min |
| `/api/v2/nm-report/downloads` | POST | Create CSV report | 3/min |
| `/api/v2/nm-report/downloads` | GET | List reports | 3/min |
| `/api/v2/nm-report/downloads/retry` | POST | Retry failed report | 3/min |
| `/api/v2/nm-report/downloads/file/{id}` | GET | Download ZIP | 3/min |

### Test results

- **474 tests passed** (0 failures)
- 69 new tests covering: domain models, analytics client, analytics service, CLI commands

---

## Phase 5 - Optimization Workflows (v0.6.0) - COMPLETED

### What was built

- **4 new domain enums**: `OptimizationAction` (10 action types), `TargetType` (campaign/item/cluster), `ClusterClass` (5 classifications), `ProductRole` (hero/support/experimental)
- **Updated `OptimizationDecision`**: Now uses typed enums for action/target_type, added `nm_id` field for scoped decisions
- **`OptimizerService`** (`services/optimizer.py`): Recommendation-first rule engine with:
  - 5 plan methods: `plan_all`, `plan_clusters`, `plan_budget`, `plan_negatives`, `plan_portfolio`
  - 5 apply methods: `apply_all`, `apply_clusters`, `apply_budget`, `apply_negatives` + `_apply_decision` router
  - Cluster classification: efficient, visible_weak, expensive_non_converting, inactive_promising, noisy_exclusion
  - Configurable thresholds: MIN_VIEWS, LOW_CTR, HIGH_CTR, WASTE_SPEND, BUDGET_ALERT, BID_RAISE/LOWER factors
  - Explainable `reason` strings on every decision with data context
  - Confidence scoring based on view count sufficiency
- **6 CLI commands** (all with `--json` support):
  - `wb optimize plan` — full plan (read-only, no --apply)
  - `wb optimize run` — plan + optional `--apply` execution
  - `wb optimize clusters` — cluster bid optimization with `--apply`
  - `wb optimize budget` — budget exhaustion detection with `--apply`
  - `wb optimize negatives` — minus phrase recommendations with `--apply`
  - `wb optimize portfolio` — product mix analysis with `--apply`
- **Guarded execution**: `--apply` flag required for mutations, `--yes` to skip confirmation, `--dry-run` supported
- **Apply routing**: `match/case` on `OptimizationAction` dispatches to correct service (cluster, budget, campaign)

### V1 heuristic rules

| Rule | Signal | Action |
|------|--------|--------|
| Efficient cluster | High CTR + orders | `raise_cluster_bid` (+20%) |
| Visible weak | High views, low CTR | `lower_cluster_bid` (-20%) |
| Wasteful cluster | Spend > 500, 0 orders | `delete_cluster_bid` |
| Noisy cluster | Low CTR + wasteful | `add_minus_phrase` |
| Budget at risk | >85% budget used | `topup_budget` |
| No conversion | Clicks but 0 orders | `pause_campaign` |

### File structure additions

```
src/wb/
  domain/
    enums.py           # +4 enums (OptimizationAction, TargetType, ClusterClass, ProductRole)
    models.py          # Updated OptimizationDecision (enum fields + nm_id)
  services/
    optimizer.py       # NEW: OptimizerService + rule engine
    _factory.py        # +create_optimizer_service with 5 sub-service injection
  cli/
    optimize.py        # NEW: 6 commands
    app.py             # +optimize_app registration
tests/unit/
  test_optimizer_service.py  # 25 tests
  test_cli_optimize.py       # 12 tests
```

### Test results

- **511 tests passed** (0 failures)
- 37 new tests covering: rule engine (each rule fires/skips), cluster classification, apply routing, CLI commands, explainability

---

## Phase 6 - Agent Platform Support (v0.7.0) - COMPLETED

### What was built

- **Python SDK facade** (`src/wb/sdk.py`): ~50 importable functions that wrap service-layer factories, exposing a typed Python API for agents
  - Campaign operations: `list_campaigns`, `get_campaign`, `create_campaign`, `clone_campaign`, `start_campaign`, `pause_campaign`, `stop_campaign`
  - Budget operations: `get_balance`, `get_budget`, `topup_budget`
  - Bid operations: `get_recommended_bids`, `set_item_bid`
  - Cluster operations: `list_clusters`, `set_cluster_bids`, `set_minus_phrases`
  - Optimizer operations: `plan_clusters`, `plan_budget`, `plan_negatives`, `plan_all`, `apply_clusters`, `apply_all`
  - All functions accept optional `profile` parameter, return typed domain objects (no exit codes, no output rendering)
- **`wb campaign clone` command** (`cli/campaign.py`): Clone existing campaign with optional name override and explicit `--nms` list (required because WB API does not return current items in campaign info)
  - Defaults new name to `"{original_name} (copy)"`
  - Reuses `bid_type` from source
  - Full dry-run and confirmation support
- **Optimizer logic fix** (`services/optimizer.py`): Fixed unreachable `NOISY_EXCLUSION` branch by reordering conditions — more specific `(is_wasteful and low_ctr)` now checked before `(is_wasteful)` alone

### File structure additions

```
src/wb/
  sdk.py                 # NEW: ~50 SDK wrapper functions
  cli/
    campaign.py          # +clone command
  services/
    optimizer.py         # Fixed _classify_cluster condition order
tests/unit/
  test_sdk.py            # 39 tests for all SDK operations
  test_cli_campaign.py   # +4 tests for clone command
  test_optimizer_service.py  # +1 test for NOISY_EXCLUSION fix
```

### Key design decisions

- SDK is a pure function facade: no try/except wrapping, callers receive `WbCliError` subclasses directly
- Clone command requires explicit `--nms` because campaign info API does not return current items
- Optimizer fix: order conditions from specific (high signal) to general (lower signal) to ensure correct classification

### Test results

- **539 tests passed** (0 failures)
- 44 new tests: SDK wrapper testing (39 tests across campaign/budget/cluster/optimizer operations), clone command (4 tests), NOISY_EXCLUSION fix (1 test)

---

---

## Phase 7 - Local SQLite Cache + Historical Snapshots (v0.8.0) - COMPLETED

### What was built

- **`CACHE_DB_FILE` constant**: `cache.db` in config dir (alongside `audit.jsonl`)
- **`domain/cache_models.py`**: 4 `@dataclass(slots=True)` models — `CampaignSnapshot`, `StatsRecord`, `ClusterRecord`, `BudgetEvent`
- **`storage/cache.py`**: `CacheStore` — SQLite-backed store with 4 tables, schema versioning via `PRAGMA user_version`, WAL journal mode, and row mappers for all model types
  - `save_campaign` / `list_campaigns` — filter by profile, campaign_id; ordered by time desc
  - `save_stats` / `list_stats` — upsert by (campaign_id, profile, date); date range filter; ordered asc
  - `save_cluster` / `list_clusters` — filter by nm_id; ordered by time desc
  - `save_budget_event` / `list_budget_events` — filter by campaign; ordered by time desc
  - `clear(profile, campaign_id?)` — delete rows with optional campaign scope
  - `summary(profile)` — row counts per table
- **`services/cache.py`**: `CacheService` — orchestrates snapshot collection and history queries
  - `snapshot_campaign(id, profile, *, nm_id, with_stats, with_clusters)` — captures config + stats + clusters
  - `snapshot_all(profile)` — captures configs for all `RUNNING` campaigns
  - `history_campaigns / history_stats / history_clusters / history_budget` — delegate to store
  - Stats/cluster errors swallowed with warning (partial snapshot is still useful)
- **`cli/cache.py`**: 8 commands under `wb cache`:
  - `wb cache list [--campaign]` — summary or campaign snapshot list
  - `wb cache snapshot --campaign [--nm] [--no-stats] [--no-clusters]` — capture snapshot
  - `wb cache snapshot-all` — capture all active campaign configs
  - `wb cache history campaigns [--campaign]` — campaign config history
  - `wb cache history stats --campaign [--from] [--to]` — stats history
  - `wb cache history clusters --campaign [--nm]` — cluster history
  - `wb cache clear [--campaign] [--yes]` — delete cached rows
- **`cli/budget.py`**: New `wb budget history` command — queries stored budget events from cache
- **Budget event auto-capture**: `wb budget topup` now persists a `BudgetEvent` to cache after every successful deposit
- **Design question Q1 closed**: Local SQLite cache implemented as explicit-only (never hidden state)

### File structure additions

```
src/wb/
  domain/
    cache_models.py     # NEW: CampaignSnapshot, StatsRecord, ClusterRecord, BudgetEvent
  storage/
    cache.py            # NEW: CacheStore (SQLite, 4 tables, WAL mode)
  services/
    cache.py            # NEW: CacheService (snapshot + query)
    _factory.py         # +create_cache_store, create_cache_service
  cli/
    cache.py            # NEW: 8 commands, history sub-app
    budget.py           # +history command, +_record_topup_event
    app.py              # +cache_app registration
  core/
    constants.py        # +CACHE_DB_FILE
tests/unit/
  test_cache_store.py   # 29 tests — schema, round-trips, upsert, filters, limits, maintenance
  test_cache_service.py # 17 tests — snapshot logic, error handling, history queries, clear/summary
  test_cli_cache.py     # 16 tests — CLI commands, confirmation, json output
  test_cli_budget.py    # +6 tests for history and topup event recording
```

### Test results

- **604 tests passed** (0 failures)
- 65 new tests covering: SQLite schema, round-trip persistence, upsert, filters, CacheService orchestration, error swallowing, CLI commands

---

## Agent-Critical Fixes (v0.9.0) - COMPLETED

### Context

During a real agent session ("top 3 products and their ad spend"), the CLI had blockers:
- Campaign `get` dropped product NM IDs (agent bypassed CLI for raw HTTP)
- Campaign stats lost per-NM breakdown (agent manually aggregated from raw API)
- Errors were colored text, not JSON (agent couldn't parse failures)
- Interactive prompts blocked automated calls

### What was built

- **Structured JSON errors**: `error_code` field on all exception classes, `to_dict()` method, JSON error output when `--json` is active in `main()` entry point
- **No interactive prompts**: Removed `prompt=True` from auth options, added `--yes` to `auth logout`, all confirms skip in JSON mode
- **Campaign.nm_ids**: Campaign model now parses `nm_settings[]` from API response, displays in `campaign get`
- **Per-NM stats breakdown**: New `NmStats` and `DayStats` dataclasses, `CampaignStats.from_api()` parses nested `days[].apps[].nms[]` structure, aggregates per-NM totals — JSON output includes full breakdown
- **Exit code consistency**: All hardcoded `typer.Exit(code=N)` replaced with `ExitCode` enum
- **Shared CLI helpers**: New `_helpers.py` module eliminates copy-pasted `_get_renderer`, `_get_profile`, `_confirm_or_abort` from 8 CLI modules
- **IMPROVEMENTS.md**: Created comprehensive AI agent improvement roadmap (6 phases, v0.9.0-v1.2.0)

### File structure

```
src/wb/
  cli/
    _helpers.py          # NEW: shared get_renderer, get_profile, confirm_or_abort
    app.py               # JSON-aware error handler in main()
    auth.py              # Removed prompt=True, added --yes, ExitCode enum
    bid.py               # Shared helpers, ExitCode enum
    budget.py            # Shared helpers
    campaign.py          # Shared helpers, nm_ids display
    cluster.py           # Shared helpers, ExitCode enum
    stats.py             # Shared helpers
    analytics.py         # Shared helpers, ExitCode enum
    cache.py             # Shared helpers
    optimize.py          # Shared helpers
    portal.py            # ExitCode enum
  core/
    exceptions.py        # error_code field, to_dict() on all exceptions
    output.py            # JSON-aware error() method on OutputRenderer
  domain/
    models.py            # Campaign.nm_ids, NmStats, DayStats, enriched CampaignStats
IMPROVEMENTS.md          # NEW: full AI agent improvement roadmap
tests/unit/
  test_agent_improvements.py  # 31 new tests
```

### Test results

- **635 tests passed** (0 failures)
- 31 new tests covering: error codes, to_dict(), Campaign.nm_ids, NmStats, DayStats, CampaignStats per-NM aggregation, shared CLI helpers

---

## Phase 8A - Warehouse Inventory Reports (v0.10.0) - COMPLETED

### What was built

- **New endpoint constants**: `EP_WAREHOUSE_REMAINS_CREATE`, `EP_WAREHOUSE_REMAINS_STATUS`, `EP_WAREHOUSE_REMAINS_DOWNLOAD`, `EP_STOCKS_WB_WAREHOUSES`, `REPORT_POLL_INTERVAL`, `REPORT_POLL_TIMEOUT`
- **New domain models** (`domain/report_models.py`): 4 dataclasses — `WarehouseStock`, `WarehouseRemainItem`, `ReportTask`, `ProductStockSummary`
- **New `ReportsClient`** (`client/reports.py`): Typed wrapper for async report lifecycle (create → status → download) on `seller-analytics-api.wildberries.ru`
- **New `ReportsService`** (`services/reports.py`): Orchestrates 3-step report lifecycle with configurable poll loop (5s interval, 120s timeout), plus `get_warehouse_top()` convenience method for top-N product stock aggregation
- **Factory functions**: `create_reports_client`, `create_reports_service` using analytics token chain
- **4 CLI commands** under `wb report warehouse`:
  - `wb report warehouse create` — create report task with groupBy/filter options
  - `wb report warehouse status <task-id>` — check task status
  - `wb report warehouse download <task-id>` — download completed report
  - `wb report warehouse top [--limit 10]` — composite: create + poll + download + aggregate top products by stock

### API endpoints integrated

| Endpoint | Method | Server | Purpose | Rate Limit |
|----------|--------|--------|---------|------------|
| `/api/v1/warehouse_remains` | GET | seller-analytics-api | Create report task | 1/min |
| `/api/v1/warehouse_remains/tasks/{id}/status` | GET | seller-analytics-api | Check task status | 1/5s |
| `/api/v1/warehouse_remains/tasks/{id}/download` | GET | seller-analytics-api | Download report | 1/min |

### Live test results (2026-04-04)

- `wb report warehouse create --group-by-nm --json` — created task `7d9e82e7-4df0-4030-936d-0be38f269023`
- Status polled from `new` → `done` in ~8 seconds
- Downloaded 20 products with per-warehouse breakdown (Коледино, Казань, Электросталь, Краснодар, etc.)
- `wb report warehouse top --limit 10` — successfully returned top 10 products sorted by total stock (651, 537, 435, 346, 346, 290, 278, 231, 224, 171 pieces)
- Note: `groupByNm` alone returns empty brand/subject/vendor fields (WB API behavior — need additional groupBy flags for those)

### File structure additions

```
src/wb/
  domain/
    report_models.py     # NEW: WarehouseStock, WarehouseRemainItem, ReportTask, ProductStockSummary
  client/
    reports.py           # NEW: ReportsClient (3 methods)
  services/
    reports.py           # NEW: ReportsService (5 methods + poll loop)
    _factory.py          # +create_reports_client, create_reports_service
  cli/
    report.py            # NEW: 4 commands, warehouse sub-app
    app.py               # +report_app registration
  core/
    constants.py         # +6 constants (endpoints + poll defaults)
tests/unit/
  test_report_models.py  # 14 tests
  test_reports_client.py # 11 tests
  test_reports_service.py # 15 tests
  test_cli_report.py     # 10 tests
```

### Test results

- **685 tests passed** (0 failures)
- 50 new tests covering: domain models, client methods, service poll loop, top-N aggregation, CLI commands

---

## Phase 8B - Stock Runway (v0.11.0) - COMPLETED

### What was built

- `src/wb/client/statistics.py` — `StatisticsClient` wrapping `statistics-api.wildberries.ru/api/v1/supplier/sales`
- `src/wb/domain/report_models.py` — Added `SaleRecord`, `WarehouseRunway`, `StockRunwayItem`, `StockRunwayReport`
- `src/wb/services/reports.py` — Added `get_stock_runway()` method + helper functions:
  - `_build_velocity_map()` — computes avg daily sales and sale-day counts per nm_id
  - `_compute_runway_item()` — per-warehouse days-of-stock calculation
  - `_runway_alert()` — critical (≤7d) / low (≤14d) alert classification
  - `_runway_confidence()` — high/medium/low/none based on observed sale-days
  - Transit warehouse exclusion (`'В пути'`, `'Всего'` prefixes filtered out)
- `src/wb/services/_factory.py` — Added `create_statistics_client()`, `create_stock_runway_service()`
- `src/wb/core/constants.py` — Added `STATISTICS_BASE_URL`, `EP_STATISTICS_SALES`, 5 runway threshold constants
- `src/wb/cli/report.py` — Added `warehouse stock-runway` command with `--days` and `--json` options

### Tests

- `tests/unit/test_statistics_client.py` — 5 tests
- `tests/unit/test_stock_runway_models.py` — 10 tests
- `tests/unit/test_stock_runway_service.py` — 10 tests
- `tests/unit/test_cli_stock_runway.py` — 8 tests

**All 716 unit tests pass.**

### Usage

```bash
wb report warehouse stock-runway --days 30 --json
wb report warehouse stock-runway --days 14
```

---

## Phase 8C - Report Caching & Multi-Seller Storage (v0.12.0) - COMPLETED

### What was built

- **`REPORT_CACHE_TTL_HOURS = 6`** and **`REPORTS_DIR_NAME = 'reports'`** added to `constants.py`
- **`Profile.seller_id`**: Optional metadata field on Profile (no routing logic — pure display)
- **`Settings.reports_dir(profile_name)`**: Returns `~/.wb-cli/<profile_name>/reports/`, created on first call
- **`ReportCacheEntry`** dataclass in `domain/cache_models.py`: profile_name, seller_id, report_type, date, payload_path, computed_at
- **`CacheStore` schema v2**: New `report_cache` table with `UNIQUE (profile_name, report_type, date)` constraint + 3 new methods:
  - `save_report_cache(entry)` — INSERT OR REPLACE
  - `get_report_cache(profile_name, report_type, date)` — single lookup
  - `list_report_cache(profile_name, limit=50)` — ordered by computed_at desc
- **`ReportsService` constructor extended**: New `reports_dir`, `cache_store`, `profile_name` parameters
- **Cache-aware `get_warehouse_top(use_cache=True)`**: Returns `(summaries, from_cache)` tuple. Cache type: `'warehouse_remains'`
- **Cache-aware `get_stock_runway(use_cache=True)`**: Returns `(report, from_cache)` tuple. Cache types: `'warehouse_remains'` + `'sales_<N>d'`
- **`_cache_hit()`**: Validates file exists + TTL ≤ 6h; returns `(path, True)` on hit
- **`_write_cache()`**: Writes JSON to `<reports_dir>/<type>_<date>.json` + upserts metadata row
- **Cache deserialisation helpers**: `_stock_item_from_dict()`, `_sale_record_from_dict()`, `_load_stock_items()`, `_load_sale_records()` — safe round-trip from `asdict()` format
- **CLI `--cache/--no-cache` flag** on `warehouse top` and `stock-runway` commands (default `--cache`)
- **`[cached]` label** in table titles when data served from cache
- **Factory updates**: `create_reports_service()` and `create_stock_runway_service()` now wire in `reports_dir`, `cache_store`, `profile_name`; added `_resolve_profile_name()` helper

### File structure additions

```
src/wb/
  core/
    constants.py        # +REPORT_CACHE_TTL_HOURS, REPORTS_DIR_NAME
    config.py           # +reports_dir() method
  auth/
    profiles.py         # +seller_id field
  domain/
    cache_models.py     # +ReportCacheEntry
  storage/
    cache.py            # schema v2, +report_cache table, 3 new methods, _row_to_report_cache
  services/
    reports.py          # Refactored with cache: _cache_hit, _write_cache, deserialisation helpers,
                        # _api_fetch_all_stock, _get_stock_items, _get_sales, updated return types
    _factory.py         # Updated create_reports_service/create_stock_runway_service + _resolve_profile_name
  cli/
    report.py           # +use_cache flag on top/stock-runway, _render_top_table/runway accept from_cache
tests/unit/
  test_report_cache.py  # NEW: 20 tests
  test_cache_store.py   # Updated schema version assertion (v1→v2)
  test_reports_service.py # Updated: get_warehouse_top returns tuple
  test_stock_runway_service.py # Updated: get_stock_runway returns tuple
  test_cli_report.py    # Updated: mock returns tuple
  test_cli_stock_runway.py # Updated: mock returns tuple
```

### Test results

- **736 tests passed** (0 failures)
- 20 new tests covering: ReportCacheEntry round-trip, upsert, multi-profile isolation, seller_id storage, list ordering, TTL hit/miss, deleted file miss, expired TTL miss, deserialisation round-trips, load helpers, `get_warehouse_top` cache hit/miss/skip, `Settings.reports_dir` path scoping

### Usage

```bash
wb report warehouse top --limit 10          # first call: hits API, caches result
wb report warehouse top --limit 10          # second call: [cached] label, instant
wb report warehouse top --no-cache          # force fresh API call
wb report warehouse stock-runway --days 30  # cached after first run
```

---

## How to Continue

1. Activate the virtual environment: `source .venv/Scripts/activate` (Windows) or `source .venv/bin/activate` (Linux/Mac)
2. Install in dev mode: `pip install -e ".[dev]"`
3. Run tests: `pytest tests/unit/ -v`
4. Run CLI: `python -m wb --help`
5. Use Python SDK: `from wb.sdk import list_campaigns, clone_campaign; campaigns = list_campaigns(profile='my_profile')`
6. All phases through 8C complete — the CLI is production-ready for human and agent operations

---

## Phase 9 - Batch Operations (v0.14.0) - COMPLETED

### What was built

- **`src/wb/core/batching.py`** (new): `chunk()` generator utility for splitting lists into sized batches; raises `ValueError` for invalid size
- **`src/wb/core/constants.py`**: Added `BID_BATCH_SIZE=1000`, `HISTORY_CHUNK_SIZE=20`, `PRODUCTS_CHUNK_SIZE=1000`
- **`src/wb/client/promotion.py`**: Added `set_item_bids_batch(payloads)` — single PATCH call for multiple bids
- **`src/wb/services/bids.py`**: Rewrote `set_item_bids` to use batch PATCH (one call per chunk of 1000); invalid bids get `success=False` result, valid ones still sent (collect-errors pattern)
- **`src/wb/services/campaigns.py`**: Added `start_campaigns`, `pause_campaigns`, `stop_campaigns`, `delete_campaigns` plural methods; per-campaign error collection without fail-fast
- **`src/wb/services/analytics.py`**: `get_product_history` now auto-chunks >20 nm_ids instead of raising `ValidationError`
- **`src/wb/cli/bid.py`**: `bid set-items` now accepts `--bids '[{"nm_id":123,"bid_kopecks":450}]'` inline JSON; `--file` optional; mutual-exclusion validation
- **`src/wb/cli/campaign.py`**: `campaign start/pause/stop/delete` accept `--ids 1,2,3` for multi-campaign; positional single-ID still works
- **`src/wb/core/output.py`**: `_filter_fields(data, fields)` helper + `fields` param on `OutputRenderer.display()`
- **`src/wb/cli/app.py`**: `--fields nm_id,orders` global option stored in `ctx.obj['fields']`
- **`src/wb/cli/_helpers.py`**: `get_fields(ctx)` helper; propagated to all 35 `renderer.display()` call sites across all CLI modules
- **`tests/integration/conftest.py`** + **`tests/integration/test_batch_read.py`**: Live read-only integration tests (auto-skip when `WB_API_TOKEN` absent)

### Test results

- **817 unit tests passed** (0 failures) — +23 new tests
- **7 integration tests passed** (0 failures) — live API coverage

---

## Phase I-2 — Per-Product Cost Tracking (v0.15.0) - COMPLETED

### What was built

- **`src/wb/domain/models.py`**: Added `NmStats` (per-NM spend, views, clicks, orders, avg_position) and `DayStats`; `CampaignStats.nm_stats` populated from `boosterStats[]` in fullstats response
- **`src/wb/services/stats.py`**: `get_product_spend(nm_ids, date_from, date_to)` — aggregates spend across all campaigns for each NM ID; `_fetch_fullstats_chunked()` auto-chunks campaign IDs into FULLSTATS_BATCH_SIZE=50 batches
- **`src/wb/cli/stats.py`**: `wb stats product-spend --nms <ids> --from <date> --to <date>` command; table shows NM ID, spend (₽), views, clicks, orders, avg position; cache write-through on every fullstats call
- **`src/wb/storage/cache.py`**: Cache auto-populated on fullstats API calls (write-through); `get_cached_stats()` for same-day reads

### Test results

- **843 unit tests passed** (0 failures) — +26 new tests

---

## Phase I-3 — Composite Commands (v0.16.0) - COMPLETED

### What was built

- **`src/wb/services/product.py`** (new): `ProductService.get_summary(nm_ids)` — single call returning `ProductSummary` with sales funnel + ad spend + clusters + bids; analytics and prices are best-effort (zero if token unavailable)
- **`src/wb/domain/models.py`**: Added `ProductSummary`, `CampaignOverview` dataclasses with `to_dict()` for JSON serialization
- **`src/wb/cli/product.py`** (new): `wb product summary --nms <ids> --json` — composite command; `wb campaign overview --id <id>` — details + budget + stats + per-NM + clusters in one call
- **`src/wb/domain/models.py`**: `MutationResult.already_applied: bool` — idempotent mutations return `already_applied: true` when state unchanged instead of error
- **`src/wb/services/campaigns.py`**: All lifecycle mutations (`start`, `pause`, `stop`) detect current state and set `already_applied=True` for idempotent retries
- **`src/wb/sdk.py`**: SDK parity — `get_product_summary()`, `get_campaign_overview()`, `rename_campaign()`, `delete_campaign()`, `get_campaign_stats()`, `get_prices()` callable from Python
- **`src/wb/services/_factory.py`**: `create_product_service()` wires all sub-services with best-effort analytics/prices

### Test results

- **876 unit tests passed** (0 failures) — +33 new tests

---

## Phase I-4 — Rate Limiting & Resilience (v0.17.0) - COMPLETED

### What was built

- **`RATE_LIMITS.md`** (new): Agent-optimized reference table mapping every CLI command → endpoint constant → path → limit (calls, period, burst) → swagger source. Includes per-endpoint guidance for agents (batch sizing, cache-first recommendations), notes on burst=1 endpoints, and instructions for updating when new limits are discovered.

- **`src/wb/core/rate_limits.py`** (new): `ENDPOINT_LIMITS` dict mapping 30 endpoint path constants to `(calls, period_seconds)` tuples. Values sourced from `docs/swagger/08-promotion.yaml`, `11-analytics.yaml`, `12-reports.yaml`; empirical entries noted inline. Burst=1 endpoints stored as `(1, interval)` to enforce spacing (e.g. fullstats: `(1, 20.0)` for its 3/min, burst=1 limit).

- **`src/wb/core/rate_limiter.py`** (new): Thread-safe sliding-window `RateLimiter` using `collections.deque` + `threading.Lock`. `acquire()` evicts expired timestamps, sleeps until a slot opens if the window is full, then records the call. Raises `ValueError` for invalid `calls < 1` or `period <= 0`.

- **`src/wb/core/batching.py`**: Added `paginate_all(fetch, page_size)` — reusable offset-based pagination helper. Calls `fetch(limit, offset)` until a page shorter than `page_size` is returned (last-page sentinel). Used by `PricesService` and available for all future offset-based APIs.

- **`src/wb/client/http.py`**: Added `path_limiters: dict[str, RateLimiter] | None` constructor param. In both `request()` and `request_raw()`, calls `limiter.acquire()` once before the retry loop — preemptive throttle, not reactive. Default `None` → zero behaviour change for existing tests.

- **`src/wb/services/_factory.py`**: Added `_Container` class (`ServiceContainer` public alias) caching `Settings` and `WbHttpClient` instances per `(base_url, token)` key. Avoids re-parsing env vars and re-creating `httpx.Client` on every factory call. `_Container.reset()` clears all state for test isolation. `_build_limiters()` constructs per-path `RateLimiter` instances from `ENDPOINT_LIMITS`; injected into promotion and analytics HTTP clients.

- **`src/wb/services/prices.py`**: `_fetch_all_pages()` refactored to use `paginate_all()` instead of a hand-rolled offset loop — same behaviour, shared implementation.

### Key design decisions

- **Per-path limiters, not per-client**: Different endpoints on the same base URL have different limits (e.g. fullstats 1/20s vs. campaign list 5/s). `path_limiters` dict gives precise control without over-throttling.
- **Preemptive over reactive**: `acquire()` runs before the HTTP call. The existing 429 retry backoff in `WbHttpClient` remains as a safety net for limits the preemptive layer doesn't cover (e.g. `EP_PRICES_GOODS_FILTER` — not in swagger).
- **Burst=1 → interval encoding**: Swagger `burst=1` means calls must be evenly spaced. Stored as `(1, interval)` (e.g. `(1, 20.0)` for fullstats) rather than `(3, 60.0)` to enforce the interval constraint in the sliding window.
- **Container caching scope**: `_Container` is module-level (process-scoped). One process → one token → one HTTP client with shared rate limiters. This is correct for CLI usage. For tests, `ServiceContainer.reset()` clears state between test cases.

### Files changed

| File | Type | Change |
|---|---|---|
| `RATE_LIMITS.md` | new | Full endpoint rate limit reference for agents |
| `src/wb/core/rate_limits.py` | new | 30-entry endpoint→limit map (swagger-sourced) |
| `src/wb/core/rate_limiter.py` | new | Thread-safe sliding-window `RateLimiter` |
| `src/wb/core/batching.py` | modified | Added `paginate_all()` helper |
| `src/wb/client/http.py` | modified | `path_limiters` param + `acquire()` call |
| `src/wb/services/_factory.py` | modified | `_Container` caching + rate limiter wiring |
| `src/wb/services/prices.py` | modified | `_fetch_all_pages()` uses `paginate_all()` |
| `tests/unit/test_rate_limiter.py` | new | 11 tests: init validation, acquire, eviction, threads |
| `tests/unit/test_batching.py` | modified | 9 new `TestPaginateAll` tests |

### Test results

- **901 unit tests passed** (0 failures) — +25 new tests (+11 rate_limiter, +9 batching, +5 prices refactor)

---

## Phase I-7 — Agent Skills (v0.20.0) - COMPLETED

### What was built

**Native CLI commands** (`wb assess`, `wb pulse`) — rate-limit-coordinated multi-endpoint aggregation that cannot be done safely from external subprocess scripts (rate limiter is process-local):

- **`src/wb/domain/assess_models.py`** (new): `AssessSnapshot`, `CampaignAssessSummary`, `PulseReport`, `CampaignPulse`, `PulseBaseline` dataclasses (all `slots=True`)
- **`src/wb/services/assess.py`** (new): `AssessService` — sequential `_safe_*` pattern; full mode (balance + campaigns + product spend + bid baselines); `--quick` skips product spend (avoids 20s rate limit wait); saves `~/.wb-cli/pulse_baseline.json`
- **`src/wb/services/pulse.py`** (new): `PulseService` — reads `pulse_baseline.json`, computes bid drift %; fires four alert codes (`competitor_surge`, `budget_low`, `campaign_paused`, `bid_floor_rising`)
- **`src/wb/cli/assess.py`** (new): `wb assess [--nm <id>] [--quick] [--json] [--compact]`
- **`src/wb/cli/pulse.py`** (new): `wb pulse --campaigns <ids> [--json] [--compact]`
- **`src/wb/services/_factory.py`**: Added `create_assess_service()`, `create_pulse_service()`
- **`src/wb/cli/app.py`**: Registered `assess` and `pulse` commands

**Claude Code skills** (`.claude/skills/<name>/SKILL.md` — subdirectory format):

| Skill | Cadence | Backed by |
|-------|---------|-----------|
| `wb-assess` | Once per morning | `wb assess` native command |
| `wb-pulse` | Every 1-2h intraday | `wb pulse` native command |
| `wb-launch` | Per new product | Sequential wb commands + `rules.json` |
| `wb-optimize` | Daily per campaign | Sequential wb commands |
| `wb-manage` | As needed | Direct wb command dispatch |
| `wb-keywords` | Weekly | `wb-keywords/scripts/wb_keywords.py` |
| `wb-calibrate` | Biweekly | `wb-calibrate/scripts/wb_calibrate.py` |

**External scripts** (co-located with their skill):

- **`.claude/skills/wb-keywords/scripts/wb_keywords.py`**: Calls wb cluster commands sequentially, joins `keyword_rules.json` lifecycle state, classifies keywords as hot/underperforming/blocked/ready-to-restore
- **`.claude/skills/wb-calibrate/scripts/wb_calibrate.py`**: Reads 30-day campaign analytics grouped by `[goal]` name prefix, adjusts `bid_percentile` per strategy, sets `validated: true` when data is sufficient

**Adaptive rule templates** (bootstrapped to `~/.wb-cli/` on first use):

- **`.claude/skills/wb-launch/rules.json`**: 4 strategy definitions (`new_product_visibility`, `volume_sales`, `steady_low_cost`, `brand_defense`) with `confidence: "low"` until `wb-calibrate` validates them
- **`.claude/skills/wb-keywords/keyword_rules.json`**: Empty keyword lifecycle store

### File structure additions

```
src/wb/
  domain/
    assess_models.py       # NEW: AssessSnapshot, CampaignAssessSummary, PulseReport, CampaignPulse, PulseBaseline
  services/
    assess.py              # NEW: AssessService
    pulse.py               # NEW: PulseService
    _factory.py            # +create_assess_service, create_pulse_service
  cli/
    assess.py              # NEW: wb assess command
    pulse.py               # NEW: wb pulse command
    app.py                 # +assess, pulse registrations
.claude/skills/
  wb-assess/SKILL.md
  wb-pulse/SKILL.md
  wb-launch/SKILL.md
  wb-launch/rules.json
  wb-optimize/SKILL.md
  wb-manage/SKILL.md
  wb-keywords/SKILL.md
  wb-keywords/keyword_rules.json
  wb-keywords/scripts/wb_keywords.py
  wb-calibrate/SKILL.md
  wb-calibrate/scripts/wb_calibrate.py
tests/unit/
  test_assess_service.py   # NEW: 35 tests
  test_pulse_service.py    # NEW (in test_assess_service.py)
```

### Test results

- **952 unit tests passed** (0 failures) — +35 new tests covering AssessService, PulseService, drift computation, alert logic, CLI JSON output

---

## Phase F-4 — UTF-8 Pipe Fix (v0.20.2) - COMPLETED

### Problem

`wb campaign list | more` (and any piped command) crashed with:

```
UnicodeEncodeError: 'charmap' codec can't encode characters in position 597-604
```

WB content is in Russian (Cyrillic). When the CLI ran in agent shells (Codex, etc.) inheriting the Windows legacy code page (cp437), piped stdout couldn't encode Cyrillic — crash with no output. Interactive Windows Terminal sessions were unaffected because they configure UTF-8 separately.

### Root cause

`sys.stdout` encoding was never reconfigured at startup. Python inherited the system code page (cp437) on piped stdout. Rich wrote UTF-8 Cyrillic through `sys.stdout` which then tried to encode with cp437.

Secondary: 10 bare `Console()` calls across CLI modules bypassed the centralized `_stdout_console` (which had `legacy_windows=False`) — scattering output logic.

### Files changed

- **`src/wb/cli/app.py`**: Added `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` + stderr at top of `main()`. Primary fix — covers all output paths.
- **`src/wb/cli/auth.py`**: Replaced `Console().print(table)` with `_stdout_console.print(table)`.
- **`src/wb/cli/campaign.py`**: Replaced `console = Console()` with `console = _stdout_console`.
- **`src/wb/cli/portal.py`**: Replaced `Console().print(table)` with `_stdout_console.print(table)`.
- **`src/wb/cli/prices.py`**: Replaced `Console().print(table)` with `_stdout_console.print(table)`.
- **`src/wb/cli/product.py`**: Replaced `Console().print(table)` with `_stdout_console.print(table)`.
- **`src/wb/cli/pulse.py`**: Replaced `console = Console()` with `console = _stdout_console`.
- **`src/wb/cli/report.py`**: Replaced 3× `Console().print(table)` with `_stdout_console.print(table)`.

### Test results

- **987 unit tests passed** (0 failures) — no regressions
