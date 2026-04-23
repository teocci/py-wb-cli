# Phase I-3 — Composite Commands (v0.16.0)

**Date:** 2026-04-06 | **Tests:** 876 passed (+33)

## What Was Built

- `ProductService.get_summary(nm_ids)` — single call returning `ProductSummary` (sales funnel + ad spend + clusters + bids + prices); analytics/prices best-effort
- `ProductSummary`, `CampaignOverview` dataclasses with `to_dict()` for JSON serialization
- `wb product summary --nms <ids> --json` — composite command
- `wb campaign overview --id <id>` — details + budget + stats + per-NM + clusters in one call
- `MutationResult.already_applied: bool` — idempotent retries return `already_applied: true` instead of error
- `CampaignService` lifecycle mutations detect current state; set `already_applied=True` for idempotent retries
- SDK parity: `get_product_summary()`, `get_campaign_overview()`, `rename_campaign()`, `delete_campaign()`, `get_campaign_stats()`, `get_prices()`
