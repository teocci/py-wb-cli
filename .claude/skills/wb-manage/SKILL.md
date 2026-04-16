---
name: wb-manage
description: Direct campaign operations — pause, resume, stop, add/remove products, replenish budget, change placements. Use when you need to act on a specific campaign without full optimization analysis.
triggers:
  - "pause campaign"
  - "resume campaign"
  - "stop campaign"
  - "replenish budget"
  - "add product to campaign"
  - "remove product from campaign"
  - "change placements"
---

# wb-manage

Dispatch table for direct campaign mutations. Use this when you know exactly what action to take (e.g., after a `wb-pulse` alert or a user instruction).

## Actions

### pause

```bash
wb campaign pause <campaign_id> --yes
```

### resume

```bash
# Check budget first — don't resume with empty balance
wb budget get --campaign <campaign_id> --json --compact

# Top up if < 500 RUB
wb budget topup --campaign <campaign_id> --sum <kopecks> --yes

# Start
wb campaign start <campaign_id> --yes
```

### stop

```bash
wb campaign stop <campaign_id> --yes
```

### replenish

```bash
# Convert RUB to kopecks: amount_rub * 100
wb budget topup --campaign <campaign_id> --sum <amount_kopecks> --yes
```

Typical amounts: 1000 RUB = 100000 kopecks, 500 RUB = 50000 kopecks.

### change placements

```bash
wb campaign set-placements <campaign_id> \
  --placements <search|recommendations|search,recommendations> \
  --yes
```

### add product

```bash
wb campaign add-items <campaign_id> --nms <nm_id> --yes
```

Note: one product per campaign is the convention. Only add if intentional.

### remove product

```bash
wb campaign remove-items <campaign_id> --nms <nm_id> --yes
```

## Output

```json
{
  "action": "resume",
  "campaign_id": 123,
  "new_status": "running",
  "budget_remaining_rub": 1500.0
}
```

## When to use vs wb-optimize

- **wb-manage**: you know the action (pulse fired an alert, user said "pause X")
- **wb-optimize**: you need to analyze data and decide what to change
