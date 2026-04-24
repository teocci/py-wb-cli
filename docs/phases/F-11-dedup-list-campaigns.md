# Fix F-11 — Dedup `list_campaigns` in `stats daily-report` (v0.25.3)

**Status:** 🔲 PLANNED
**Scope:** `src/wb/services/stats.py`

## Problem

`StatsService.get_daily_report` calls the promotion API's `list_campaigns` endpoint twice per invocation:

1. `_get_daily_report_fresh` → `_collect_nm_ids_by_status(statuses)` → `client.list_campaigns(status=statuses)`
2. `_get_daily_report_fresh` → `get_product_spend(...)` → `_find_campaign_ids_for_nms(nm_set)` → `client.list_campaigns()` *(no filter — full scan)*

Both calls hit `GET /api/advert/v2/adverts`. The second call is strictly redundant: its raw output is a superset of what the first already fetched — we only need the subset whose IDs contain any of our NM IDs.

## Solution

Refactor `_collect_nm_ids_by_status` to return `(nm_ids, raw_campaigns)` so the campaigns list is cached once; pass `raw_campaigns` into a new `_find_campaign_ids_for_nms_from(raw, nm_set)` variant so the second API call disappears. Keep the old `_find_campaign_ids_for_nms` for `get_product_spend` standalone usage.

Since the first call was already status-filtered to `[9, 11]` (active), scanning it for matching NMs is strictly sufficient — a campaign can't contain a product that's not in its own `nm_settings`.

## Steps

- [ ] Refactor `_collect_nm_ids_by_status` to return a tuple `(nm_ids, raw_campaigns_with_status)`.
- [ ] Add `_find_campaign_ids_for_nms_from(raw_campaigns, nm_set)` helper.
- [ ] In `_get_daily_report_fresh`, pass `raw_campaigns` through and call a new `_get_product_spend_from_campaigns(raw_campaigns, nm_ids, date, date)` path that skips the redundant fetch.
- [ ] Unit test: `get_daily_report` triggers exactly one `list_campaigns` call (currently: two).
- [ ] Live test: `wb stats daily-report` still returns identical data.
