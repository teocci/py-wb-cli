# F-23 — Warehouse-remains stock double-count

**Status:** ✅ DONE
**Version:** 0.47.1 · **Date:** 2026-06-14 · **Tests:** 1660/1661 (1 new; 1 pre-existing env-leak)
**Scope:** `src/wb/services/reports.py`

## Symptom

`wb economics product` reports inflated `units_in_stock`. Live example: nmId `189923770`
has **65** real units (sum of stock across available warehouses) but the command shows
roughly double.

## Root cause

The WB `/api/v1/warehouse_remains` download returns, inside each item's `warehouses[]`
list, a **synthetic aggregate row** `Всего находится на складах` ("Total located in
warehouses") plus `В пути…` (in-transit) rows, alongside the real per-warehouse entries.

`_aggregate_top()` summed **every** entry, adding the `Всего` total on top of the real
quantities → double count. The sibling `_compute_runway_item()` already filtered these via
`EXCLUDED_WAREHOUSE_PREFIXES = ('В пути', 'Всего')` but the rule was inline and not shared.

## Fix

Extract the exclusion rule into one module-level helper `_physical_warehouses(item)` and use
it in **both** `_aggregate_top()` and `_compute_runway_item()` — fixes the bug and removes
the inline duplication. No new parameters / query surface (YAGNI): the `Всего` aggregate is
never a real warehouse, and both current callers want physical-only stock.

## Files changed

| File | Change |
|------|--------|
| `src/wb/services/reports.py` | Add `_physical_warehouses()` helper; call it from `_aggregate_top()` (the bug fix) and replace the inline filter in `_compute_runway_item()` (removes duplication) |
| `tests/unit/test_reports_service.py` | New `test_excludes_synthetic_and_transit_rows` regression test |

## Live verification

`wb --profile 3925272_personal --json report warehouse top --no-cache` for nmId
`189923770` returned `total_quantity = 65` with the per-warehouse breakdown summing
exactly (6 + 15 + 19 + 24 + 1 = 65) and the synthetic `Всего находится на складах` /
`В пути` rows correctly excluded. Before the fix this nmId reported ~double.

The same `_aggregate_top` path feeds `economics product` → `units_in_stock`, so the
economics command is fixed by the same change.
