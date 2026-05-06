---
name: wb-daily-report
description: Per-product daily report combining advertising spend and total platform orders. Run to see SKU-level cost vs. orders for any date or range (default yesterday). Requires analytics token for funnel fields.
triggers:
  - "daily report"
  - "advertising cost and orders"
  - "spend and orders by product"
  - "how much did I spend and how many orders"
  - "yesterday's report"
---

# wb-daily-report

Per-product advertising cost vs. total orders for a given date or range. The default JSON shape carries the full funnel + spend bundle.

> **Base-token sellers (R-5+):** the per-product breakdown chains `EP_CAMPAIGN_FULLSTATS` (1/h Base) per active campaign batch and `EP_FUNNEL_PRODUCTS` (2/h Base, 30-min interval). For 5+ active campaigns, expect 30-min-plus wall time on Base. The response cache short-circuits past-day reruns — always prefer `reports/daily/*_raw.json` reuse on Base before triggering a fresh run.

## Source contract

- `spend` / `advertising_costs` come from `wb stats product-spend` and are aggregated by NM ID for the requested date(s).
- `orders` come from `wb analytics sales-funnel products` and specifically use `order_count`.
- These `orders` are not the same metric as a WB sales report export (`отчет по продажам`).
- If the user asks for sales report orders, references `отчет по продажам`, or brings a reconciliation sheet against a sales report export, state that the standard daily-report output is a funnel-orders report unless a sales-report-specific source is used.
- Always label the output as `sales-funnel orders` unless the user explicitly asked for another orders source.

## Usage

`--json` is a **global** flag on the root `wb` command and must come **before** the subcommand.

Date modes are mutually exclusive. All dates must be strictly before today (24-hour settle window, no override).

```bash
# Yesterday (default)
wb --json stats daily-report

# Single past date
wb --json stats daily-report --date YYYY-MM-DD

# Last 7 days (relative, ends yesterday)
wb --json stats daily-report --days 7

# Absolute range (max 7 days inclusive)
wb --json stats daily-report --from YYYY-MM-DD --to YYYY-MM-DD

# Status filter (default: active = running + paused)
wb --json stats daily-report --date YYYY-MM-DD --status running

# Legacy narrow shape (4 keys only)
wb --json stats daily-report --date YYYY-MM-DD --fields nm_id,name,spend,orders

# Table output (omit --json)
wb stats daily-report --date YYYY-MM-DD
```

## Running the skill

1. **Pre-flight rate check.** This workflow makes 3 API calls. Before starting, run `wb --json rate status`:
   - If any endpoint shows `locked: true`, sleep `reset_in_s + 5` and retry; do NOT start the workflow during an active cooldown.
   - If everything shows `locked: false`, proceed directly.
2. Resolve yesterday's date: `python -c "from datetime import date, timedelta; print(date.today() - timedelta(days=1))"`
3. Prefer the composite command: `wb --json stats daily-report --date YYYY-MM-DD`.
4. If composite rate-limits or fails, fall back to the two-step workflow:
   - Orders: `wb --json --compact analytics sales-funnel products --from YYYY-MM-DD --to YYYY-MM-DD --all`
   - Spend (same NM IDs): `wb --json --compact stats product-spend --nms <ids> --from YYYY-MM-DD --to YYYY-MM-DD`
5. Immediately save each raw response before further parsing:
   - `reports/daily/daily_report_YYYY-MM-DD_full.json` (single-date) or `daily_report_FROM_to_TO_full.json` (range)
6. If the same date/report request is repeated, check for these saved artifacts first and reuse them unless the user explicitly asks for a fresh pull.
7. On rate-limit failures, reuse the saved raw JSON instead of restarting the whole workflow.
8. Label the output so the user can tell that `orders` means `sales-funnel order_count`.
9. Parse and format as a markdown table ranked by `spend` descending.
10. Flag any products where `spend > 0` but `orders == 0` — these may indicate budget waste or attribution lag.

## Backfill (missed days)

The script supports multi-day backfill in a single run — total WB calls stay at 3 regardless of range width (within the 7-day cap).

```bash
# Last 3 days (relative, ending yesterday)
python scripts/generate_daily_wb_report.py --days 3

# Absolute range
python scripts/generate_daily_wb_report.py --from 2025-04-29 --to 2025-05-05
```

Range-named artifacts and CSVs are written:
- `reports/daily/daily_report_FROM_to_TO_full.json`
- `reports/daily/orders_FROM_to_TO_by_nm.csv`
- `reports/daily/ad_costs_FROM_to_TO_merged.csv`

Range CSVs aggregate metrics across all days in the period — one row per campaign-NM pair, not one per day. If you need per-date breakdowns, run per-date (with N×cooldown cost on Base).

## What it returns

Full 11-field shape per product. For the 4-key legacy narrow path, add `--fields nm_id,name,spend,orders`.

```json
[
  {
    "nm_id": 34659218,
    "name": "Духи Strawberry сладкие стойкие Клубника 14 мл.",
    "views": 12400,
    "clicks": 620,
    "ad_orders": 47,
    "spend": 1250.00,
    "avg_position": 3.2,
    "opens": 5800,
    "cart_adds": 410,
    "orders": 223,
    "order_sum": 111500,
    "buyouts": 198
  },
  {
    "nm_id": 177672640,
    "name": "Духи Caramel карамель сладкие 14 мл.",
    "views": 9100,
    "clicks": 455,
    "ad_orders": 38,
    "spend": 980.50,
    "avg_position": 4.1,
    "opens": 4200,
    "cart_adds": 310,
    "orders": 191,
    "order_sum": 95500,
    "buyouts": 172
  }
]
```

## Reconciliation guardrails

- If a user compares the output to a WB sales report export and sees order mismatches, treat that first as a source mismatch check, not a merge bug.
- If a user compares the output to another ad-cost report and only sees small fractional differences, check whether the other report rounds to whole rubles before calling it an error.
- Only call it a calculation bug if the final CSV differs from the raw WB payloads used to build it.
- Saving raw payload artifacts is mandatory for this skill because the underlying calls are rate-limited and expensive to reproduce.
- Treat existing raw JSON for the same date as a first-class cache for follow-up questions like "include orders too", "split by search/manual", or reconciliation against another export.

## Output table format

| SKU | Product Name | Spend ₽ | Views | Clicks | Ad Orders | Avg Pos | Opens | Cart | Orders | Order Sum | Buyouts |
|-----|--------------|---------|-------|--------|-----------|---------|-------|------|--------|-----------|---------|
| 34659218 | Духи Strawberry... | 1250.00 | 12400 | 620 | 47 | 3.2 | 5800 | 410 | 223 | 111500 | 198 |

## Notes

- **orders** = Sales-Funnel orders from Analytics funnel API (`sales-funnel/products`, `order_count`), all channels (organic + advertising). Requires an analytics token with standard Analytics scope.
- **ad_orders** = Orders attributed to advertising from the Promotion API fullstats. Different metric from `orders`.
- Sales-funnel `order_count` may not match a WB sales report export row-for-row.
- If the analytics token is missing or has insufficient scope, all funnel fields (`opens`, `cart_adds`, `orders`, `order_sum`, `buyouts`) will be 0 for all rows.
- **spend** is aggregated across all campaigns containing each product for the given date(s).
- Products with `orders = 0` when analytics is available may indicate the product had no orders that day (not a data error).
- Date range max: 7 days inclusive. Funnel call covers the whole range in a single call; no per-day breakdown in range mode.
- Rate limits: `EP_CAMPAIGN_FULLSTATS` (1/20s) and `EP_FUNNEL_PRODUCTS` (3/min) are enforced by the CLI rate limiter — no sleeps needed.

## Typical daily workflow integration

1. `wb-assess` → check balance and campaign health
2. `wb-daily-report` → review yesterday's cost-per-order by product
3. `wb-optimize` → adjust bids for campaigns with poor cost efficiency
