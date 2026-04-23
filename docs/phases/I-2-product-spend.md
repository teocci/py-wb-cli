# Phase I-2 — Per-Product Cost Tracking (v0.15.0)

**Date:** 2026-04-06 | **Tests:** 843 passed (+26)

## What Was Built

- `NmStats` (per-NM spend/views/clicks/orders/avg_position), `DayStats`; `CampaignStats.nm_stats` from `boosterStats[]`
- `StatsService.get_product_spend(nm_ids, date_from, date_to)` — aggregates spend across all campaigns per NM ID
- `_fetch_fullstats_chunked()` — auto-chunks campaign IDs into `FULLSTATS_BATCH_SIZE=50` batches
- `wb stats product-spend --nms <ids> --from <date> --to <date>` — table: NM ID, spend (₽), views, clicks, orders, avg position
- Cache write-through on every fullstats API call; `get_cached_stats()` for same-day reads
