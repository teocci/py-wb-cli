# Phase I-17 — Status filter on campaign discovery for `product-spend`

**Status:** 🔲 PLANNED · **Depends on:** none
**Plan:** [floofy-orbiting-parnas.md](../../../../Users/teocci/.claude/plans/floofy-orbiting-parnas.md)

## Problem

[`_find_campaign_ids_for_nms`](../../src/wb/services/stats.py) iterates the full campaign list — including stopped/archived campaigns whose `nm_settings` still list the requested NM IDs — and includes them in the `EP_CAMPAIGN_FULLSTATS` batch count. Each extra 50-campaign batch costs **+1 hour** on Base tokens. Sellers with legacy stopped campaigns sharing NMs with active ones pay multi-hour cooldowns for zero data (stopped campaigns produced no spend on the report date).

## Goal

Filter campaigns to running (status 9) and paused (11) before counting fullstats batches, so Base sellers don't burn cooldown buckets on stopped legacy campaigns. Internal change only — no CLI surface change.

## Changes

| File | Change |
|------|--------|
| `src/wb/services/stats.py` | `_get_product_spend_fresh` filters `raw_campaigns` to `[9, 11]` before passing to `_find_campaign_ids_for_nms`. `_find_campaign_ids_for_nms` accepts an optional `statuses` arg (default `None` = no filter, preserves caller behaviour for any non-spend path). |
| `tests/unit/test_stats_service.py` | New test: mock `list_campaigns` with one running, one paused, one stopped campaign all sharing the requested NM set; assert the resulting fullstats call receives only the running + paused IDs. |

## Steps

- [ ] Add `statuses` kwarg to `_find_campaign_ids_for_nms`
- [ ] Update `_get_product_spend_fresh` to filter to `[9, 11]` before discovery
- [ ] Confirm `_get_daily_report_fresh` is unaffected (it already filters via `_collect_nm_ids_from_campaigns`)
- [ ] Add unit test for the status-filter branch
- [ ] Run `pytest tests/unit/ -v` — all green
- [ ] Live spot-check: pick a date with at least one stopped legacy campaign sharing NMs with active campaigns; run `wb --json stats product-spend --nms <ids> --from <date> --to <date>` before and after; expect identical `spend` values per NM and strictly fewer `EP_CAMPAIGN_FULLSTATS` advances visible in `wb rate status`.
- [ ] `phase-complete` → version 0.34.0, tag, push

## Verification

- Unit test passes asserting fullstats receives only running + paused IDs.
- `pytest tests/unit/ -v` green.
- Live: `wb rate status` advances `EP_CAMPAIGN_FULLSTATS` strictly fewer times for sellers with legacy stopped-campaign overlap.

## Out of scope

- Daily-report path (`get_daily_report` / `_get_daily_report_fresh`) — already filters via `_collect_nm_ids_from_campaigns`. No change there.
- Exposing the filter on the CLI surface — internal change only.
