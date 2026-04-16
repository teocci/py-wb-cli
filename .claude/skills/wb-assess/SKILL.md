---
name: wb-assess
description: Morning account snapshot — balance, campaign status, and 7-day product spend. Run this first each day before making any decisions. Also saves bid baselines for wb-pulse intraday drift detection.
triggers:
  - "what's the state"
  - "morning check"
  - "account snapshot"
  - "how are campaigns doing"
---

# wb-assess

Morning situational awareness. Run this once per day (or any time you need a current state snapshot) before using wb-optimize or wb-launch.

## Usage

```bash
# Full snapshot (balance + campaigns + 7-day product spend — takes ~20-25s due to rate limit)
wb assess --json --compact

# Quick snapshot (no product spend — fast, under 5s)
wb assess --quick --json --compact

# With single-product detail
wb assess --nm <nm_id> --json --compact
```

## What it returns

```json
{
  "data_as_of": "2026-04-17T09:00:00+00:00",
  "balance_rub": 5420.0,
  "running": [{"campaign_id": 123, "name": "[steady_low_cost] Dress A", "status": "running", "nm_id": 789}],
  "paused": [],
  "ready": [],
  "product_spend_7d": [{"nm_id": 789, "spend": 840.0, "views": 1200, "clicks": 50, "orders": 10}]
}
```

## Notes

- **Saves bid baselines** to `~/.wb-cli/pulse_baseline.json` when running full mode (not `--quick`). wb-pulse uses these to detect intraday drift.
- Data freshness: balance and campaign status are real-time; product spend is updated hourly by WB.
- Run `--quick` when you only need a fast status check and don't need spend data.

## Typical daily workflow

1. `wb assess --json --compact` → understand current state
2. `wb-optimize` for running campaigns that need bid tuning
3. `wb-pulse` every 1-2 hours during business hours for intraday monitoring
