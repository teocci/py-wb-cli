# Phase 8C — Report Caching & Multi-Seller Storage (v0.12.0)

**Date:** 2026-04-04 | **Tests:** 736 passed (+20)

## What Was Built

- `REPORT_CACHE_TTL_HOURS = 6`, `REPORTS_DIR_NAME = 'reports'` constants
- `Profile.seller_id`: Optional metadata field (no routing logic — pure display)
- `Settings.reports_dir(profile_name)`: Returns `~/.wb-cli/<profile_name>/reports/`
- `ReportCacheEntry` dataclass in `domain/cache_models.py`
- `CacheStore` schema v2: `report_cache` table with `UNIQUE(profile_name, report_type, date)`
  - `save_report_cache`, `get_report_cache`, `list_report_cache`
- Cache-aware `get_warehouse_top(use_cache=True)` and `get_stock_runway(use_cache=True)` returning `(data, from_cache)` tuples
- `--cache/--no-cache` flag on `warehouse top` and `stock-runway` commands
- `[cached]` label in table titles when serving from cache

## Storage Layout

```
~/.wb-cli/
  profiles.json
  cache.db                               ← shared SQLite; report_cache table
  <profile_name>/
    reports/
      warehouse_remains_YYYY-MM-DD.json  # raw API download, TTL-guarded
      sales_<N>d_YYYY-MM-DD.json         # raw sales window, TTL-guarded
```
