# Phase 3 — Search-Cluster Control (v0.4.0)

**Date:** 2026-04-02 | **Tests:** 405 passed (+39)

## What Was Built

- `ClusterBidMutation` domain model (replaces unused `ClusterBid`)
- `PromotionClient` write methods: `set_cluster_bids`, `delete_cluster_bids`, `set_minus_phrases`
- `ClusterService` write methods: `set_cluster_bids`, `delete_cluster_bids`, `set_minus_phrases`, `clear_minus_phrases` — all with dry-run, validation (max 100 bids, max 1000 phrases)
- `ClusterService.get_cluster_stats_daily` via normquery v1 API
- CLI commands: `wb cluster set-bids`, `wb cluster set-bids-file`, `wb cluster delete-bids`, `wb cluster delete-bids-file`, `wb cluster stats-daily`
- Minus phrase sub-app: `wb cluster minus list|set|clear`
