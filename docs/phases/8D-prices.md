# Phase 8D — Prices & Discounts Command (v0.13.0)

**Date:** 2026-04-06 | **Tests:** 764 passed (+28)

## Problem

During a live agent session, `wb portal products` only returned base price. The agent had to bypass the CLI and call `discounts-prices-api.wildberries.ru` directly to get discount % and final price.

## What Was Built

- `PRICES_BASE_URL`, `EP_PRICES_GOODS_FILTER` constants
- `ProductPriceSize`, `ProductPrice` domain models with `base_price`, `final_price`, `club_price` properties
- `PricesClient` (`client/prices.py`): `list_goods(limit, offset, filter_nm_id)`
- `PricesService` (`services/prices.py`): `get_prices()` with auto-pagination + client-side filter
- `wb prices list [--nm-ids ...] [--min-discount N]` CLI command

## Output Format

```
┌───────────────┬─────────────┬────────────┬──────────┬─────────────┬──────────┐
│        NM ID  │ Vendor Code │ Base Price │ Discount │ Final Price │ Currency │
```
Club Price column appears automatically when any product has a WB Club discount.
