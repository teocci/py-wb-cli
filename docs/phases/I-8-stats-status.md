# Phase I-8 — Stats Campaigns --status Filter (v0.21.0)

**Date:** 2026-04-21

## What Was Built

- `stats campaigns --status running|paused|active` filter
- `active` = virtual alias for `running` + `paused` (all non-stopped campaigns)
- `StatsService.get_stats_by_status()` service method
- Filters campaigns before calling fullstats API (avoids unnecessary API calls for stopped campaigns)
