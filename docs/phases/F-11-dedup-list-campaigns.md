# Fix F-11 — Dedup `list_campaigns` in `stats daily-report` (v0.25.3)

**Date:** 2026-04-24
**Tests:** 1106/1107 (1 pre-existing env-isolation failure in `test_auth_list_empty`, unrelated)

## Problem

`StatsService.get_daily_report` called the promotion API's `list_campaigns` endpoint **twice** per invocation:

1. `_get_daily_report_fresh` → `_collect_nm_ids_by_status(statuses)` → `client.list_campaigns(status=statuses)`
2. `_get_daily_report_fresh` → `get_product_spend(...)` → `_find_campaign_ids_for_nms(nm_set)` → `client.list_campaigns()` *(no filter — full scan)*

Both hit `GET /api/advert/v2/adverts`, and since the nm_ids in call 1 came from active campaigns, the full-scan in call 2 was strictly redundant: any campaign containing those nm_ids was already part of the first response.

## What Was Built

- **One `list_campaigns` call, filtered in memory.** `_get_daily_report_fresh` now calls `self._client.list_campaigns()` **once** (unfiltered — the superset), then applies the status filter client-side via the new helper `_collect_nm_ids_from_campaigns(raw, status_set)`.
- **Pass-through of pre-fetched campaigns.** `_get_product_spend_fresh` and `_find_campaign_ids_for_nms` both accept an optional `raw_campaigns` kwarg. When `_get_daily_report_fresh` threads the list through, the downstream helpers skip their own `list_campaigns` call and use the pre-fetched data.
- **Backward compatibility preserved.** `get_product_spend` (public method used by `wb stats product-spend`) still works standalone — when called with no `raw_campaigns`, `_find_campaign_ids_for_nms` fetches exactly as before.
- **Old helper removed.** `_collect_nm_ids_by_status` was only used inside `_get_daily_report_fresh`; it's replaced by `_collect_nm_ids_from_campaigns`. The test class was renamed and its fixtures now include a `status` field (required for client-side filtering; previously the server-side filter meant the field was never inspected locally).

## Files Changed

| File | Change |
|------|--------|
| `src/wb/services/stats.py` | Rewrote `_get_daily_report_fresh` to make one unfiltered `list_campaigns` call and thread the raw list through; added `_collect_nm_ids_from_campaigns(raw, status_set)`; removed `_collect_nm_ids_by_status`; `_get_product_spend_fresh` and `_find_campaign_ids_for_nms` accept optional `raw_campaigns` kwarg |
| `tests/unit/test_stats_daily_report.py` | Renamed `TestCollectNmIdsByStatus` → `TestCollectNmIdsFromCampaigns` (4 tests rewritten with new signature); added 2 new tests `test_calls_list_campaigns_exactly_once` and `test_list_campaigns_called_without_status_filter`; updated 2 existing tests (`test_uses_active_statuses_by_default`, `test_respects_custom_statuses`) to reflect the client-side filter; added `status` field to 4 existing campaign fixtures |
| `docs/FIXES.md`, `docs/PROGRESS.md` | F-11 row flipped to ✅ DONE |

## Live Test Results

Cleared `~/.wb-cli/rate_limits.db`, then ran `wb --json --compact stats daily-report --date 2026-04-23`. DB state after:

```
def07bba57905265  /api/advert/v2/adverts    ← 1 row (was 2 pre-F-11)
def07bba57905265  /adv/v3/fullstats         ← 1 row (unchanged)
589f628451e31cb7  _seller_global            ← 3 rows (F-10 limiter, 1 per endpoint)
```

`/api/advert/v2/adverts` count is the witness: exactly one acquire recorded, proving the duplicate fetch was eliminated. Before F-11 the same workload would have produced two rows for this endpoint (one per `list_campaigns` invocation). The three `_seller_global` rows reflect the three distinct endpoint calls across both promotion and analytics HTTP clients, unaffected by this fix.

## Behavioural note

The refactor preserves the previous result semantics for `get_daily_report`: identical `DailyReportRow` output for the same inputs. The only observable change is **one fewer HTTP call** per invocation (and a slightly larger in-memory filter pass — negligible at any realistic campaign count). Server-side `?status=` filtering is no longer applied to the one call, which is why the updated tests assert `list_campaigns.assert_called_once_with()` (no kwargs).
