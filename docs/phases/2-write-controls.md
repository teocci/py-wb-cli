# Phase 2 — Core Write Controls (v0.3.0)

**Date:** 2026-03-18 | **Tests:** 326 passed (+77)

## What Was Built

- `WbHttpClient.delete()`: HTTP DELETE method
- 9 write-path endpoint constants
- New models: `MutationResult` (dry-run aware), `CampaignCreate`, `BidMutation`, `PlacementConfig`
- `PromotionClient` write methods: `start/pause/stop/rename/delete/create_campaign`, `add/remove_items`, `set_placements`, `deposit_budget`, `set_item_bid`
- `CampaignService` write methods: all lifecycle + items/placements, all with `dry_run` support
- `BudgetService.topup()`, `BidService.set_item_bid/set_item_bids`
- CLI write commands (all with `--dry-run`, `--yes`, audit logging):
  - `wb campaign create/start/pause/stop/rename/delete/add-items/remove-items/set-placements`
  - `wb bid set-item/set-items`
  - `wb budget topup`
- `OutputRenderer.is_json` property (auto-skip confirms in JSON mode)
