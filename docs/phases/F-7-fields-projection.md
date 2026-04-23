# Fix F-7 — campaign list --fields Projection (v0.20.5)

**Date:** 2026-04-19 | **Tests:** 988 passed

## Problem

`wb --fields id,name,status campaign list` rendered the full 6-column table. `--json --fields` also returned complete campaign objects.

## Root Cause

`campaign_list` in `cli/campaign.py` bypassed `renderer.display()` entirely, using a bare `typer.echo` + `render_table` that ignored `--fields`.

## Fix

`cli/campaign.py`: Route both JSON and table rendering through `renderer.display(..., fields=get_fields(ctx))`.
- JSON path: `_filter_fields()` keeps only requested dict keys
- Table path: columns filtered by case-insensitive header match (`id`→`ID`, `status`→`Status`)
