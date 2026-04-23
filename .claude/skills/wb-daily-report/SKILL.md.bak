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

Per-product advertising cost vs. total orders for a given date. Combines Promotion API spend data with Analytics funnel order counts.

## Usage

```bash
# Yesterday's report (default)
wb stats daily-report --json

# Specific date
wb stats daily-report --date 2026-04-19 --json

# Table output
wb stats daily-report --date 2026-04-19

# Only running campaigns
wb stats daily-report --date 2026-04-19 --status running
```

## What it returns

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

## Running the skill

1. Resolve yesterday's date: `python -c "from datetime import date, timedelta; print(date.today() - timedelta(days=1))"`
2. Run the command: `wb stats daily-report --date YYYY-MM-DD --json`
3. Parse the JSON and format as a markdown table ranked by `ad_spend` descending
4. Flag any products where `ad_spend > 0` but `total_orders == 0` — these may indicate budget waste or attribution lag

## Output table format

| SKU | Product Name | Ad Spend ₽ | Total Orders |
|-----|-------------|-----------|-------------|
| 34659218 | Духи Strawberry... | 1250.00 | 223 |
| 177672640 | Духи Caramel... | 980.50 | 191 |

## Notes

- **Total orders** come from the Analytics funnel API (`sales-funnel/products`) and include all channels (organic + advertising). Requires an analytics token with standard Analytics scope.
- If the analytics token is missing or has insufficient scope, `total_orders` will be 0 for all rows and the table title will note the fallback.
- **Ad spend** is aggregated across all campaigns containing each product for the given date.
- Products with `total_orders = 0` when analytics is available may indicate the product had no orders that day (not a data error).
- Rate limits: `EP_CAMPAIGN_FULLSTATS` (1/20s) and `EP_FUNNEL_PRODUCTS` (3/min) are enforced by the CLI rate limiter — no sleeps needed.
- For a date with 50+ active products, allow ~60-90s for the command to complete.

## Typical daily workflow integration

1. `wb-assess` → check balance and campaign health
2. `wb-daily-report` → review yesterday's cost-per-order by product
3. `wb-optimize` → adjust bids for campaigns with poor cost efficiency
