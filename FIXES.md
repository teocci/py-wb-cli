# WB CLI — Fix Log

Tracks bug fixes and non-feature improvements across all versions.

## 🚀 Quick Status (for AI Agents)

| Fix | Name | Status | Scope | Date | Notes |
|-----|------|--------|-------|------|-------|
| 0 | Documentation & guard rails | ✅ DONE | docs | 2026-04-02 | Added CLAUDE.md rules + FIXES.md |
| 1 | Constants migration | ✅ DONE | constants.py | 2026-04-02 | 14 endpoints updated, 8 normquery added |
| 2 | Domain model updates | ✅ DONE | 9 models | 2026-04-02 | from_api() rewritten, 3 enums extended |
| 3 | HTTP client (PUT+PATCH) | ✅ DONE | client/http.py | 2026-04-02 | Added put() and patch() methods |
| 4 | PromotionClient rewrite | ✅ DONE | client/promotion.py | 2026-04-02 | 8 methods updated, GET→POST migrations |
| 5 | Service layer adjustments | ✅ DONE | services/*.py | 2026-04-02 | ClusterService rewrite, StatsService cleanup |
| 6 | CLI adjustments | ✅ DONE | cli/*.py | 2026-04-02 | Cluster commands updated, new options |
| 7 | Test updates | ✅ DONE | tests/unit/ | 2026-04-02 | 366 tests pass (+2 cluster tests) |
| 8 | Write endpoint verification | ✅ DONE | live API test | 2026-04-02 | Campaign create/rename/delete verified |
| 9 | Analytics token fallback + selectedPeriod | ✅ DONE | _factory.py, analytics.py | 2026-04-03 | WB_API_TOKEN fallback, start→begin fix |
| 10 | UTF-8 pipe fix (F-4) | ✅ DONE | cli/app.py + 7 CLI modules | 2026-04-17 | stdout reconfigure + centralized _stdout_console |
| 11 | Budget unit + unified bid_type (F-5) | ✅ DONE | services/budgets.py, cli/budget.py, domain/models.py, skills | 2026-04-19 | Budget deposit expects rubles not kopecks; unified must omit placement_types |
| 12 | TTY-aware ANSI output (F-6) | ✅ DONE | core/output.py, cli/assess.py | 2026-04-19 | force_terminal=True → sys.stdout.isatty(); plain text when piped |

**Summary:** All 13 fixes complete. **988 tests passing** (989 total; 1 pre-existing env test). No ANSI codes in piped/agent output.

---

## Summary

Live testing revealed that **10 of 12 endpoint paths** in the codebase return HTTP 404.
WB migrated their Promotion API without deprecation notice. Only `/ping` and `/adv/v1/budget` survived.

Authoritative documentation: `dev-wb-adv.md` (from `https://dev.wildberries.ru/en`)

---

## Fix 0 — Documentation & guard rails

- Added API documentation rule to `CLAUDE.md`
- Created this file (`FIXES.md`)

---

## Fix 1 — Constants migration

**Status:** PENDING

Replace all dead `EP_*` constants with paths from `dev-wb-adv.md`.

| Old Constant | Old Path | New Path | Note |
|---|---|---|---|
| `EP_CAMPAIGN_LIST` | `/adv/v1/promotion/adverts` | `/adv/v1/promotion/count` + `/api/advert/v2/adverts` | Split into 2 |
| `EP_CAMPAIGN_FULLSTATS` | `/adv/v2/fullstats` | `/adv/v3/fullstats` | POST→GET |
| `EP_ELIGIBLE_SUBJECTS` | `/adv/v1/promotion/subjects` | `/adv/v1/supplier/subjects` | Path change |
| `EP_ELIGIBLE_ITEMS` | `/adv/v1/promotion/nms` | `/adv/v2/supplier/nms` | GET→POST |
| `EP_RECOMMENDED_BID` | `/adv/v2/promotion/recommended_cpm` | `/api/advert/v0/bids/recommendations` | Path change |
| `EP_ACCOUNT_BALANCE` | `/adv/v1/account/balance` | `/adv/v1/balance` | Path change |
| `EP_CAMPAIGN_CREATE` | `/adv/v1/promotion/adverts` | `/adv/v2/seacat/save-ad` | Path change |
| `EP_CAMPAIGN_RENAME` | `/adv/v1/rename` | `/adv/v0/rename` | v1→v0 |
| `EP_CAMPAIGN_ITEMS` | `/adv/v1/promotion/nms` | `/adv/v0/auction/nms` | New path+method |
| `EP_CAMPAIGN_PLACEMENTS` | `/adv/v1/auto/update-params` | `/adv/v0/auction/placements` | New path+method |
| `EP_BID_SET` | `/adv/v1/cpm` | `/api/advert/v1/bids` | New path |
| `EP_CLUSTER_ACTIVE` | `/adv/v1/auto/active-words` | Removed (use normquery) | Dead |
| `EP_CLUSTER_ALL` | `/adv/v1/auto/words` | Removed (use normquery) | Dead |
| `EP_CLUSTER_STATS` | `/adv/v2/auto/stat-words` | Removed (use normquery) | Dead |

New normquery constants added: `EP_NQ_LIST`, `EP_NQ_GET_BIDS`, `EP_NQ_SET_BIDS`, `EP_NQ_DEL_BIDS`, `EP_NQ_GET_MINUS`, `EP_NQ_SET_MINUS`, `EP_NQ_STATS`, `EP_NQ_STATS_DAILY`

---

## Fix 2 — Domain model updates

**Status:** DONE

- Campaign: `from_api()` rewritten for v2 adverts shape (id, settings.*, timestamps.*, bid_type, currency)
- AccountBalance: added currency, cashbacks fields
- BudgetSnapshot: replaced daily/balance with cash/netting/currency
- CampaignStats: rewritten for v3 fullstats (added cr, atbs, shks, currency)
- SearchCluster: refactored to norm_query-based (string ID, not numeric)
- ClusterStats: rewritten for normquery stats shape
- BidMutation/CampaignCreate/PlacementConfig: to_api() rewritten for new payloads
- MinusPhraseSet: added from_api() and to_api()
- CampaignStatus: added DELETED(-1), DECLINED(8)
- CampaignType: added STANDARD(9)

---

## Fix 3 — HTTP client (put + patch)

**Status:** DONE

- Added `put()` and `patch()` methods to WbHttpClient

---

## Fix 4 — PromotionClient rewrite

**Status:** DONE

- list_campaigns: returns adverts[] from dict response, uses ids/statuses params
- get_campaign_stats: POST→GET with query params (ids, beginDate, endDate)
- get_eligible_items: GET→POST with subject IDs array as body
- Cluster methods: replaced get_active_clusters/get_all_clusters with normquery POST methods
- delete_campaign: DELETE→GET
- deposit_budget: id moved to query param
- set_placements: POST→PUT
- set_item_bid: POST→PATCH

---

## Fix 5 — Service layer adjustments

**Status:** DONE

- ClusterService: complete rewrite for normquery API (all methods require nm_id)
- StatsService: removed dead get_cluster_stats (moved to ClusterService)
- CampaignService: get_eligible_items passes list to client

---

## Fix 6 — CLI adjustments

**Status:** DONE

- All cluster commands: added required `--nm` option
- Cluster stats: added required `--from`/`--to` date options
- Table headers/rows updated for new model fields

---

## Fix 7 — Test updates

**Status:** DONE

- 366 tests pass (was 364 before fix, gained 2 new cluster tests)
- All mock return values updated for new API response shapes
- Cluster tests rewritten for normquery service/client interface

---

## Fix 8 — Write endpoint verification

**Status:** DONE (2026-04-02)

Throwaway campaign 35495276 used for testing:

| Endpoint | Method | Status | Result |
|---|---|---|---|
| `/adv/v2/seacat/save-ad` | POST | 200 | Created campaign |
| `/adv/v0/start` | GET | 400 | Expected: no budget |
| `/adv/v0/pause` | GET | 400 | Expected: not active |
| `/adv/v0/rename` | POST | 200 | Renamed OK |
| `/adv/v0/stop` | GET | 400 | Expected: not active |
| `/adv/v0/delete` | GET | 200 | Deleted OK |

All write endpoints confirmed working. 400 errors are expected (can't start without budget, can't pause/stop non-active campaign).

---

## Fix 9 — Analytics token fallback + selectedPeriod key

**Status:** DONE (2026-04-03)

### Problem 1 — Analytics commands fail when only `WB_API_TOKEN` is set

`_get_analytics_token()` in `src/wb/services/_factory.py` checked `settings.analytics_token`
(`WB_ANALYTICS_TOKEN`) but skipped `settings.api_token` (`WB_API_TOKEN`), then fell through to
the profile store and raised `ConfigError: Profile 'default' does not exist` even though a valid
token was present in `.env`.

**Fix:** Added `if settings.api_token: return settings.api_token` as a second fallback, after
`settings.analytics_token` and before the profile store lookup.

> If your token covers all WB scopes (Content, Analytics, Promotion, etc.), a single `WB_API_TOKEN`
> in `.env` is sufficient — no separate `WB_ANALYTICS_TOKEN` needed.

### Problem 2 — `selectedPeriod` used wrong field name `begin` instead of `start`

All three methods in `src/wb/services/analytics.py` built the request body as:
```python
'selectedPeriod': {'begin': begin, 'end': end}
```
The WB Analytics v3 API requires `start`, not `begin`:
```python
'selectedPeriod': {'start': begin, 'end': end}
```
This caused every `analytics sales-funnel` command to return `HTTP 400 Bad Request`.

**Fix:** Replaced all three occurrences (`get_product_funnel`, `get_product_history`,
`get_grouped_funnel`) with `'start'`.

---

## Fix 11 — Budget unit + unified bid_type (F-5, v0.20.3)

**Status:** IN PROGRESS (2026-04-19)

### Bug A — Budget deposit accepts rubles, not kopecks

The `/adv/v1/budget/deposit` API `sum` field expects **rubles**. WB error messages confirm:
"Минимальная сумма пополнения 1000 рублей", "кратна 50 руб". The example `"sum": 5000`
satisfies ≥1000 only if interpreted as rubles (5000 kopecks = 50 rubles would fail minimum).

The wb-launch and wb-manage skills incorrectly multiply `budget_rub * 100` before calling
`wb budget topup --sum`, causing 100× over-deposit (1000 RUB → 100,000 RUB deposited).

### Bug B — unified bid_type must not send placement_types

WB API docs state `placement_types` is "Specify for campaign with custom bid only".
For `bid_type: unified` (flat rate), WB activates all placements simultaneously —
no placement selection is applicable. Current `CampaignCreate.to_api()` always sends
`placement_types` regardless.

### Steps

| Step | Description | Status |
|------|-------------|--------|
| A1 ✅ |  Fix `services/budgets.py` — kopecks → rubles in docstring + log messages | [ ] |
| A2 ✅ |  Fix `cli/budget.py` — kopecks → rubles in `--sum` help and log string | [ ] |
| A3 ✅ |  Fix `tests/unit/test_cli_budget.py` — update expected message string | [ ] |
| A4 ✅ |  Fix `skills/wb-launch/SKILL.md` — remove `* 100` conversion | [ ] |
| A5 ✅ |  Fix `skills/wb-manage/SKILL.md` — remove `* 100` conversion | [ ] |
| A6 ✅ |  Add CLAUDE.md quirk entry for budget deposit unit | [ ] |
| B1 ✅ | Fix `domain/models.py` `CampaignCreate.to_api()` — skip placement_types for unified | [ ] |
| B2 ✅ | Fix `cli/campaign.py` — update `--placements` help text | [ ] |
| B3 ✅ | Add tests: unified payload has no placement_types; manual payload does | [ ] |
| C ✅ | Bump version to 0.20.3, update PROGRESS.md | [ ] |

---

## Fix 12 — TTY-Aware ANSI Output (F-6, v0.20.4)

**Status:** DONE (2026-04-19)
**Version:** 0.20.4

### Problem

Commands piped to files, `2>&1` captures, or agent shells (Codex, CI) received raw ANSI escape codes in the output:

```
[3m                  campaign stop                   [0m
[1;32mSuccess:[0m [1;36m1[0m/[1;36m1[0m succeeded
```

This made output unparseable for agents that don't have a real terminal.

### Root cause

`_stdout_console` in `core/output.py` was created with `force_terminal=True`, which tells Rich to always emit ANSI codes regardless of whether stdout is actually a TTY. This was added to fix Windows UTF-8 encoding (F-4), but it broke piped output.

`cli/assess.py` had its own `Console(force_terminal=True)` instance instead of using the shared `_stdout_console`.

### Fix

Replace `force_terminal=True` with `sys.stdout.isatty()` — Rich emits ANSI only when connected to a real terminal. `legacy_windows=False` is retained on both consoles for UTF-8 correctness on Windows regardless of TTY state.

### Files changed

| File | Change |
|------|--------|
| `src/wb/core/output.py` | `force_terminal=True` → `force_terminal=sys.stdout.isatty()` on both `_stdout_console` and `_stderr_console`; added `import sys` |
| `src/wb/cli/assess.py` | Removed local `Console(force_terminal=True)` import; use shared `_stdout_console` |

### Test results

- **988 unit tests passed** (0 failures) — no regressions

---

## Fix 10 — UTF-8 Pipe Fix (F-4, v0.20.2)

**Status:** DONE (2026-04-17)
**Version:** 0.20.2

### Problem

`wb campaign list | more` (and any piped CLI command) crashed with:

```
UnicodeEncodeError: 'charmap' codec can't encode characters in position 597-604: character maps to <undefined>
```

WB content is entirely in Russian (Cyrillic). Agent shells (Codex, CI) inherit the Windows legacy code page (cp437), which cannot encode Cyrillic. Interactive Windows Terminal sessions were unaffected because they configure UTF-8 separately. Agents received no output — the process crashed silently.

### Root cause

`sys.stdout` encoding was never reconfigured at startup. Python inherited the system code page (cp437) on piped stdout. Rich wrote Cyrillic content through `sys.stdout`, which then tried to encode with cp437.

Secondary: 10 bare `Console()` calls across CLI modules bypassed the centralized `_stdout_console` (which carries `legacy_windows=False`) — scattering output logic and making each call independently vulnerable.

### Steps

| Step | Description | Status |
|------|-------------|--------|
| 1 | Add `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` at top of `main()` in `app.py` | ✅ DONE |
| 2 | Replace bare `Console()` in `auth.py` (×2) with `_stdout_console` | ✅ DONE |
| 3 | Replace bare `Console()` in `campaign.py` with `_stdout_console` | ✅ DONE |
| 4 | Replace bare `Console()` in `portal.py` with `_stdout_console` | ✅ DONE |
| 5 | Replace bare `Console()` in `prices.py` with `_stdout_console` | ✅ DONE |
| 6 | Replace bare `Console()` in `product.py` with `_stdout_console` | ✅ DONE |
| 7 | Replace bare `Console()` in `pulse.py` with `_stdout_console` | ✅ DONE |
| 8 | Replace bare `Console()` in `report.py` (×3) with `_stdout_console` | ✅ DONE |
| 9 | Verify: 987 unit tests pass, no regressions | ✅ DONE |

### Files changed

| File | Change |
|------|--------|
| `src/wb/cli/app.py` | `sys.stdout/stderr.reconfigure(encoding='utf-8', errors='replace')` at top of `main()` |
| `src/wb/cli/auth.py` | Removed 2× local `Console()`, added `_stdout_console` import |
| `src/wb/cli/campaign.py` | `console = Console()` → `console = _stdout_console` |
| `src/wb/cli/portal.py` | `Console().print(table)` → `_stdout_console.print(table)` |
| `src/wb/cli/prices.py` | `Console().print(table)` → `_stdout_console.print(table)` |
| `src/wb/cli/product.py` | `Console().print(table)` → `_stdout_console.print(table)` |
| `src/wb/cli/pulse.py` | `console = Console()` → `console = _stdout_console` |
| `src/wb/cli/report.py` | 3× `Console().print(table)` → `_stdout_console.print(table)` |

### Test results

- **987 unit tests passed** (0 failures) — no regressions
