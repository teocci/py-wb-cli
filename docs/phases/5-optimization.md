# Phase 5 — Optimization Workflows (v0.6.0)

**Date:** 2026-04-03 | **Tests:** 511 passed (+37)

## What Was Built

- 4 new domain enums: `OptimizationAction` (10 types), `TargetType`, `ClusterClass` (5), `ProductRole`
- `OptimizerService` with 5 plan + 5 apply methods, configurable thresholds, explainable `reason` strings
- Cluster classification: efficient, visible_weak, expensive_non_converting, inactive_promising, noisy_exclusion
- 6 CLI commands: `wb optimize plan|run|clusters|budget|negatives|portfolio`
- Guarded execution: `--apply` required for mutations, `--yes` to skip confirmation

## V1 Heuristic Rules

| Rule | Signal | Action |
|------|--------|--------|
| Efficient cluster | High CTR + orders | `raise_cluster_bid` (+20%) |
| Visible weak | High views, low CTR | `lower_cluster_bid` (-20%) |
| Wasteful cluster | Spend > 500, 0 orders | `delete_cluster_bid` |
| Noisy cluster | Low CTR + wasteful | `add_minus_phrase` |
| Budget at risk | >85% budget used | `topup_budget` |
| No conversion | Clicks but 0 orders | `pause_campaign` |
