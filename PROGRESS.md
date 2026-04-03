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

## Current Version: 0.5.0

## Phase Status

| Phase | Name | Status | Version |
|-------|------|--------|---------|
| 0 | Foundation | COMPLETED | 0.1.0 |
| 1 | Read-only operational visibility | COMPLETED | 0.2.0 |
| 2 | Core write controls | COMPLETED | 0.3.0 |
| 3 | Search-cluster control | COMPLETED | 0.4.0 |
| 4 | Analytics bridge | COMPLETED | 0.5.0 |
| 5 | Optimization workflows | PENDING | - |

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

## Phase 5 - Optimization Workflows (PENDING)

### Planned scope

- Recommendation-first optimize commands
- Explainable rule outputs
- Guarded --apply execution

### Expected version: 0.6.0

---

## How to Continue

1. Activate the virtual environment: `source .venv/Scripts/activate` (Windows) or `source .venv/bin/activate` (Linux/Mac)
2. Install in dev mode: `pip install -e ".[dev]"`
3. Run tests: `pytest tests/unit/ -v`
4. Run CLI: `python -m wb --help`
5. Continue with the next pending phase
