# WB CLI - Implementation Progress

## Version History

| Version | Phase | Date | Description |
|---------|-------|------|-------------|
| 0.1.0 | Phase 0 | 2026-03-18 | Foundation - CLI scaffold, config, auth, HTTP client, audit |
| 0.2.0 | Phase 1 | 2026-03-18 | Read-only visibility - campaigns, budgets, bids, stats, clusters |

## Current Version: 0.2.0

## Phase Status

| Phase | Name | Status | Version |
|-------|------|--------|---------|
| 0 | Foundation | COMPLETED | 0.1.0 |
| 1 | Read-only operational visibility | COMPLETED | 0.2.0 |
| 2 | Core write controls | PENDING | - |
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

## Phase 2 - Core Write Controls (PENDING)

### Planned scope

- Campaign create/start/pause/stop/rename/delete
- Item bid changes
- Placement changes
- Add/remove items from campaigns
- Budget top-up
- Dry-run support for all mutations

### Expected version: 0.3.0

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
