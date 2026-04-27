# Phase 7 — Local SQLite Cache (v0.8.0)

**Date:** 2026-04-03 | **Tests:** 604 passed (+65)

> **Renamed in I-16 (v0.33.0):** the `wb cache ...` group described below moved to `wb snapshot ...`, and the `snapshot` / `snapshot-all` subcommands became `capture` / `capture-all`. The original `wb cache` namespace is now occupied by the I-15 HTTP response cache. See [I-16 phase doc](I-16-rename-cache-snapshot.md).

## What Was Built

- `domain/cache_models.py`: `CampaignSnapshot`, `StatsRecord`, `ClusterRecord`, `BudgetEvent` (`@dataclass(slots=True)`)
- `storage/cache.py`: `CacheStore` — SQLite-backed, 4 tables, schema versioning via `PRAGMA user_version`, WAL journal mode
  - `save/list_campaign`, `save/list_stats` (upsert by date), `save/list_cluster`, `save/list_budget_event`
  - `clear(profile, campaign_id?)`, `summary(profile)`
- `services/cache.py`: `CacheService` — snapshot collection + history queries
  - `snapshot_campaign(id, profile, *, nm_id, with_stats, with_clusters)`, `snapshot_all(profile)`
  - Errors swallowed with warning (partial snapshot still useful)
- 8 CLI commands under `wb cache`: `list`, `snapshot`, `snapshot-all`, `history campaigns|stats|clusters`, `clear`
- `wb budget history` — queries stored budget events
- `wb budget topup` now persists `BudgetEvent` to cache after every successful deposit
