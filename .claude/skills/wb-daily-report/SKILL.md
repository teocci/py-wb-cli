---
name: wb-daily-report
description: Per-product daily report combining advertising spend and total platform orders. Run to see SKU-level cost vs. orders for any date (default yesterday). Requires analytics token for total orders.
triggers:
  - "daily report"
  - "advertising cost and orders"
  - "spend and orders by product"
  - "how much did I spend and how many orders"
  - "yesterday's report"
---

# wb-daily-report

Per-product advertising cost vs. total orders for a given date. Standard output combines Promotion API spend data with Analytics funnel order counts.

## Source contract

- `ad_spend` / `advertising_costs` come from `wb stats product-spend` and are aggregated by NM ID for the requested date.
- `total_orders` / `orders` come from `wb analytics sales-funnel products` and specifically use `order_count`.
- These `orders` are not the same metric as a WB sales report export (`отчет по продажам`).
- If the user asks for sales report orders, references `отчет по продажам`, or brings a reconciliation sheet against a sales report export, state that the standard daily-report output is a funnel-orders report unless a sales-report-specific source is used.
- Always label the output as `sales-funnel orders` unless the user explicitly asked for another orders source.

## Usage

`--json` is a **global** flag on the root `wb` command and must come **before** the subcommand.

```bash
# Composite (preferred when it fits the source contract above)
wb --json stats daily-report --date YYYY-MM-DD

# Yesterday, default status filter (active = running + paused)
wb --json stats daily-report

# Only running campaigns, specific date
wb --json stats daily-report --date YYYY-MM-DD --status running

# Two-step workflow — pull orders then spend separately
wb --json --compact analytics sales-funnel products --from YYYY-MM-DD --to YYYY-MM-DD --all
wb --json --compact stats product-spend --nms <comma-separated-nm-ids> --from YYYY-MM-DD --to YYYY-MM-DD

# Table output (omit --json)
wb stats daily-report --date YYYY-MM-DD
```

## Running the skill

1. **Pre-flight rate check.** This workflow makes 3+ API calls across two services. Before starting, run `wb --json rate status`:
   - If `locked: true`, sleep `seller_cooldown_seconds + 5` and retry; do NOT start the workflow during an active cooldown (it would waste one of its calls on a 429 that extends the lock).
   - If `locked: false`, proceed directly; no need to probe unless you suspect an external tool tripped the throttle, in which case `wb --json rate probe` gives the authoritative answer in one call.
2. Resolve yesterday's date: `python -c "from datetime import date, timedelta; print(date.today() - timedelta(days=1))"`
3. Prefer the composite command: `wb --json stats daily-report --date YYYY-MM-DD`.
4. If composite rate-limits or fails, fall back to the two-step workflow:
   - Orders: `wb --json --compact analytics sales-funnel products --from YYYY-MM-DD --to YYYY-MM-DD --all`
   - Spend (same NM IDs): `wb --json --compact stats product-spend --nms <ids> --from YYYY-MM-DD --to YYYY-MM-DD`
5. Immediately save each raw response before further parsing:
   - `reports/daily/orders_YYYY-MM-DD_raw.json`
   - `reports/daily/product_spend_YYYY-MM-DD_raw.json`
   - `reports/daily/daily_report_YYYY-MM-DD_raw.json` containing both payloads plus artifact metadata
6. If the same date/report request is repeated, check for these saved artifacts first and reuse them unless the user explicitly asks for a fresh pull.
7. On rate-limit failures after one side has already been saved, reuse the saved raw JSON instead of restarting the whole workflow.
8. Merge on `nm_id` only; never merge by product name.
9. Verify the merged `orders` exactly match the raw `order_count` payload and `advertising_costs` exactly match the raw `spend` payload before presenting results.
10. Label the output so the user can tell that `orders` means `sales-funnel order_count`.
11. Parse and format as a markdown table ranked by `ad_spend` descending.
12. Flag any products where `ad_spend > 0` but `total_orders == 0` — these may indicate budget waste or attribution lag.

## What it returns

JSON keys stay short and code-friendly (`total_orders`); the rendered table uses the disambiguated column label `Sales-Funnel Orders`.

```json
[
  {
    "nm_id": 34659218,
    "name": "Духи Strawberry сладкие стойкие Клубника 14 мл.",
    "ad_spend": 1250.00,
    "total_orders": 223
  },
  {
    "nm_id": 177672640,
    "name": "Духи Caramel карамель сладкие 14 мл.",
    "ad_spend": 980.50,
    "total_orders": 191
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

| SKU | Product Name | Ad Spend ₽ | Sales-Funnel Orders |
|-----|--------------|------------|---------------------|
| 34659218 | Духи Strawberry... | 1250.00 | 223 |
| 177672640 | Духи Caramel... | 980.50 | 191 |

## Notes

- **Sales-Funnel Orders** come from the Analytics funnel API (`sales-funnel/products`, `order_count`) and include all channels (organic + advertising). Requires an analytics token with standard Analytics scope.
- Sales-funnel `order_count` may not match a WB sales report export row-for-row.
- If the analytics token is missing or has insufficient scope, `total_orders` will be 0 for all rows and the table title should note the fallback.
- **Ad spend** is aggregated across all campaigns containing each product for the given date.
- Products with `total_orders = 0` when analytics is available may indicate the product had no orders that day (not a data error).
- Rate limits: `EP_CAMPAIGN_FULLSTATS` (1/20s) and `EP_FUNNEL_PRODUCTS` (3/min) are enforced by the CLI rate limiter — no sleeps needed. Batch spend lookups conservatively for larger daily reports.
- For a date with 50+ active products, allow ~60–90 s for the composite command to complete.
- When a user asks for another slice of the same date, prefer reusing saved raw JSON over rerunning the WB endpoints.

## Typical daily workflow integration

1. `wb-assess` → check balance and campaign health
2. `wb-daily-report` → review yesterday's cost-per-order by product
3. `wb-optimize` → adjust bids for campaigns with poor cost efficiency
