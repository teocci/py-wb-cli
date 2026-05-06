# Phase I-19 — `generate_daily_wb_report.py` switches to `wb stats daily-report`

**Version:** 0.35.1 · **Date:** 2026-05-06 · **Tests:** 1329 passed (1 pre-existing env failure)

## What was built

- Rewrote `scripts/generate_daily_wb_report.py` (634 → 296 lines): replaced the two-subprocess orchestration (`analytics sales-funnel products` + `stats product-spend`) with a single `wb stats daily-report --from X --to Y` call — total WB calls drop from N×2 to 3 regardless of date range.
- Added three-mode date filtering mirroring I-18: `--date`, `--days N`, `--from`/`--to` (max 7 days, all dates `<= today-1`, mutually exclusive).
- Range-aware file naming: single-date uses unchanged names (`orders_{date}_by_nm.csv`, `ad_costs_{date}_merged.csv`, `daily_report_{date}_full.json`); range mode appends `_{from}_to_{to}` stem.
- Dropped dead helpers: `SPEND_RELEVANT_ENDPOINTS`, `read_rate_status`, `find_active_lock`, `find_active_lock_for`, `load_orders_payload`, `load_spend_payload`, `collect_spend_results`, `build_spend_rows`, `verify_spend_rows_against_payloads`, `fetch_orders_payload`, `fetch_spend_payload`, `acquire_payloads`, `verify_orders_csv`, `verify_merged_csv`, mid-run rate-status pre-check.
- New helpers: `resolve_date_range`, `fetch_daily_report`, `load_daily_report_payload`, `build_report_rows` (maps `DailyReportRow` JSON directly to CSV), `build_orders_rows` (simplified), `_artifact_paths`.
- Updated `tests/unit/test_daily_report_script.py`: replaced `TestFindActiveLockFor` / `TestSpendRelevantEndpoints` with `TestResolveDateRange` (13 cases) + `TestBuildReportRows` (9 cases) + `TestBuildOrdersRows` (2 cases); net +16 tests (1313 → 1329 passing).
- Updated `.claude/skills/wb-daily-report/SKILL.md`: added **Backfill** section with `--days N` and `--from`/`--to` examples; updated artifact naming to `daily_report_{date}_full.json`.

## Files changed

| File | Change |
|------|--------|
| `scripts/generate_daily_wb_report.py` | Full rewrite — single subprocess, three date modes, range-aware naming |
| `tests/unit/test_daily_report_script.py` | Replaced deleted-function tests with resolve_date_range + build_report_rows coverage |
| `.claude/skills/wb-daily-report/SKILL.md` | Added backfill section and updated artifact naming |
| `docs/phases/I-19-script-uses-daily-report.md` | This file |

## Production constraint

Production has the `wb` CLI installed but **not** the repo source. The script stays a subprocess client throughout — no `from wb...` imports.

## Backfill improvement

Before I-19: a 3-day backfill cost ~3 hours on Base (N runs × 2 subprocess calls × 30-min cooldowns between runs). After I-19: `--days 3` costs 3 WB API calls total (1 per endpoint, same as a single-day run).

## Verification

- `pytest tests/unit/ -q` → 1329 passed, 1 pre-existing failure (`test_auth_list_empty`)
- Validation negatives all exit 2: future date, `--days 0`, `--days 8`, `--from` missing `--to`, `--to` missing `--from`, `--from > --to`, range > 7 days, `--to` with `--days`
- `build_report_rows` field mapping verified by unit tests; computed metrics (`cpo_rub`, `drr_percent`, `cpc_rub`, `ad_attribution_percent`) tested with known values
- Zero-denominator guard yields empty string (not divide-by-zero crash)
- Sort order (spend descending, then article_number) preserved
