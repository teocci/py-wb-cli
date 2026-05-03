# Phase I-19 — `generate_daily_wb_report.py` switches to `wb stats daily-report`

**Status:** 🔲 PLANNED · **Depends on:** I-18 shipped *and installed in production* (the script needs the new CLI shape)
**Plan:** [floofy-orbiting-parnas.md](../../../../Users/teocci/.claude/plans/floofy-orbiting-parnas.md)

## Problem

[`scripts/generate_daily_wb_report.py`](../../scripts/generate_daily_wb_report.py) shells out to two separate `wb` subprocesses (`analytics sales-funnel products` + `stats product-spend`) and merges the results in Python. Each subprocess opens its own SQLite handles and emits its own `RateLimitedError` envelope; the script duplicates orchestration that already lives in `get_daily_report` post-I-18.

Backfilling N missed days forces N script runs that hit the same three Base buckets repeatedly — calls 2 and 3 wait 30–60 min for cooldown to clear. A 3-day backfill on Base costs ~3 h.

## Goal

Replace the script's two-subprocess orchestration with a single `wb stats daily-report --from X --to Y` call. Add `--days N` / `--from`/`--to` modes mirroring I-18 so cron and ad-hoc backfill use the same shape. Total WB calls drop to 3 regardless of range width within the 7-day cap.

## Production constraint

Production has the `wb` CLI installed but **not** the repo source. The script stays a subprocess client throughout — no `from wb...` imports.

## Date-filter rules

Mirror I-18 exactly:

- `--date YYYY-MM-DD` — single past date (default to yesterday when no flags pass; preserves cron compat).
- `--days N` — relative range ending yesterday.
- `--from YYYY-MM-DD --to YYYY-MM-DD` — absolute range.
- All resolved dates `<= today-1`. `--from <= --to`. Range cap 7 days. Mutually exclusive.

## Changes

| File | Change |
|------|--------|
| `scripts/generate_daily_wb_report.py` | Replace `fetch_orders_payload` + `fetch_spend_payload` + the merge with one `wb --json --compact stats daily-report --from X --to Y` call. Drop `build_spend_rows`, `verify_spend_rows_against_payloads`, the funnel/spend payload loaders, and the mid-run `wb rate status` check (one subprocess now). Argparse mirrors I-18's three date modes with the same validation rules. Keep `RateLimitedError` envelope parsing. Keep persisted-artifact fallback, renamed for the range case (`daily_report_<from>_to_<to>_full.json`). |
| Output CSV file naming | Single-date: unchanged (`orders_<date>_by_nm.csv`, `ad_costs_<date>_merged.csv`). Range: `orders_<from>_to_<to>_by_nm.csv`, `ad_costs_<from>_to_<to>_merged.csv`. |
| `.claude/skills/wb-daily-report/SKILL.md` | Add backfill example: `--days N` or `--from`/`--to`. Note that the merged CSV row set is campaign-NM scoped (already covered in I-18's skill update). |

## Steps

- [ ] Wait for I-18 to be released *and installed in production*
- [ ] Refactor argparse to the three-mode shape with shared validator
- [ ] Replace two-phase orchestration with the single `wb stats daily-report` subprocess call
- [ ] Update CSV writer to consume the rich shape directly (drop the merge step)
- [ ] Adjust persisted-artifact paths and recovery code for both single-date and range
- [ ] Drop dead helpers (`fetch_orders_payload`, `fetch_spend_payload`, `build_spend_rows`, `verify_spend_rows_against_payloads`, related loaders)
- [ ] Update wb-daily-report skill with backfill example
- [ ] Single-date regression on a known past date — verify CSVs match (with the campaign-NM scope narrowing called out in release notes)
- [ ] Range happy-path: `--days 3` and `--from D-6 --to D-1`
- [ ] Validation negatives mirror I-18
- [ ] Live test on Base for both modes
- [ ] `phase-complete` → version 0.35.1, tag, push

## Verification

- Single-date run produces the same `ad_costs_<date>_merged.csv` content as today (campaign-NM scope narrowing flagged in release notes).
- `--days 3` and `--from <D-6> --to <D-1>` produce range-named CSVs with metric sums across the period and row counts matching the campaign NM set.
- Validation negatives exit non-zero with single-line errors and write no partial artifacts.
- Cooldown accounting on Base: `EP_CAMPAIGN_INFO` +1 (or 0 if pre-warmed by `wb assess`), `EP_FUNNEL_PRODUCTS` +1, `EP_CAMPAIGN_FULLSTATS` +1. Total 3 calls regardless of range width.

## Out of scope

- Removing the script entirely. Still owns CSV formatting, file-naming, persisted-artifact fallback.
- Per-date CSVs for backfill ranges. Operator can still run per-date if needed (with N×cooldown cost).
