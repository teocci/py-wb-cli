# Phase 1 — Read-Only Operational Visibility (v0.2.0)

**Date:** 2026-03-18 | **Tests:** 249 passed (+100)

## What Was Built

- 10 Promotion API endpoint constants
- `from_api()` class methods on `ProductCard`, `ItemBid`, `SearchCluster`, `BudgetSnapshot`, `CampaignStats`, `ClusterStats`
- New models: `AccountBalance`, `RecommendedBid`
- `PromotionClient` (`client/promotion.py`): 11 read methods
- 5 service classes: `CampaignService`, `BudgetService`, `StatsService`, `ClusterService`, `BidService` + `_factory.py`
- CLI commands: `wb campaign list|get|eligible-subjects|eligible-items`, `wb bid recommend|minimum|get-items`, `wb budget balance|get`, `wb stats campaign|campaigns`, `wb cluster list|active|inactive|bids|stats`
- All commands support `--json`
