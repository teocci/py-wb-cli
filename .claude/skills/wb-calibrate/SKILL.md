---
name: wb-calibrate
description: Biweekly strategy calibration. Reads 30-day campaign analytics grouped by [goal] prefix, computes observed performance ranges, and updates rules.json. Run after 14+ days of campaign data to validate or correct the default strategy rules.
triggers:
  - "calibrate rules"
  - "update rules"
  - "recalibrate strategies"
  - "validate rules"
  - "rules out of date"
---

# wb-calibrate

Biweekly calibration of `~/.wb-cli/rules.json`. Reads 30-day analytics for all running campaigns, groups by `[goal]` name prefix, and updates bid percentile and payment type confidence based on observed CTR and spend ranges.

## When to run

- After 14+ days of campaign data (first run)
- Every 2 weeks thereafter
- When WB announces algorithm changes (resets `confidence` to `"low"` for affected strategies)

## Steps

### 1. Run calibration script

```bash
.venv/Scripts/python .claude/skills/wb-calibrate/scripts/wb_calibrate.py --days 30
```

The script:
1. Calls `wb stats campaigns` for all running campaign IDs (sequential, 1 call/20s rate limit)
2. Groups results by `[goal]` prefix in campaign name
3. Computes per-strategy CTR range, CPC range, order rate
4. Updates `~/.wb-cli/rules.json` — adjusts `bid_percentile`, sets `validated: true` for strategies with enough data (≥7 days, ≥100 views), sets `confidence: "medium"` or `"high"`

### 2. Review calibration report

```json
{
  "calibrated_at": "2026-04-17",
  "strategies_updated": ["steady_low_cost", "new_product_visibility"],
  "strategies_skipped": ["volume_sales"],
  "skip_reasons": {"volume_sales": "insufficient_data: only 3 days"},
  "changes": {
    "steady_low_cost": {"bid_percentile": {"old": 50, "new": 45}, "validated": true},
    "new_product_visibility": {"bid_percentile": {"old": 75, "new": 80}, "validated": true}
  },
  "note": "Re-run wb-launch dry-runs for any active campaigns using updated strategies to see new recommended bids."
}
```

### 3. Act on the report

- **Strategies updated with `validated: true`**: next `wb-launch` will use these with `confidence: "medium"` — no warning needed.
- **Strategies skipped**: continue using defaults; run calibrate again in 2 weeks.
- **Large bid_percentile changes (>15 points)**: consider adjusting bids on existing campaigns via `wb-optimize`.

## Notes

- Requires campaign names in `[goal] ...` format. Campaigns without this prefix are ignored.
- Financial data (`orders`, revenue) has up to 24h lag — calibrate on data that is at least 2 days old. The script uses `--to yesterday` automatically.
- `keyword_rules.json` is also updated: keywords that performed well across re-test periods get their `min_ctr_to_keep` thresholds adjusted.
