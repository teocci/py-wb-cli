---
name: wb-launch
description: Create and start a new advertising campaign for one product. Reads strategy rules from ~/.wb-cli/rules.json. Requires goal, nm_id, product_name, budget_rub. Campaign name must follow [goal] format for wb-calibrate grouping.
triggers:
  - "launch campaign"
  - "create campaign"
  - "new campaign"
  - "start advertising"
---

# wb-launch

Create, fund, and start a campaign for a single product. Uses strategy rules from `~/.wb-cli/rules.json` to select payment type and placements.

## Inputs

| Field | Example | Notes |
|-------|---------|-------|
| `goal` | `steady_low_cost` | One of: `new_product_visibility`, `volume_sales`, `steady_low_cost`, `brand_defense` |
| `nm_id` | `789` | Product article ID |
| `product_name` | `Dress A` | Human-readable, used in campaign name |
| `budget_rub` | `2000` | Initial budget in rubles |

## Goals quick-reference

| Goal | When to use |
|------|-------------|
| `new_product_visibility` | New product, needs reviews and first orders |
| `volume_sales` | Proven product, maximize order volume |
| `steady_low_cost` | Stable product, minimize CPC, no rush |
| `brand_defense` | Own brand keywords under competitor pressure |

## Steps

### 1. Read strategy rules

```bash
cat ~/.wb-cli/rules.json
```

Extract settings for `<goal>`: `payment_type`, `placements`, `bid_percentile`, `validated`, `confidence`.

**If `confidence = "low"`**: warn the user — rules are unvalidated defaults, not empirically calibrated. Proceed on confirmation only.

**If `~/.wb-cli/rules.json` does not exist**: copy the template first:
```bash
cp .claude/skills/wb-launch/rules.json ~/.wb-cli/rules.json
```

### 2. Get bid recommendation

```bash
wb bid minimum --json --compact
```

For `new_product_visibility` and `volume_sales`: target bid at `bid_percentile` of the recommendation range.
For `steady_low_cost` and `brand_defense`: use minimum bid as starting point.

### 3. Create campaign (dry-run first)

```bash
wb campaign create \
  --name "[<goal>] <product_name>" \
  --nms <nm_id> \
  --placements <placements_from_rules> \
  --payment-type <payment_type_from_rules> \
  --dry-run
```

Show dry-run output to the user. Confirm before proceeding.

### 4. Execute: create → fund → start

```bash
# Create
wb campaign create \
  --name "[<goal>] <product_name>" \
  --nms <nm_id> \
  --placements <placements> \
  --payment-type <payment_type> \
  --yes

# Fund (convert budget_rub to kopecks: rub * 100)
wb budget topup --campaign <campaign_id> --sum <budget_kopecks> --yes

# Start
wb campaign start <campaign_id> --yes
```

### 5. Output

```json
{
  "campaign_id": 123456,
  "name": "[steady_low_cost] Dress A",
  "goal": "steady_low_cost",
  "payment_type": "cpc",
  "placements": ["recommendations"],
  "bid_percentile": 50,
  "budget_rub": 2000.0,
  "confidence": "low",
  "note": "Analytics available in ~1h. Revenue data finalized after ~24h."
}
```

## Important

- Campaign name **must** start with `[goal]` — required for `wb-calibrate` to group campaigns by strategy.
- `bid_percentile` is a rule-of-thumb target, not an exact bid. Round to nearest 5 RUB.
- After launch, run `wb-assess` next morning and `wb-pulse` every 1-2h during business hours.
- One product per campaign — do not add multiple nm_ids to one campaign.
