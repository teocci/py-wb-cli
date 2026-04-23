# Phase I-1 — Batch Operations (v0.14.0)

**Date:** 2026-04-06 | **Tests:** 817 passed (+23) + 7 integration tests

## What Was Built

- `core/batching.py`: `chunk()` generator; raises `ValueError` for invalid size
- `BID_BATCH_SIZE=1000`, `HISTORY_CHUNK_SIZE=20`, `PRODUCTS_CHUNK_SIZE=1000` constants
- `PromotionClient.set_item_bids_batch(payloads)` — single PATCH call
- `BidService.set_item_bids` rewritten: batch PATCH (one call per chunk of 1000); collect-errors pattern
- `CampaignService`: `start/pause/stop/delete_campaigns` plural methods with per-campaign error collection
- `AnalyticsService.get_product_history`: auto-chunks >20 nm_ids
- `bid set-items`: accepts `--bids '[{"nm_id":123,"bid_kopecks":450}]'` inline JSON; `--file` optional
- `campaign start/pause/stop/delete`: accept `--ids 1,2,3` for multi-campaign
- `core/output.py`: `_filter_fields(data, fields)` + `fields` param on `OutputRenderer.display()`
- `--fields nm_id,orders` global option stored in `ctx.obj['fields']`; `get_fields(ctx)` helper
