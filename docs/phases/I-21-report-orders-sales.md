# Phase I-21 — `wb report orders` + `wb report sales` (Statistics API wrappers)

**Version:** 0.42.0 · **Date:** 2026-05-26 · **Tests:** 1471 passing (18 new, 1 pre-existing failure in `test_auth_list_empty`)

## Goal

Surface two Statistics API endpoints that the CLI already advertises but never wrapped:

- `GET /api/v1/supplier/orders` — every ordered item line (operational stream)
- `GET /api/v1/supplier/sales` — every paid sale or return

[src/wb/cli/report.py:13](../../src/wb/cli/report.py) literally claims `'Reports (warehouse remains, orders, sales)'` in its help string, but only `warehouse` exists as a subcommand. This phase closes the gap.

## Why now

User question on 2026-05-26: *"how do I get all orders for each product (only products with orders) for yesterday?"*. Existing answers are unsatisfying:

- `wb stats daily-report` is campaign-driven — it misses every SKU that sells organically without an active ad campaign.
- `wb analytics sales-funnel products` is pre-aggregated — drops per-order fields (`srid`, `warehouseName`, `regionName`, `isCancel`, `finishedPrice`) that agents need for region-level / cancel-state / individual-price reasoning.

The orders endpoint is the right primitive: every per-order WB field is preserved, so agents can aggregate / filter / correlate downstream.

## Steps

1. **constants** — add `EP_STATISTICS_ORDERS = '/api/v1/supplier/orders'` to [src/wb/core/constants.py](../../src/wb/core/constants.py) (next to existing `EP_STATISTICS_SALES`) + export from `__all__`.
2. **rate-limits** — add `EP_STATISTICS_ORDERS: (1, 60.0)` and `EP_STATISTICS_SALES: (1, 60.0)` to `ENDPOINT_LIMITS` in [src/wb/core/rate_limits.py](../../src/wb/core/rate_limits.py). Swagger docs them at 1/min, burst 1.
3. **client** — add `StatisticsClient.get_orders(date_from, flag=1)` to [src/wb/client/statistics.py](../../src/wb/client/statistics.py) mirroring the existing `get_sales` signature (raw `list[dict]` return).
4. **CLI** — add `report orders` and `report sales` Typer commands to [src/wb/cli/report.py](../../src/wb/cli/report.py). Options:
   - `--date YYYY-MM-DD` (default: yesterday, uses `flag=1`)
   - `--since YYYY-MM-DD[THH:MM]` (uses `flag=0`, mutually exclusive with `--date`)
   - `--flag 0|1` (raw override, mutually exclusive with `--date`/`--since`)
   - `--exclude-cancelled` (orders only — drops `isCancel=true`)
   - `--by-product` (client-side aggregation by `nmId`)
5. **factory** — add `create_statistics_client(profile)` helper to [src/wb/services/_factory.py](../../src/wb/services/_factory.py) (CLI doesn't need the full ReportsService for these direct read-throughs).
6. **tests** — extend [tests/unit/test_cli_report.py](../../tests/unit/test_cli_report.py) (create if absent) with mocked-HTTP cases: default-yesterday resolution, `--flag` pass-through, `--exclude-cancelled`, `--by-product` aggregation, JSON shape.

## Out of scope

- No `OrderRecord` / `SaleRecord` dataclass — keep WB field passthrough lossless (matches existing `get_sales` pattern).
- No incremental-cursor automation. Agents drive the `flag=0` cursor themselves with the documented `lastChangeDate` pattern.
- No new analytics command — sales-funnel already covers that surface.

## CLI shape (final)

```text
wb [GLOBAL_FLAGS] report orders [--date | --since | --flag] [--exclude-cancelled] [--by-product]
wb [GLOBAL_FLAGS] report sales  [--date | --since | --flag]                       [--by-product]
```

Global flags (`--json`, `--compact`, `--profile`, `--fields`, `--no-cache`, `--verbose`, `--quiet`) are declared on the app callback and must precede the subcommand chain.

## Verification

- `pytest tests/unit/test_cli_report.py -v` → 28 passed (18 new).
- `pytest tests/unit/ -q` → 1471 passed, 1 pre-existing failure (`test_auth_list_empty`, same env-leak as v0.40.1 / v0.41.0).
- Live against `25169_personal` profile, 2026-05-25:
  - `wb --json report orders --date 2026-05-25 --exclude-cancelled --by-product` returned 147 products with orders, 1,980 total uncancelled orders, 1,980,054.10 ₽ revenue.
  - Top SKU: nmID 4959738 (CITY PARFUM, Духи) — 234 orders, 204,047.86 ₽.
  - Each per-product record exposes deduped `warehouses[]` and `regions[]` arrays so agents can filter by fulfillment location without re-fetching raw rows.

## Files changed

| File | Change |
|------|--------|
| `src/wb/core/constants.py` | New `EP_STATISTICS_ORDERS = '/api/v1/supplier/orders'` + `__all__` export. |
| `src/wb/core/rate_limits.py` | Added both `EP_STATISTICS_ORDERS` and `EP_STATISTICS_SALES` to `ENDPOINT_LIMITS` at `(1, 60.0)` — swagger documents 1/min, burst 1 for both. Sales had been silently unrate-limited until now (it was used internally by `stock-runway`); both now share the throttle. |
| `src/wb/core/cache_policy.py` | Added both endpoints to `CACHEABLE_ENDPOINTS` (60 s TTL = the rate-limit interval). |
| `src/wb/client/statistics.py` | New `StatisticsClient.get_orders(date_from, flag=1)`. Returns raw `list[dict]` for lossless WB field passthrough — matches the existing `get_sales` shape and avoids field-drift bugs if WB adds new fields. |
| `src/wb/services/_factory.py` | `create_statistics_client()` now wires `with_rate_limits=True` + token-type-aware prior. The previously-pure HTTP client (used by `stock-runway`'s sales call) now participates in the shared `EndpointBudget`. |
| `src/wb/cli/report.py` | Two new Typer commands: `report orders` and `report sales`. Shared helpers: `_resolve_orders_query()` (date-mode mutual-exclusion + flag mapping), `_aggregate_by_product()` (client-side per-nmId roll-up returning order_count, cancelled_count, total_revenue, total_for_pay, warehouses[], regions[]). |
| `tests/unit/test_cli_report.py` | 18 new tests across 4 classes: `TestReportOrdersDateResolution` (6), `TestReportOrdersOutput` (6), `TestReportSales` (2), `TestResolveOrdersQuery` (4). |

## Notes for AI agents

- **`flag=1` is the daily snapshot.** Default for `--date <YYYY-MM-DD>` (or no flags → yesterday). No row cap, time portion of `dateFrom` ignored.
- **`flag=0` is the incremental cursor.** Auto-selected by `--since <timestamp>`. Capped at ~80,000 rows; on subsequent calls feed the response's last `lastChangeDate` back in as `--since`.
- **Cache:** 60 s HTTP-layer TTL aligned with the WB 1/min budget — same-minute re-runs return the cached payload instead of waiting on the throttle.
- **Field projection:** use `--fields a,b,c` (global flag — must precede the subcommand) to keep only the columns you need from the JSON output. Works on both raw and `--by-product` shapes.
- **`forPay` is sales-only.** Orders carry `priceWithDisc` and `finishedPrice` but `forPay` is populated only for confirmed sales — the `--by-product` aggregator computes it from whatever rows it gets, so `wb report orders --by-product` will show `total_for_pay: 0.0`. Use `wb report sales --by-product` when you need the payout side.
