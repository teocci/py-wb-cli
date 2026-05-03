# Fix F-18 — `funnel-history` `dt` field parser reads wrong key

**Status:** ✅ DONE · **Version:** 0.33.1 · **Date:** 2026-05-04 · **Tests:** 1298 passed

## Problem

`EP_FUNNEL_HISTORY` (`/api/analytics/v3/sales-funnel/products/history`) returns per-day rows
whose date lives in a field the swagger schema names `date`. `FunnelHistoryDay.from_api` was
reading `data.get('dt', '')`, so the parsed `dt` field was always empty string in real API
responses. Documented in CLAUDE.md "Known WB API Quirks" but never fixed.

## What Was Built

- `FunnelHistoryDay.from_api` now reads `data.get('date') or data.get('dt') or ''` — prefers
  the real WB field, falls back to `dt` for any caller that supplies legacy payloads.
- Existing test fixtures in `test_analytics_models.py` and `test_analytics_service.py` updated
  to supply `date` key (matching real API shape).
- Added parametrized test `test_date_field_fallback` covering three cases: `date` only, `dt`
  only, and both present (confirms `date` wins).
- Struck the "Returns empty string" quirk row from CLAUDE.md and replaced it with an accurate
  note describing the fix.

## Files Changed

| File | Change |
|------|--------|
| `src/wb/domain/analytics_models.py` | `FunnelHistoryDay.from_api` reads `date` with `dt` fallback |
| `tests/unit/test_analytics_models.py` | Fixture uses `date`; added `test_date_field_fallback` parametrized test |
| `tests/unit/test_analytics_service.py` | `get_funnel_history` fixture uses `date` key |
| `CLAUDE.md` | Replaced stale quirk row with accurate `date`/`dt` note |

## Risk

Pure parser fix. No CLI surface change. The `dt` fallback preserves any caller relying on the
old key. The one pre-existing test failure (`test_auth_list_empty`) is unrelated to this fix.
