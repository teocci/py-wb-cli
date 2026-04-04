# WB CLI - Implementation Progress

## Version History

| Version | Phase | Date | Description |
|---------|-------|------|-------------|
| 0.1.0 | Phase 0 | 2026-03-18 | Foundation - CLI scaffold, config, auth, HTTP client, audit |
| 0.2.0 | Phase 1 | 2026-03-18 | Read-only visibility - campaigns, budgets, bids, stats, clusters |
| 0.3.0 | Phase 2 | 2026-03-18 | Core write controls - lifecycle, items, bids, budget, placements |
| 0.3.1 | Auth | 2026-03-19 | Dual auth - portal session support, env var fallback, /ping fix |
| 0.3.2 | API Fix | 2026-04-02 | Full API migration - all dead endpoints replaced with current WB API |
| 0.4.0 | Phase 3 | 2026-04-02 | Search-cluster control - cluster bid mutations, minus phrases, daily stats |
| 0.5.0 | Phase 4 | 2026-04-03 | Analytics bridge - sales funnel, search reports, CSV exports |
| 0.6.0 | Phase 5 | 2026-04-03 | Optimization workflows - recommendation engine, guarded apply |
| 0.8.0 | Phase 7 | 2026-04-03 | Local SQLite cache - historical snapshots, wb budget history |
| 0.9.0 | Agent Fixes | 2026-04-03 | Agent-critical fixes - JSON errors, per-NM stats, Campaign nm_ids |
| 0.10.0 | Phase 8A | 2026-04-04 | Warehouse inventory reports — async report lifecycle + top products |
| 0.11.0 | Phase 8B | 2026-04-04 | Stock runway — days-until-stockout via Statistics API sales velocity |

## Current Version: 0.11.0

## Phase Status

| Phase | Name | Status | Version |
|-------|------|--------|---------|
| 0 | Foundation | COMPLETED | 0.1.0 |
| 1 | Read-only operational visibility | COMPLETED | 0.2.0 |
| 2 | Core write controls | COMPLETED | 0.3.0 |
| 3 | Search-cluster control | COMPLETED | 0.4.0 |
| 4 | Analytics bridge | COMPLETED | 0.5.0 |
| 5 | Optimization workflows | COMPLETED | 0.6.0 |
| 6 | Agent platform support | COMPLETED | 0.7.0 |
| 7 | Local SQLite cache + historical snapshots | COMPLETED | 0.8.0 |
| A1 | Agent-critical fixes | COMPLETED | 0.9.0 |
| 8A | Warehouse inventory reports | COMPLETED | 0.10.0 |
| 8B | Stock runway (days-until-stockout) | COMPLETED | 0.11.0 |

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
- **Auth commands**: login, logout, list, use, status, ping

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

## How to Continue

1. Activate the virtual environment: `source .venv/Scripts/activate` (Windows) or `source .venv/bin/activate` (Linux/Mac)
2. Install in dev mode: `pip install -e ".[dev]"`
3. Run tests: `pytest tests/unit/ -v`
4. Run CLI: `python -m wb --help`
5. Use Python SDK: `from wb.sdk import list_campaigns, clone_campaign; campaigns = list_campaigns(profile='my_profile')`
6. All phases through 8B complete — the CLI is production-ready for human and agent operations
