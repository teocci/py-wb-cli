# Phase I-17 — Status filter on campaign discovery for `product-spend`

**Status:** ✅ DONE · **Version:** 0.34.0 · **Date:** 2026-05-04 · **Tests:** 1301 (1300 passing, 1 pre-existing env failure)

## What Was Built

- Added `statuses: list[int] | None = None` kwarg to `_find_campaign_ids_for_nms` in `StatsService`. When provided, campaigns whose `status` is not in the given set are skipped before NM-ID matching. Default `None` preserves behaviour for all other callers.
- Updated `_get_product_spend_fresh` to pass `statuses=[9, 11]` (running + paused) to the discovery helper, preventing stopped/archived campaigns from being included in `EP_CAMPAIGN_FULLSTATS` batch counts.
- Fixed all existing tests in `test_stats_product_spend.py` and `test_response_cache_integration.py` that used campaign dicts without a `status` field — added `'status': 9` (or `11`) so they continue to exercise the intended paths.
- Added `TestProductSpendStatusFilter` test class with two new cases:
  - `test_stopped_campaign_excluded_from_fullstats` — running (9) + paused (11) + stopped (7) sharing same NM; asserts fullstats receives only running + paused IDs.
  - `test_only_stopped_campaigns_returns_zeros` — all matching campaigns stopped; asserts `get_campaign_stats` is never called and zero-spend row returned.

## Files Changed

| File | Change |
|------|--------|
| `src/wb/services/stats.py` | `_find_campaign_ids_for_nms` gains `statuses` kwarg; `_get_product_spend_fresh` passes `[9, 11]` |
| `tests/unit/test_stats_service.py` | New `TestProductSpendStatusFilter` class (2 tests) |
| `tests/unit/test_stats_product_spend.py` | Added `'status': 9/11` to 5 campaign mock dicts |
| `tests/unit/test_response_cache_integration.py` | Added `'status': 9` to campaign mock in `_make_service` |

## Behaviour

- `get_product_spend` now only queries fullstats for campaigns in running (9) or paused (11) state. Stopped (7), archived (11 → actually archived is different... status 7 is stopped/completed), and other non-active statuses are excluded.
- `_get_daily_report_fresh` path is unaffected in intent: it passes `raw_campaigns` through to `_get_product_spend_fresh`, which now also applies the status filter — this is a bonus reduction in fullstats calls for the daily-report path too.
- No CLI surface change. Internal only.
