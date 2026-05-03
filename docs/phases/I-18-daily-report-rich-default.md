# Phase I-18 — `wb stats daily-report` rich default shape + `--from`/`--to`/`--days` filters

**Status:** 🔲 PLANNED · **Depends on:** I-17 shipped (sequencing — I-17's status filter applies automatically inside `get_daily_report`'s campaign discovery path)
**Plan:** [floofy-orbiting-parnas.md](../../../../Users/teocci/.claude/plans/floofy-orbiting-parnas.md)

## Problem

Today's [`wb stats daily-report`](../../src/wb/cli/stats.py) emits only `{nm_id, name, ad_spend, total_orders}` — too thin for the production [`generate_daily_wb_report.py`](../../scripts/generate_daily_wb_report.py) script, which needs the full per-NM funnel + spend bundle. The script reimplements the merge by calling `wb analytics sales-funnel products` + `wb stats product-spend` separately, duplicating semantics that already live in [`get_daily_report`](../../src/wb/services/stats.py) and producing two cache entries instead of one.

The same command also has no range mode — backfilling missed days forces N per-date runs, each hitting the same Base buckets (and serial Base runs cost 30–60 min cooldowns per repeat).

## Goal

Upgrade `wb stats daily-report`'s default JSON shape to the full per-NM funnel + spend bundle, and add three mutually-exclusive date-filter modes (`--date`, `--days N`, `--from`/`--to`). Producer of the merged shape that I-19's script consumes.

## Behaviour change (call out in CHANGELOG)

The default JSON shape gains funnel and spend fields previously absorbed only into `total_orders` and `ad_spend`. Adding fields is non-breaking by JSON-consumer convention; table-mode rendering becomes wider. Callers who want only the legacy four keys add `--fields nm_id,name,ad_spend,total_orders` (already supported in JSON mode). No `--full` / `--summary` flag — one shape, one command.

## Open question (decide before implementation)

Whether to keep the legacy field aliases (`ad_spend`, `total_orders`) alongside canonical names (`spend`, `orders`), or rename outright. Recommend **rename outright** to avoid schema bloat and mirror the underlying API names; flag for confirm at implementation start.

## Date-filter rules

Three mutually-exclusive modes, default = single-date yesterday:

- `--date YYYY-MM-DD` — single past date.
- `--days N` — relative range ending yesterday: `from = today-N`, `to = today-1`. `N >= 1`.
- `--from YYYY-MM-DD --to YYYY-MM-DD` — absolute range. Both required together.

Validation:

- All resolved dates must be `<= today-1` (24-hour settle window — hard rule, no opt-out).
- `--from <= --to`.
- Range width capped at **7 days** (matches documented `funnel-history` limit; relax in a follow-up after verifying the `funnel-products` server-side cap).
- Combining modes (e.g. `--date` + `--days`) → validation error pointing at the mutual-exclusion rule.

## Changes

| File | Change |
|------|--------|
| `src/wb/domain/models.py` | Expand `DailyReportRow` to carry every field the script needs: funnel side `opens, cart_adds, orders, order_sum, buyouts`; spend side `views, clicks, ad_orders, spend, avg_position`. Plus existing `nm_id, name`. (Decide on `ad_spend`/`total_orders` per the open question above.) |
| `src/wb/services/stats.py` | `get_daily_report` always returns the rich shape (no `full` parameter). Accept `date_to: str \| None = None`; range mode = one funnel call + one fullstats call across `[date, date_to]`. `_fetch_funnel_orders` extended to pull all funnel fields (today only pulls `order_count`). Cache key includes `date_to` so range and single-date have separate cache entries. |
| `src/wb/cli/stats.py` | Three mutually-exclusive date modes (`--date`, `--days N`, `--from`/`--to`); shared validator covering all three modes + the `<= today-1` rule + the 7-day cap. Emit rich shape always. Table renders the wider column set. |
| `tests/unit/test_stats_service.py` | Update existing tests to assert the rich shape. Add range-mode tests. Add a `--fields` projection test demonstrating the legacy 4-key narrow path. |
| `docs/AGENT.md` | Document the new shape and date filters. |
| `.claude/skills/wb-daily-report/SKILL.md` | Update example output and command flags. Note the rich default and the `--fields` projection for legacy callers. |
| `CHANGELOG.md` | 0.35.0 entry calls out the JSON shape change as a behaviour change. |

## Steps

- [ ] Confirm the field-rename open question (keep aliases vs canonical names)
- [ ] Expand `DailyReportRow` dataclass per the decision
- [ ] Update `get_daily_report` to always populate the rich shape
- [ ] Add `date_to` parameter to `get_daily_report`; thread through `_get_daily_report_fresh` to call funnel and fullstats with the range
- [ ] Update `_fetch_funnel_orders` to pull every funnel field, not just `order_count`
- [ ] CLI: add `--days N` and `--from`/`--to`; centralise date-validation helper covering all three modes + `<= today-1` rule + 7-day cap
- [ ] Update existing unit tests to the rich shape; add range-mode tests; add `--fields` projection test
- [ ] Update wb-daily-report skill and AGENT.md
- [ ] Run `pytest tests/unit/ -v` — all green
- [ ] CLI smoke: `--json` no flags, `--date X`, `--days 7`, `--from D-6 --to D-1`, `--fields nm_id,name,ad_spend,total_orders`, plus all validation negatives
- [ ] `phase-complete` → version 0.35.0, tag, push

## Verification

- `pytest tests/unit/ -v` green.
- All five CLI smoke cases produce the expected shape; validation negatives exit non-zero with single-line errors.
- `wb stats daily-report --json --date <past-date>` run twice — second run hits the I-15 cache (0 WB calls).
- `wb stats daily-report --json --from X --to Y` separately cached from single-date — re-run hits cache.

## Out of scope

- Per-day breakdown across a range. Funnel-history is capped at 20 NMs/call (worse on Base); CLI fan-out per date defeats the range optimization. Aggregate-range is the trade-off.
- Relaxing the 7-day range cap. Follow-up after live verification of the funnel-products server-side limit.
- Allowing `today` or future dates. Hard-blocked by the 24 h settle rule — no flag overrides it.
- Renaming `daily-report` to something else.
- Adding a `--summary` / `--full` flag.
