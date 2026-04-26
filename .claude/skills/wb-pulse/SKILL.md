---
name: wb-pulse
description: Intraday campaign health check using real-time endpoints. Detects bid drift, budget depletion, and campaign pauses. Run every 1-2 hours during business hours. Requires wb-assess to have run first today (to establish bid baselines).
triggers:
  - "check campaigns"
  - "intraday check"
  - "bid drift"
  - "is budget okay"
  - "are campaigns running"
---

# wb-pulse

Intraday health check. Uses **real-time endpoints only** — bid recommendations, budget balance, and campaign status. No analytics (those are hourly/30-min lag — use wb-assess for trend data).

> **Base-token sellers (R-5+):** the bid-recommendations leg costs one Base bucket call per campaign at a 3-min interval (20/h). For 7 campaigns the bid-recommend phase alone is ~21 min. The campaign-info and budget-balance legs each consume a 1/h Base bucket — running pulse twice in the same hour will block on those buckets, not on the bid-recommend interval. Check `wb rate status` between pulses; do not loop pulse on Base.

## Usage

```bash
# Check specific campaigns
wb pulse --campaigns 123,456,789 --json --compact

# Single campaign
wb pulse --campaigns 123 --json --compact
```

## Alert codes and actions

| Alert | Meaning | Action |
|-------|---------|--------|
| `competitor_surge` | Bid recommendations jumped >15% since morning | Consider raising bids: `wb bid set-items --campaign <id> --bids '[...]' --yes` |
| `budget_low` | Balance < 500 RUB or < 20% of morning balance | Replenish: `wb budget topup --campaign <id> --sum <kopecks> --yes` |
| `campaign_paused` | Campaign auto-paused (budget exhausted) | Replenish then resume: `wb budget topup... && wb campaign start <id> --yes` |
| `bid_floor_rising` | Minimum bids up >10% since morning | Verify current bids are still above minimum: `wb bid minimum --campaign <id>` |

## Output

```json
{
  "timestamp": "2026-04-17T14:30:00+00:00",
  "campaigns": [
    {
      "campaign_id": 123,
      "nm_id": 789,
      "status": "running",
      "budget_remaining_rub": 340.0,
      "bid_recommend_rub": 25.0,
      "bid_recommend_drift_pct": 18.5,
      "bid_floor_drift_pct": 2.1,
      "alerts": ["competitor_surge", "budget_low"]
    }
  ],
  "action_needed": true
}
```

## Context: time of day

- **12-17h peak hours**: bid drift >15% may be normal daily demand peak, not necessarily competitors. Compare against previous pulse readings before reacting.
- **Morning (9-11h)**: competitor_surge here is more meaningful (bidding war at campaign start).
- **Evening (18h+)**: budget_low alerts are expected — less urgent unless campaign should run overnight.

## Prerequisites

`wb-assess` must have run today (full mode, not `--quick`) to establish baselines. Without a baseline, `bid_recommend_drift_pct` will be 0.0 and `competitor_surge` cannot fire.
