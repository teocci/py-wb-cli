# Phase I-18 — `wb stats daily-report` rich default shape + date filters

**Status:** ✅ DONE · **Version:** 0.35.0 · **Date:** 2026-05-06 · **Tests:** 1313/1314

## What was built

- Expanded `DailyReportRow` from 4 fields to 11: spend side (`views`, `clicks`, `ad_orders`, `spend`, `avg_position`) + funnel side (`opens`, `cart_adds`, `orders`, `order_sum`, `buyouts`). Field rename: `ad_spend` → `spend`, `total_orders` → `orders` (canonical names, BREAKING change called out in CHANGELOG).
- `StatsService.get_daily_report` accepts `date_to: str | None` for range mode; range and single-date cache entries are keyed separately.
- `_fetch_funnel_orders` renamed to `_fetch_funnel_rows`; returns `dict[int, ProductFunnelStats]` instead of `dict[int, int]` so all funnel fields flow through.
- `_get_daily_report_fresh` threads the date range through both the spend fetch and funnel fetch.
- `_cached_or_fetch` now catches `TypeError`/`KeyError` on deserialization so old cache entries (with `ad_spend`/`total_orders` schema) fall through to a fresh fetch instead of crashing.
- CLI `stats daily-report` adds three mutually-exclusive date modes: `--date`, `--days N`, `--from/--to`. Centralised `_resolve_daily_range` validator covers: mutual exclusion, future-date guard (`≤ today-1`), missing `--to` with `--from`, inverted range, 7-day cap.
- Table rendering upgraded to 12 columns.
- JSON output uses `renderer.display()` with `get_fields()` so `--fields` projection works.
- 39 tests in `test_stats_daily_report.py` (fully rewritten + new).

## Files changed

| File | Change |
|------|--------|
| `src/wb/domain/models.py` | Expand `DailyReportRow` to 11 fields |
| `src/wb/services/stats.py` | Range param, `_fetch_funnel_rows`, stale-cache guard |
| `src/wb/cli/stats.py` | Three date modes, `_resolve_daily_range`, wider table, `renderer.display` |
| `tests/unit/test_stats_daily_report.py` | Full rewrite — rich shape, range, stale-cache, `--fields` |
| `AGENT.md` | Add `--days` and `--from/--to` examples |
| `.claude/skills/wb-daily-report/SKILL.md` | New 11-field example, all date flags, updated table |

## Behaviour change (BREAKING)

The JSON shape renames `ad_spend` → `spend` and `total_orders` → `orders`. Callers using the old 4-key narrow path must update their `--fields` to `--fields nm_id,name,spend,orders`. Old response cache entries with the old schema fall through to a fresh fetch automatically (no manual cache purge needed).
