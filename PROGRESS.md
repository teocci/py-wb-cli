# WB CLI - Implementation Progress

## Version History

| Version | Phase | Date | Description |
|---------|-------|------|-------------|
| 0.1.0 | Phase 0 | 2026-03-18 | Foundation - CLI scaffold, config, auth, HTTP client, audit |
| 0.2.0 | Phase 1 | 2026-03-18 | Read-only visibility - campaigns, budgets, bids, stats, clusters |
| 0.3.0 | Phase 2 | 2026-03-18 | Core write controls - lifecycle, items, bids, budget, placements |
| 0.3.1 | Auth | 2026-03-19 | Dual auth - portal session support, env var fallback, /ping fix |

## Current Version: 0.3.1

## Phase Status

| Phase | Name | Status | Version |
|-------|------|--------|---------|
| 0 | Foundation | COMPLETED | 0.1.0 |
| 1 | Read-only operational visibility | COMPLETED | 0.2.0 |
| 2 | Core write controls | COMPLETED | 0.3.0 |
| 3 | Search-cluster control | PENDING | - |
| 4 | Analytics bridge | PENDING | - |
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

## Phase 3 - Search-cluster Control (PENDING)

### Planned scope

- Cluster bid listing and mutations
- Minus phrase workflows (list, set, clear)
- Planning diffs for cluster changes

### Expected version: 0.4.0

---

## Phase 4 - Analytics Bridge (PENDING)

### Planned scope

- Search-query reporting
- Sales-funnel access
- CSV report workflows

### Expected version: 0.5.0

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
