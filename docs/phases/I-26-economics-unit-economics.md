# Phase I-26 — `wb economics product` (per-product unit economics)

**Version:** 0.47.0 · **Status:** ✅ DONE · **Date:** 2026-06-12 · **Tests:** 1659 passing (31 new; same pre-existing `test_auth_list_empty` env-leak as I-22..I-25)

## Goal

Add a `wb economics` command group whose first command, `wb economics product`, produces a
per-product (per `nm_id`) unit-economics view by **joining** two surfaces that already exist
but are never combined:

- **Stock** — `ReportsService.get_warehouse_top()` → `ProductStockSummary.total_quantity` per
  `nm_id` (warehouse-remains report, analytics token).
- **Settlement costs** — `FinanceService.detailed_sales_reports()` → raw per-row WB settlement
  fields (finance token).

For every product with at least one unit in stock (configurable via `--scope`), it reports:
units in stock, units sold, revenue, average sale price, the WB cost breakdown
(commission / logistics / storage / acquiring), WB's net payout, the total WB cost to sell, and
per-unit economics on both a per-sold and per-held basis, plus optional net profit when a COGS
file is supplied.

Originating plan: [we-need-to-extract-adaptive-penguin.md](../../../../Users/teocci/.claude/plans/we-need-to-extract-adaptive-penguin.md).

## Why now

All the raw inputs are reachable today, but no command joins them. Sellers/agents need a single
call that answers "how much does it cost to sell this product on WB, is it profitable, and how
much stock is left?" without manually correlating `wb report warehouse top` against
`wb finance sales-reports detailed --json`.

## Authoritative field source

`/api/finance/v1/sales-reports/detailed` returns schema `SalesReportsDetailedRes`
([docs/swagger/13-finances.yaml](../../docs/swagger/13-finances.yaml) lines 1098–1188).
Fields are **camelCase** (the snake_case `DetailReportItem` schema in the same file is the
deprecated statistics `reportDetailByPeriod` surface — do not use it).

| Concept | WB key | Type |
|---|---|---|
| article | `nmId` | int |
| vendor code | `vendorCode` | str |
| subject / brand | `subjectName` / `brandName` | str |
| units | `quantity` | int |
| revenue | `retailAmount` | str ₽ |
| net payout | `forPay` | str ₽ |
| commission ₽ / % | `ppvzSalesCommission` / `commissionPercent` | str ₽ / num |
| logistics | `deliveryService` (+ `rebillLogisticCost`) | str ₽ |
| storage | `paidStorage` | str ₽ |
| acquiring | `acquiringFee` | str ₽ |
| sale-vs-return classifier | `docTypeName` / `sellerOperName` (`'Продажа'` = sale) | str |

## Core model (settlement identity — corrected after live test)

A live run against seller 3925272 disproved a naive `revenue − Σ forPay` model (it produced
negative costs). WB's settlement identity, **verified to the kopeck** against the summary
endpoint, is:

```
bank_payment = Σ forPay − Σ logistics − Σ storage − Σ deduction − Σ penalty − Σ acceptance
```

`forPay` is the gross payout on sale rows; logistics/storage/deductions sit on separate
`forPay=0` rows and are subtracted. Logistics attributes per nmId; storage and withholdings are
period-level (no nmId). Two cost modes via one flag:

- **exact (default)** — per-product costs WB ties to the nmId only (commission/acquiring/
  logistics); margin is an upper bound. Period storage+deductions surface in `EconomicsPeriod`.
- **`--apportion`** — folds the period pool into each row pro-rata by revenue (estimate);
  per-product `net_payout` then reconciles to bank payment (`Σ net_payout == bank_payment`).

`wb_cost_total = revenue − net_payout`. Per-sold divides by `units_sold` (sales − returns);
per-held by `units_in_stock` (estimate).

## Steps

1. **constants** — add `ECONOMICS_STOCK_LIMIT = 100_000`, `ECONOMICS_DEFAULT_MIN_STOCK = 1`,
   `ECONOMICS_SALE_OPER = 'Продажа'` in [src/wb/core/constants.py](../../src/wb/core/constants.py).
2. **domain** — `ProductEconomics` + `EconomicsPeriod` dataclasses in
   [src/wb/domain/economics_models.py](../../src/wb/domain/economics_models.py).
3. **service** — `EconomicsService(reports_service, finance_service)` in
   [src/wb/services/economics.py](../../src/wb/services/economics.py): `_Agg` per-nm + `_Pool`
   for nmId-less period costs; `get_product_economics(... , apportion=False) -> (rows, period)`.
4. **factory** — `create_economics_service(profile_name)` in
   [src/wb/services/_factory.py](../../src/wb/services/_factory.py) (reports = analytics token,
   finance = finance token).
5. **CLI** — `economics_app` in [src/wb/cli/economics.py](../../src/wb/cli/economics.py) +
   register in [src/wb/cli/app.py](../../src/wb/cli/app.py). Command `product` with
   `--from/--to/--period/--scope/--apportion/--cogs-file/--min-stock/--all`. Lean table + period
   footer; full JSON list.
6. **tests** — `tests/unit/test_economics_service.py`, `tests/unit/test_cli_economics.py`
   (31 tests; includes the apportion reconciliation invariant).
7. **docs** — `CLAUDE.md` Financial Data Surface row + settlement-identity quirk at phase-complete.

## CLI shape

```text
wb [GLOBAL_FLAGS] economics product --from YYYY-MM-DD --to YYYY-MM-DD [--scope in-stock|sold|all]
   [--apportion] [--cogs-file PATH] [--min-stock N] [--all/--no-all] [--period weekly|daily]
```

## Verification (live, 2026-06-11, profile `3925272_all`)

- Exact: `wb economics product --from 2026-05-01 --to 2026-05-31` → per-SKU margins ~91–98%
  (upper bound); period footer reconciles `359943.80 − 30061.15 − 20499.67 − 62427.36 =
  246955.62 = bank_payment`.
- Apportioned: `… --apportion --json` → `Σ net_payout = 246955.63 ≈ bank_payment` (1-kopeck
  rounding); margins drop to a realistic 62–76% (median 71%).

## Caveats (in `--help`)

- COGS is not in any WB API — margin is WB-fees-only unless `--cogs-file` supplied.
- Under `--apportion`, storage & withholdings are period-level → per-product values are estimates.
- Stock is a current snapshot joined to a historical sales period — per-held is indicative.
- `detailed` finance fetch is throttled 1 req/min; `--all` over a wide range takes minutes.
- Requires two tokens on the profile: analytics (stock) + finance (settlement).
