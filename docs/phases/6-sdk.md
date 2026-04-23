# Phase 6 — Agent Platform Support / Python SDK (v0.7.0)

**Date:** 2026-04-03 | **Tests:** 539 passed (+44)

## What Was Built

- Python SDK facade (`src/wb/sdk.py`): ~50 importable functions wrapping service factories
  - Campaign: `list_campaigns`, `get_campaign`, `create_campaign`, `clone_campaign`, `start/pause/stop_campaign`
  - Budget: `get_balance`, `get_budget`, `topup_budget`
  - Bids: `get_recommended_bids`, `set_item_bid`
  - Clusters: `list_clusters`, `set_cluster_bids`, `set_minus_phrases`
  - Optimizer: `plan_clusters`, `plan_budget`, `plan_negatives`, `plan_all`, `apply_clusters`, `apply_all`
- `wb campaign clone` command: clones campaign with optional name override + explicit `--nms`
- Optimizer fix: reordered `NOISY_EXCLUSION` branch to fix unreachable condition

## Key Design Decisions

- SDK is a pure function facade: no try/except, callers receive `WbCliError` subclasses directly
- Clone requires explicit `--nms` because campaign info API does not return current items
