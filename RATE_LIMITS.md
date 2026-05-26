# WB API Rate Limits

> **For AI agents:** Use this file to plan call sequences. The CLI throttles
> preemptively — never add sleeps. Limits are coordinated **per-(token, endpoint)
> across all `wb` processes** via a shared SQLite file at
> `~/.wb-cli/rate_limits.db` (WAL mode). The runtime authority is **WB's own
> `X-Ratelimit-*` response headers**, not the static numbers in this file —
> `EndpointBudget` self-corrects from headers within one round-trip. The numbers
> below are the **bootstrap priors** used for the very first call to a fresh
> `(token, endpoint)` bucket. After that, WB tells the limiter what to do.

---

## Token type matters

Every limit below has up to two columns: **Personal/Service** (the swagger default
applied to most accounts) and **Base** (a 30–60× tighter regime applied to
"Base" tokens). Some endpoints are uniform across all types — those rows have one
column. To find out your type:

```bash
wb rate status              # shows token_type per token (R-5+)
wb auth list                # shows the persisted token_type field (R-5+)
```

Default when unknown: **`base`** (the safer assumption — Base limits are
strictly tighter, so over-throttling Personal is harmless but under-throttling
Base costs a 30-minute lockout). Override with `wb auth login --token-type
{personal|service|base|test}`.

---

## Endpoints

| CLI Command | Endpoint Constant | Path | Personal/Service | **Base** | Source |
|---|---|---|---|---|---|
| `wb campaign list` | `EP_CAMPAIGN_INFO` | `/api/advert/v2/adverts` | 5/s (burst 5) | **1/h** | swagger 08 |
| `wb campaign start` | `EP_CAMPAIGN_START` | `/adv/v0/start` | 5/s (burst 5) | *uniform* | swagger 08 |
| `wb campaign pause` | `EP_CAMPAIGN_PAUSE` | `/adv/v0/pause` | 5/s (burst 5) | *uniform* | swagger 08 |
| `wb campaign stop` | `EP_CAMPAIGN_STOP` | `/adv/v0/stop` | 5/s (burst 5) | *uniform* | swagger 08 |
| `wb campaign delete` | `EP_CAMPAIGN_DELETE` | `/adv/v0/delete` | 5/s (burst 5) | *uniform* | swagger 08 |
| `wb campaign rename` | `EP_CAMPAIGN_RENAME` | `/adv/v0/rename` | 5/s (burst 5) | **2/h** (1 per 30 min) | swagger 08 |
| `wb campaign create` | `EP_CAMPAIGN_CREATE` | `/adv/v2/seacat/save-ad` | 5/min (1/12 s) | *uniform* | swagger 08 |
| `wb campaign eligible-subjects` | `EP_ELIGIBLE_SUBJECTS` | `/adv/v1/supplier/subjects` | 1/12 s | **2/h** (1 per 30 min) | swagger 08 |
| `wb stats campaign` | `EP_CAMPAIGN_FULLSTATS` | `/adv/v3/fullstats` | **1/20 s** (3/min, burst 1) | **1/h** | swagger 08 |
| `wb budget get` | `EP_CAMPAIGN_BUDGET` | `/adv/v1/budget` | 4/s (burst 4) | *uniform* | swagger 08 |
| `wb budget topup` | `EP_BUDGET_DEPOSIT` | `/adv/v1/budget/deposit` | 1/s (burst 5) | **5/h** (1 per 12 min) | swagger 08 |
| `wb budget balance` | `EP_ACCOUNT_BALANCE` | `/adv/v1/balance` | 1/s (burst 5) | **2/h** (1 per 30 min) | swagger 08 |
| `wb bid set-items` | `EP_BID_SET` | `/api/advert/v1/bids` | 5/s (burst 5) | **2/h** (1 per 30 min) | swagger 08 |
| `wb bid recommend` | `EP_RECOMMENDED_BID` | `/api/advert/v0/bids/recommendations` | 5/min (1/12 s) | **20/h** (1 per 3 min, burst 1) | swagger 08 |
| `wb cluster list` | `EP_NQ_LIST` | `/adv/v0/normquery/list` | 5/s (burst 10) | *uniform* | swagger 08 |
| `wb cluster bids` | `EP_NQ_GET_BIDS` | `/adv/v0/normquery/get-bids` | 5/s (burst 10) | *uniform* | swagger 08 |
| `wb cluster set-bids` | `EP_NQ_SET_BIDS` | `/adv/v0/normquery/bids` (POST) | 2/s (burst 4) | **5/h** (1 per 12 min) | swagger 08 |
| `wb cluster delete-bids` | `EP_NQ_DEL_BIDS` | `/adv/v0/normquery/bids` (DELETE) | 2/s (burst 4) | **5/h** (1 per 12 min) | swagger 08 |
| `wb cluster minus list` | `EP_NQ_GET_MINUS` | `/adv/v0/normquery/get-minus` | 5/s (burst 10) | *uniform* | swagger 08 |
| `wb cluster minus set` | `EP_NQ_SET_MINUS` | `/adv/v0/normquery/set-minus` | 5/s (burst 10) | *uniform* | swagger 08 |
| `wb cluster stats` | `EP_NQ_STATS` | `/adv/v0/normquery/stats` | 10/min (1/6 s, burst 20) | **5/h** (1 per 12 min) | swagger 08 |
| `wb cluster stats-daily` | `EP_NQ_STATS_DAILY` | `/adv/v1/normquery/stats` | 10/min (1/6 s, burst 20) | **2/h** (1 per 30 min) | swagger 08 |
| `wb analytics sales-funnel products` | `EP_FUNNEL_PRODUCTS` | `/api/analytics/v3/sales-funnel/products` | 3/min (1/20 s) | **2/h** (1 per 30 min) | swagger 11 |
| `wb analytics sales-funnel history` | `EP_FUNNEL_HISTORY` | `/api/analytics/v3/sales-funnel/products/history` | 3/min (1/20 s) | **2/h** (1 per 30 min) | swagger 11 |
| `wb analytics sales-funnel grouped` | `EP_FUNNEL_GROUPED` | `/api/analytics/v3/sales-funnel/grouped/history` | 3/min (1/20 s) | **2/h** (1 per 30 min) | swagger 11 |
| `wb analytics search-report main` | `EP_SEARCH_REPORT` | `/api/v2/search-report/report` | 3/min (1/20 s) | **1/h** | swagger 11 |
| `wb analytics search-report groups` | `EP_SEARCH_GROUPS` | `/api/v2/search-report/table/groups` | 3/min (1/20 s) | **1/h** | swagger 11 |
| `wb analytics search-report details` | `EP_SEARCH_DETAILS` | `/api/v2/search-report/table/details` | 3/min (1/20 s) | **1/h** | swagger 11 |
| `wb analytics search-report search-texts` | `EP_SEARCH_TEXTS` | `/api/v2/search-report/product/search-texts` | 3/min (1/20 s) | **1/h** | swagger 11 |
| `wb analytics search-report orders` | `EP_SEARCH_ORDERS` | `/api/v2/search-report/product/orders` | 3/min (1/20 s) | **1/h** | swagger 11 |
| `wb analytics csv create` | `EP_CSV_CREATE` | `/api/v2/nm-report/downloads` (POST) | 3/min (1/20 s) | **1/h** | swagger 11 |
| `wb analytics csv list` | `EP_CSV_LIST` | `/api/v2/nm-report/downloads` (GET) | 3/min (1/20 s) | **1/h** | swagger 11 |
| `wb analytics csv retry` | `EP_CSV_RETRY` | `/api/v2/nm-report/downloads/retry` | 3/min (1/20 s) | **1/h** | swagger 11 |
| *(not yet implemented)* | `EP_STOCKS_WB_WAREHOUSES` | `/api/analytics/v1/stocks-report/wb-warehouses` | **1/20 s** (3/min, burst 1) | *uniform* | swagger 11 |
| `wb report warehouse create` | `EP_WAREHOUSE_REMAINS_CREATE` | `/api/v1/warehouse_remains` (POST) | **1/min** (burst 5) | **4/h** (1 per 15 min) | swagger 12 |
| `wb report warehouse status` | `EP_WAREHOUSE_REMAINS_STATUS` | `/api/v1/warehouse_remains/tasks` (GET) | 1/5 s (burst 5) | **4/h** (1 per 15 min) | swagger 12 |
| `wb report orders` | `EP_STATISTICS_ORDERS` | `/api/v1/supplier/orders` (statistics-api) | **1/min** (burst 1) | *uniform* | swagger 12 |
| `wb report sales` | `EP_STATISTICS_SALES` | `/api/v1/supplier/sales` (statistics-api) | **1/min** (burst 1) | *uniform* | swagger 12 |
| `wb finance sales-reports list` | `EP_FINANCE_SALES_REPORT_LIST` | `/api/finance/v1/sales-reports/list` (finance-api) | **1/min** (burst 1) | **1/h** (assumed) | swagger 13 |
| `wb finance sales-reports detailed` | `EP_FINANCE_SALES_REPORT_DETAILED` | `/api/finance/v1/sales-reports/detailed` (finance-api) | **1/min** (burst 1) | **1/h** (assumed) | swagger 13 |
| `wb finance sales-reports get` | `/api/finance/v1/sales-reports/detailed/{reportId}` | template — no prior, EndpointBudget learns from response headers | — | — | swagger 13 |
| `wb finance acquiring list` | `EP_FINANCE_ACQUIRING_LIST` | `/api/finance/v1/acquiring/list` (finance-api) | **1/min** (burst 1) | **1/h** (assumed) | swagger 13 |
| `wb finance acquiring detailed` | `EP_FINANCE_ACQUIRING_DETAILED` | `/api/finance/v1/acquiring/detailed` (finance-api) | **1/min** (burst 1) | **1/h** (assumed) | swagger 13 |
| `wb finance acquiring get` | `/api/finance/v1/acquiring/detailed/{reportId}` | template — no prior, EndpointBudget learns from response headers | — | — | swagger 13 |
| `wb prices list` | `EP_PRICES_GOODS_FILTER` | `/api/v2/list/goods/filter` | undocumented | undocumented | not in swagger |

> *uniform* in the Base column means swagger documents a single rate that applies
> to every token type — no penalty for Base on that endpoint.

---

## Composite commands

These do not call a single endpoint — they orchestrate several. Slowest leg sets
total wall time. **Base** rates dominate when applicable.

| Command | Endpoints called | Personal/Service wall time | **Base** wall time |
|---|---|---|---|
| `wb assess` | `EP_ACCOUNT_BALANCE` + `EP_CAMPAIGN_INFO` + `EP_CAMPAIGN_FULLSTATS` (per 50-campaign batch) + `EP_RECOMMENDED_BID` (per running campaign) | ~20–25 s (fullstats bottleneck) | **30+ min** (balance, campaign list, fullstats each blow Base 1/h-or-tighter buckets) |
| `wb assess --quick` | `EP_ACCOUNT_BALANCE` + `EP_CAMPAIGN_INFO` | <5 s | ~30 min (sequential 30-min Base buckets) |
| `wb pulse` | `EP_RECOMMENDED_BID` + `EP_CAMPAIGN_BUDGET` + `EP_CAMPAIGN_INFO` per campaign | ~1 s/campaign (paused campaigns 400 fast) | **3 min/campaign** (bid-recommend Base interval); first-pulse-of-hour also burns the campaign-info hour bucket |
| `wb daily-report` | `EP_CAMPAIGN_FULLSTATS` + `EP_FUNNEL_PRODUCTS` per active campaign | ~20 s/campaign | **30+ min** (fullstats 1/h, funnel 30 min) |

**Base agent guidance:** call `wb rate status` first. Only run multi-endpoint
commands if `endpoint_budget` shows the relevant buckets clear. A blind retry
loop on Base will compound 30-minute lockouts across endpoints.

---

## Recovering from 429

`EndpointBudget.observe(...)` writes the response headers into the budget on
every response (200 and 429). When a 429 hits, the row's `reset_at` is set from
WB's own header preference order:

1. `X-Ratelimit-Retry` — when the next request is legal (most precise)
2. `Retry-After` — HTTP standard fallback
3. `X-Ratelimit-Reset` — when the full burst is restored (worst case)

Subsequent `reserve(...)` calls block until that deadline. Other endpoints under
the same token are unaffected — the 429 lock is per-(token, endpoint), not
seller-wide.

If a CLI invocation hits a wait > 60 s, it exits `RATE_LIMITED` (code 5) instead
of blocking. Re-run after `reset_in_s` (visible in `wb rate status`) elapses.

For deeper recovery, invoke the `wb-rate-recover` skill.

---

## Diagnostic surfaces

- **`wb rate status`** — pure read of the `endpoint_budget` table. Shows
  `remaining`, `bucket_limit`, `reset_in_s`, `last_seen_ago_s`, `locked` per
  `(seller_id, token, endpoint)`. Also shows `token_type` per token group.
- **`wb cache status`** — pure read of the `request_cache` table (I-15).
  Shows row count, total bytes, oldest `cached_at`, and soonest `expires_at`
  per `(seller_id, token, endpoint)`.
- **`wb auth ping`** — single GET to `/ping` for connectivity and token
  validity. Uniform 3/30s rate (not Base-stratified), so safe to call on any
  token type without burning an advert bucket.

R-5 removed `wb rate probe`. It made sense before R-1..R-4 when the only way
to know cooldown state was to make a call, but the header-driven runtime now
populates `endpoint_budget` from every real WB response automatically. To
refresh visibility on a specific endpoint, just run any command that hits it.

---

## Request cache (I-15)

Every cacheable read endpoint's response is stored in a per-(token, endpoint,
params-hash) SQLite cache at `~/.wb-cli/request_cache.db` (WAL, cross-process).
The TTL on each entry equals the rate-limit interval (`period / calls`) for
the current token type. So a Base `EP_CAMPAIGN_INFO` entry lives for 3600 s —
exactly the window WB will refuse a refresh in. The cache can never serve data
staler than what a real refresh would deliver, because no real refresh is
possible inside that window.

For Personal tokens the TTL is sub-second on most endpoints, so the cache
effectively no-ops — Personal rate budgets remain the dominant control.

**Mutations auto-invalidate related read caches.** A successful
`wb campaign start` drops cached `EP_CAMPAIGN_INFO` entries for the acting
token, so the next `wb campaign list` reflects the new state. The full map
lives in `src/wb/core/cache_policy.py::MUTATION_INVALIDATES`.

**Bypass for live data:**

```bash
wb --no-cache stats product-spend ...   # one-off bypass
WB_REQUEST_CACHE=disabled wb assess     # env var (CI / scripts)
wb cache clear --endpoint /api/advert/v2/adverts   # surgical wipe
wb cache clear --all --yes          # full wipe
```

The cache is on by default. Only 200–299 responses are cached — wrong-params
400s and 429s never poison the store.

For a full design rationale see
[docs/phases/I-15-request-cache.md](docs/phases/I-15-request-cache.md).

---

## Endpoint groups

Some endpoints share a swagger description but track separate buckets:

| Group | Endpoints | Behaviour |
|---|---|---|
| Analytics search-report | `EP_SEARCH_REPORT`, `EP_SEARCH_GROUPS`, `EP_SEARCH_DETAILS`, `EP_SEARCH_TEXTS`, `EP_SEARCH_ORDERS` | Each has its own bucket (3/min Personal, 1/h Base each) |
| Analytics CSV | `EP_CSV_CREATE`, `EP_CSV_LIST`, `EP_CSV_RETRY` | Each has its own bucket |
| Normquery bids | `EP_NQ_SET_BIDS` (POST), `EP_NQ_DEL_BIDS` (DELETE) | Same path, same bucket |

---

## Source files

| File | API | Base URL |
|---|---|---|
| `docs/swagger/08-promotion.yaml` | Promotion | `advert-api.wildberries.ru` |
| `docs/swagger/11-analytics.yaml` | Analytics | `seller-analytics-api.wildberries.ru` |
| `docs/swagger/12-reports.yaml` | Reports | `seller-analytics-api.wildberries.ru` |

The runtime: [src/wb/core/endpoint_budget.py](src/wb/core/endpoint_budget.py)
(header-driven authority) and [src/wb/core/rate_limits.py](src/wb/core/rate_limits.py)
(`ENDPOINT_LIMITS` bootstrap priors + `BASE_OVERRIDES` after R-5).
