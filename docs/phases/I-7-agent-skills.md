# Phase I-7 — Agent Skills (v0.20.0)

**Date:** 2026-04-17 | **Tests:** 952 passed (+35)

## What Was Built

### Native CLI Commands

- `domain/assess_models.py`: `AssessSnapshot`, `CampaignAssessSummary`, `PulseReport`, `CampaignPulse`, `PulseBaseline`
- `services/assess.py`: `AssessService` — balance + campaigns + product spend + bid baselines; `--quick` skips fullstats; saves `~/.wb-cli/pulse_baseline.json`
- `services/pulse.py`: `PulseService` — reads baseline, computes bid drift %; fires alert codes
- `cli/assess.py`: `wb assess [--nm <id>] [--quick] [--json] [--compact]`
- `cli/pulse.py`: `wb pulse --campaigns <ids> [--json] [--compact]`

### Claude Code Skills

| Skill | Cadence | Backed by |
|-------|---------|-----------|
| `wb-assess` | Once per morning | `wb assess` |
| `wb-pulse` | Every 1-2h intraday | `wb pulse` |
| `wb-launch` | Per new product | Sequential wb commands + `rules.json` |
| `wb-optimize` | Daily per campaign | Sequential wb commands |
| `wb-manage` | As needed | Direct wb command dispatch |
| `wb-keywords` | Weekly | `scripts/wb_keywords.py` |
| `wb-calibrate` | Biweekly | `scripts/wb_calibrate.py` |

### Alert Thresholds (wb-pulse)

| Alert | Trigger |
|-------|---------|
| `competitor_surge` | bid recommendation up >15% since morning |
| `budget_low` | balance < 500 RUB or < 20% of morning balance |
| `campaign_paused` | status changed to paused |
| `bid_floor_rising` | minimum bid up >10% since morning |
