---
name: wb-optimize
description: Daily bid and budget optimization for a running campaign. Reads 7-day analytics, compares against bid recommendations, and applies adjustments. Run after wb-assess each morning for campaigns that are running.
triggers:
  - "optimize campaign"
  - "adjust bids"
  - "tune bids"
  - "optimize bids"
  - "campaign performance"
---

# wb-optimize

Daily bid and budget tune-up for a running campaign. Uses analytics + bid recommendations to decide whether to raise, lower, or hold bids and whether to top up budget.

## Input

`campaign_id` — the campaign to optimize.

## Steps

### 1. Ensure wb-assess ran today

If not, run it first:
```bash
wb assess --quick --json --compact
```

### 2. Pull 7-day analytics

```bash
wb stats campaign --id <campaign_id> \
  --from <date_7_days_ago> --to <today> \
  --json --compact
```

Key metrics to read: `views`, `clicks`, `ctr`, `spend_rub`, `orders`, `cpc_rub`.

### 3. Get bid recommendations and minimums

```bash
wb bid recommend --campaign <campaign_id> --json --compact
wb bid minimum --campaign <campaign_id> --json --compact
```

### 4. Get optimize plan

```bash
wb optimize plan --campaign <campaign_id> \
  --from <date_7_days_ago> --to <today> \
  --json --compact
```

### 5. Decide: raise / lower / hold

| Signal | Action |
|--------|--------|
| CTR < 1% AND spend growing | Lower bids 10-15% |
| CTR > 3% AND orders low | Check placements — bids may be fine, keywords need review (`wb-keywords`) |
| `competitor_surge` alert fired today | Raise bids to match recommendation |
| Bid below minimum | Raise to minimum immediately |
| Budget depleted before 18h | Increase daily budget by 20-30% |

Round bid changes to nearest 5 RUB. Never bid below minimum.

### 6. Apply changes

```bash
# Bid adjustment (only if changes decided)
wb bid set-items --campaign <campaign_id> \
  --bids '[{"nm": <nm_id>, "bid": <new_bid_kopecks>}]' \
  --yes

# Budget top-up (only if balance < 500 RUB or < 1 day of spend)
wb budget topup --campaign <campaign_id> --sum <kopecks> --yes
```

### 7. Output

```json
{
  "campaign_id": 123,
  "bids_changed": true,
  "old_bid_rub": 20.0,
  "new_bid_rub": 25.0,
  "budget_topped_up": false,
  "ctr_7d": 2.1,
  "spend_7d_rub": 840.0,
  "next": "check results in 1h via wb-pulse"
}
```

## Notes

- Do not optimize the same campaign twice in one day without new intraday data from `wb-pulse`.
- If CTR is low and keywords look healthy, check placements — consider running `wb-keywords` next.
- Revenue (`orders`) lags up to 24h in analytics — yesterday's orders may not yet appear today.
