# Phase 8B — Stock Runway (v0.11.0)

**Date:** 2026-04-04 | **Tests:** 716 passed (+31)

## What Was Built

- `client/statistics.py`: `StatisticsClient` wrapping `statistics-api.wildberries.ru/api/v1/supplier/sales`
- `domain/report_models.py` additions: `SaleRecord`, `WarehouseRunway`, `StockRunwayItem`, `StockRunwayReport`
- `services/reports.py` additions: `get_stock_runway()` + helpers:
  - `_build_velocity_map()` — avg daily sales + sale-day counts per `nm_id`
  - `_compute_runway_item()` — per-warehouse days-of-stock
  - `_runway_alert()` — critical (≤7d) / low (≤14d) classification
  - `_runway_confidence()` — high/medium/low/none based on observed sale-days
  - Transit warehouse exclusion (`'В пути'`, `'Всего'` prefixes filtered)
- `wb report warehouse stock-runway [--days 30]` CLI command

## Usage

```bash
wb report warehouse stock-runway --days 30 --json
```
