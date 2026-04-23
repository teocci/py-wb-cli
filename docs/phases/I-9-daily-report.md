# Phase I-9 — Stats Daily-Report (v0.22.0)

**Date:** 2026-04-21

## What Was Built

- `wb stats daily-report [--date YYYY-MM-DD] [--status running]` command
- Joins Promotion API fullstats (ad spend per NM ID per campaign) with Analytics funnel (total platform orders)
- Output: per-product table with `nm_id`, `name`, `ad_spend`, `total_orders`
- `wb-daily-report` Claude Code skill

## Implementation Notes

- `ad_spend` aggregated across all campaigns containing each product for the given date
- `total_orders` from `analytics sales-funnel products` (all channels: organic + advertising)
- If analytics token unavailable, `total_orders = 0` with a note in output
- Rate limits: `EP_CAMPAIGN_FULLSTATS` (1/20s) + `EP_FUNNEL_PRODUCTS` (3/min) — CLI rate limiter handles both
