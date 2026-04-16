# WB API Rate Limits

> **For AI agents:** Use this file to plan call sequences. Exceeding a limit returns
> HTTP 429 (exit code 5). The CLI enforces these limits preemptively — you do not need
> to add sleeps between calls. Limits are enforced per-process per-token.

---

## Quick Reference — By CLI Command

| CLI Command | Endpoint Constant | Path | Limit | Period | Burst | Safe Call Rate | Source |
|---|---|---|---|---|---|---|---|
| `wb campaigns list` | `EP_CAMPAIGN_INFO` | `/api/advert/v2/adverts` | 5 | 1 s | 5 | 5/s | swagger 08 |
| `wb campaigns start` | `EP_CAMPAIGN_START` | `/adv/v0/start` | 5 | 1 s | 5 | 5/s | swagger 08 |
| `wb campaigns pause` | `EP_CAMPAIGN_PAUSE` | `/adv/v0/pause` | 5 | 1 s | 5 | 5/s | swagger 08 |
| `wb campaigns stop` | `EP_CAMPAIGN_STOP` | `/adv/v0/stop` | 5 | 1 s | 5 | 5/s | swagger 08 |
| `wb campaigns delete` | `EP_CAMPAIGN_DELETE` | `/adv/v0/delete` | 5 | 1 s | 5 | 5/s | swagger 08 |
| `wb campaigns rename` | `EP_CAMPAIGN_RENAME` | `/adv/v0/rename` | 5 | 1 s | 5 | 5/s | swagger 08 |
| `wb campaigns create` | `EP_CAMPAIGN_CREATE` | `/adv/v2/seacat/save-ad` | 5 | 1 min | 5 | 1/12 s | swagger 08 |
| `wb stats campaign` | `EP_CAMPAIGN_FULLSTATS` | `/adv/v3/fullstats` | 3 | 1 min | **1** | **1/20 s** | swagger 08 |
| `wb budget get` | `EP_CAMPAIGN_BUDGET` | `/adv/v1/budget` | 4 | 1 s | 4 | 4/s | swagger 08 |
| `wb budget deposit` | `EP_BUDGET_DEPOSIT` | `/adv/v1/budget/deposit` | 1 | 1 s | 5 | 1/s | swagger 08 |
| `wb budget balance` | `EP_ACCOUNT_BALANCE` | `/adv/v1/balance` | 1 | 1 s | 5 | 1/s | swagger 08 |
| `wb bids set` | `EP_BID_SET` | `/api/advert/v1/bids` | 5 | 1 s | 5 | 5/s | swagger 08 |
| `wb bids recommended` | `EP_RECOMMENDED_BID` | `/api/advert/v0/bids/recommendations` | 5 | 1 min | 5 | 1/12 s | swagger 08 |
| `wb clusters list` | `EP_NQ_LIST` | `/adv/v0/normquery/list` | 5 | 1 s | 10 | 5/s | swagger 08 |
| `wb clusters get-bids` | `EP_NQ_GET_BIDS` | `/adv/v0/normquery/get-bids` | 5 | 1 s | 10 | 5/s | swagger 08 |
| `wb clusters set-bids` | `EP_NQ_SET_BIDS` | `/adv/v0/normquery/bids` | 2 | 1 s | 4 | 2/s | swagger 08 |
| `wb clusters del-bids` | `EP_NQ_DEL_BIDS` | `/adv/v0/normquery/bids` | 2 | 1 s | 4 | 2/s | swagger 08 |
| `wb clusters get-minus` | `EP_NQ_GET_MINUS` | `/adv/v0/normquery/get-minus` | 5 | 1 s | 10 | 5/s | swagger 08 |
| `wb clusters set-minus` | `EP_NQ_SET_MINUS` | `/adv/v0/normquery/set-minus` | 5 | 1 s | 10 | 5/s | swagger 08 |
| `wb clusters stats` | `EP_NQ_STATS` | `/adv/v0/normquery/stats` | 10 | 1 min | 20 | 1/6 s | swagger 08 |
| `wb clusters stats-daily` | `EP_NQ_STATS_DAILY` | `/adv/v1/normquery/stats` | 10 | 1 min | 20 | 1/6 s | swagger 08 |
| `wb campaigns eligible` | `EP_ELIGIBLE_SUBJECTS` | `/adv/v1/supplier/subjects` | 1 | 12 s | 5 | **1/12 s** | swagger 08 |
| `wb analytics funnel` | `EP_FUNNEL_PRODUCTS` | `/api/analytics/v3/sales-funnel/products` | 3 | 1 min | 3 | 1/20 s | swagger 11 |
| `wb analytics history` | `EP_FUNNEL_HISTORY` | `/api/analytics/v3/sales-funnel/products/history` | 3 | 1 min | 3 | 1/20 s | swagger 11 |
| `wb analytics grouped` | `EP_FUNNEL_GROUPED` | `/api/analytics/v3/sales-funnel/grouped/history` | 3 | 1 min | 3 | 1/20 s | assumed same group |
| `wb analytics search` | `EP_SEARCH_REPORT` | `/api/v2/search-report/report` | 3 | 1 min | 3 | 1/20 s | swagger 11 |
| `wb analytics search-groups` | `EP_SEARCH_GROUPS` | `/api/v2/search-report/table/groups` | 3 | 1 min | 3 | 1/20 s | swagger 11 |
| `wb analytics search-details` | `EP_SEARCH_DETAILS` | `/api/v2/search-report/table/details` | 3 | 1 min | 3 | 1/20 s | swagger 11 |
| `wb analytics search-texts` | `EP_SEARCH_TEXTS` | `/api/v2/search-report/product/search-texts` | 3 | 1 min | 3 | 1/20 s | swagger 11 |
| `wb analytics search-orders` | `EP_SEARCH_ORDERS` | `/api/v2/search-report/product/orders` | 3 | 1 min | 3 | 1/20 s | swagger 11 |
| `wb reports create` | `EP_CSV_CREATE` | `/api/v2/nm-report/downloads` (POST) | 3 | 1 min | 3 | 1/20 s | swagger 11 |
| `wb reports list` | `EP_CSV_LIST` | `/api/v2/nm-report/downloads` (GET) | 3 | 1 min | 3 | 1/20 s | swagger 11 |
| `wb reports retry` | `EP_CSV_RETRY` | `/api/v2/nm-report/downloads/retry` | 3 | 1 min | 3 | 1/20 s | swagger 11 |
| `wb reports stocks` | `EP_STOCKS_WB_WAREHOUSES` | `/api/analytics/v1/stocks-report/wb-warehouses` | 3 | 1 min | **1** | **1/20 s** | swagger 11 |
| `wb reports warehouse create` | `EP_WAREHOUSE_REMAINS_CREATE` | `/api/v1/warehouse_remains` (POST) | 1 | 1 min | 5 | **1/min** | swagger 12 |
| `wb reports warehouse status` | `EP_WAREHOUSE_REMAINS_STATUS` | `/api/v1/warehouse_remains/tasks` (GET) | 1 | 5 s | 5 | 1/5 s | swagger 12 |
| `wb reports warehouse download` | `EP_WAREHOUSE_REMAINS_DOWNLOAD` | `/api/v1/warehouse_remains/tasks` (GET) | 1 | 1 min | 1 | **1/min** | swagger 12 |
| `wb prices list` | `EP_PRICES_GOODS_FILTER` | `/api/v2/list/goods/filter` | unknown | — | — | use default retry | not in swagger |
| `wb assess` (full) | composite: `EP_ACCOUNT_BALANCE` + `EP_CAMPAIGN_INFO` + `EP_CAMPAIGN_FULLSTATS` + `EP_RECOMMENDED_BID` | multiple | see each endpoint | — | — | ~20-25s total (fullstats bottleneck) | composite |
| `wb assess --quick` | composite: `EP_ACCOUNT_BALANCE` + `EP_CAMPAIGN_INFO` | multiple | fast | — | — | <5s | composite |
| `wb pulse` | composite: `EP_RECOMMENDED_BID` + `EP_CAMPAIGN_BUDGET` + `EP_CAMPAIGN_INFO` per campaign | multiple | see each endpoint | — | — | ~1s/campaign (budget/status fast; bid recommend 5/min) | composite |

---

## Endpoint Groups

Some endpoints share a rate limit pool. Calling any endpoint in a group consumes from the same counter.

| Group | Endpoints | Shared Limit |
|---|---|---|
| Analytics search-report | `EP_SEARCH_REPORT`, `EP_SEARCH_GROUPS`, `EP_SEARCH_DETAILS`, `EP_SEARCH_TEXTS`, `EP_SEARCH_ORDERS` | 3/min per endpoint (separate limits) |
| Analytics CSV | `EP_CSV_CREATE`, `EP_CSV_LIST`, `EP_CSV_RETRY` | 3/min per endpoint (separate limits) |

---

## Critical Endpoints for Agent Workflows

These endpoints are most likely to cause 429 errors in automated workflows:

### `EP_CAMPAIGN_FULLSTATS` — `wb stats campaign`
- **Limit:** 3/min, **burst 1** (no burst allowed — must space 20 s apart)
- **CLI enforcement:** `RateLimiter(1, 20.0)` — one call every 20 s
- **Agent guidance:** Batch campaign IDs (max 50 per call, `FULLSTATS_BATCH_SIZE`). A 100-campaign account needs 2 calls → 40 s minimum.

### `EP_FUNNEL_HISTORY` — `wb analytics history`
- **Limit:** 3/min, burst 3 (can fire 3 back-to-back, then wait 60 s)
- **CLI enforcement:** `RateLimiter(3, 60.0)`
- **Agent guidance:** Max NM IDs per call is 20 (`HISTORY_CHUNK_SIZE`). Batch large NM lists.

### `EP_WAREHOUSE_REMAINS_CREATE` — `wb reports warehouse`
- **Limit:** 1/min
- **Agent guidance:** The CLI caches results for 6 h (`REPORT_CACHE_TTL_HOURS`). Always use cached results; only create a new report if the cache is stale.

### `wb assess` / `wb pulse` — composite commands

`wb assess` (full mode) is the slowest composite command: it calls `EP_CAMPAIGN_FULLSTATS` (1/20s) once per batch of up to 50 campaign IDs. With 7 running campaigns this is one fullstats call → ~20s wait. For 51+ campaigns it would be two calls → ~40s.

`wb pulse` calls `EP_RECOMMENDED_BID` (5/60s) once per campaign — sequential, rate-limiter spaced. For 7 campaigns: 7 bid-recommend calls at ~12s intervals = ~84s maximum. In practice campaigns with no active bids return 400 immediately (no wait), so pulse is typically fast.

> Both commands are native CLI (not external scripts) specifically because the rate limiter is process-local — external subprocesses cannot share the limiter and would cause 429 errors.

### Analytics endpoints (funnel, search-report)
- **Limit:** 3/min across all funnel/search variants
- **Agent guidance:** Use `wb product summary` to get analytics + bids + clusters in one composite call instead of making separate analytics calls.

---

## Implementation Details

Rate limits are enforced preemptively in `src/wb/core/rate_limiter.py` using a
sliding-window algorithm. The `ENDPOINT_LIMITS` map in `src/wb/core/rate_limits.py`
maps each endpoint path to `(calls, period_seconds)`. The HTTP client acquires a slot
before sending — no sleep after 429 (the reactive retry in `http.py` remains as backup).

**Sliding window interpretation of burst:**
- `burst = 1` → all calls must be spaced by `period / limit` → stored as `(1, interval)`
- `burst = limit` → full burst allowed, then wait → stored as `(limit, period)`

---

## How to Update

When a new 429 is observed or a new endpoint is added:

1. Check `docs/swagger/` for a documented rate limit.
2. If not documented, record the empirical limit with a `# empirical` comment.
3. Add a row to the Quick Reference table above.
4. Add or update the entry in `src/wb/core/rate_limits.py`.
5. Keep the source column accurate: `swagger 08`, `swagger 11`, `swagger 12`, or `empirical`.

---

## Source Files

| Swagger File | API | Key Endpoints |
|---|---|---|
| `docs/swagger/08-promotion.yaml` | Promotion API (`advert-api.wildberries.ru`) | Campaigns, bids, budget, clusters |
| `docs/swagger/11-analytics.yaml` | Analytics API (`seller-analytics-api.wildberries.ru`) | Funnel, search-report, CSV |
| `docs/swagger/12-reports.yaml` | Reports API (`seller-analytics-api.wildberries.ru`) | Warehouse remains, paid storage |
