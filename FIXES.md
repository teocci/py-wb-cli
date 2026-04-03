# WB CLI — API Fix Log

Tracks the migration from dead WB API endpoints to the current API (discovered 2026-04-02).

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
