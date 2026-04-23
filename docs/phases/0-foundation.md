# Phase 0 — Foundation (v0.1.0)

**Date:** 2026-03-18 | **Tests:** 149 passed

## What Was Built

- Project scaffolding: `pyproject.toml`, `src/wb` package structure, pytest config
- Core constants: API URLs, exit codes (`IntEnum`), default values
- Exception hierarchy: `WbCliError` base, `ValidationError`, `AuthenticationError`, `RateLimitError`, `ApiError`, `ConfigError`
- Domain enums: `CampaignStatus`, `CampaignType`, `PaymentType`, `PlacementType`, `BidType`, `OutputFormat`, `VerbosityLevel`
- Domain models: `Campaign`, `ProductCard`, `ItemBid`, `SearchCluster`, `ClusterBid`, `BudgetSnapshot`, `CampaignStats`, `ClusterStats`, `MinusPhraseSet`, `OptimizationDecision`
- Config system: Pydantic `BaseSettings` with `WB_` prefix env var support
- Output rendering: JSON/table/quiet output via Rich, `OutputRenderer` class
- HTTP client: `httpx`-based with exponential backoff, jitter, rate-limit header parsing, retry on 429/5xx
- Auth/profiles: Multi-profile token storage (JSON file), per-category tokens
- Token validation: Lightweight WB API ping for promotion tokens
- Audit logging: Append-only JSONL audit trail for mutating operations
- CLI layer: Typer-based with global options (`--verbose`, `--quiet`, `--json`, `--profile`)
- Auth commands: `login`, `logout`, `list`, `use`, `status`, `ping`, `categories`, `login-portal`, `generate-token`
