# Phase I-15 — Cooldown-tied HTTP-layer request cache (`RequestCache`)

**Status:** ✅ DONE · **Version:** 0.32.0 · **Date:** 2026-04-27 · **Tests:** +74 (1275 total)
**Depends on:** R-5 (token-type-aware priors must be in place — TTL = `period / calls` is derived from `select_prior`)
**Resolves:** the architectural fragility behind F-16 (`stats product-spend` → `/api/advert/v2/adverts` 1-hour lockout on Base tokens)
**Plan:** [happy-exploring-fox.md](../../../../Users/teocci/.claude/plans/happy-exploring-fox.md)

## Context

WB's Base-token rate limits are 30–60× tighter than Personal/Service on the same advert + analytics endpoints (see R-5: `BASE_OVERRIDES` in `src/wb/core/rate_limits.py`). Examples:

- `/api/advert/v2/adverts` (`EP_CAMPAIGN_INFO`): Personal 5/s, **Base 1/h**.
- `/adv/v3/fullstats` (`EP_CAMPAIGN_FULLSTATS`): Personal 1/20 s, **Base 1/h**.
- `/api/analytics/v3/sales-funnel/products` (`EP_FUNNEL_PRODUCTS`): Personal 3/min, **Base 2/h**.

Workflows that re-invoke `wb` against the same Base endpoint inside its cooldown — chained scripts, multi-chunk callers, parallel cron jobs, ad-hoc inspection — collide with these caps deterministically. The current `EndpointBudget` correctly reports the lock and bails fast, but offers no relief: every fresh process refetches the same data.

The R-5 substrate already encodes "how often WB lets us refresh this endpoint". I-15 adds the natural twin: a per-(token, endpoint, params) cache whose TTL equals the rate-limit interval (`period / calls`). Because the TTL exactly matches what WB will let us refresh, the cache can never serve data staler than reality permits — yet it eliminates the entire class of "second invocation locks for an hour".

## Why TTL = `period / calls`

For Base `(1, 3600)`:
- WB will refuse a refresh for 3600 s.
- Cache TTL = 3600 s.
- The cache can never serve data staler than what a real refresh would deliver — because no real refresh is possible inside that window.
- **No correctness loss, full availability gain.**

For Personal `(5, 1.0)`:
- TTL = 0.2 s. Effectively off — Personal tokens don't need this protection. The existing rate-limit budget remains the dominant control.

For endpoints with no prior (`select_prior` returns `None`): skip the cache entirely. Header-driven `EndpointBudget` self-corrects from the first response.

## Design summary

- **One SQLite file** at `~/.wb-cli/request_cache.db` (WAL, cross-process). Separate from `rate_limits.db` for clean lifecycle.
- **One key, one lookup** per request: `(token_fp, endpoint, params_hash)`. The cooldown check stays in `EndpointBudget.reserve()` — the cache never duplicates that responsibility.
- **Allowlist** of cacheable read endpoints; mutations are explicitly never cached.
- **Mutation invalidation**: a successful `wb campaign start` drops cached entries for `EP_CAMPAIGN_INFO`, etc.
- **Only 200–299 responses cached.** 4xx (bad params, 429) and 5xx never poison the cache.
- **Double-check on the rare race path**: when `EndpointBudget.reserve()` raises `RateLimitError`, do one final `cache.get` before re-raising — handles the case where another process just published while we were waiting on `reserve`.
- **Bypass:** global `--no-cache` flag + `WB_REQUEST_CACHE=disabled` env var.
- **Diagnostics:** `wb api-cache status` and `wb api-cache clear` (top-level group; `wb cache` is already taken by the snapshot cache from phase 7).

## Concurrency model

Detail in the plan; recap of the contract:

| Aspect | Guarantee | How |
|---|---|---|
| Cache reads across processes | Latest committed visible | SQLite WAL default isolation |
| Cache writes across processes | Last-write-wins; identical responses idempotent | `INSERT OR REPLACE` on PRIMARY KEY |
| Rate-limit slot allocation across processes | Exactly one acquires per window | `SharedRateLimiter` SQLite atomic transaction (existing) |
| In-flight publication race | Mitigated by double-check on `RateLimitError` path | one extra `cache.get` |

What we explicitly do NOT build: `RaceConditionError`, single-flight via in-flight claims, retry loops on `RateLimitError`. Reasoning in the plan; future-improvement candidates only if real concurrency pain shows up.

## Catalog

### Cacheable endpoints (read-only, idempotent reads only)

```
EP_CAMPAIGN_INFO
EP_CAMPAIGN_BUDGET
EP_CAMPAIGN_FULLSTATS
EP_RECOMMENDED_BID
EP_ACCOUNT_BALANCE
EP_ELIGIBLE_SUBJECTS
EP_FUNNEL_PRODUCTS
EP_FUNNEL_HISTORY
EP_FUNNEL_GROUPED
EP_NQ_LIST
EP_NQ_GET_BIDS
EP_NQ_GET_MINUS
EP_NQ_STATS
EP_NQ_STATS_DAILY
EP_SEARCH_REPORT
EP_SEARCH_GROUPS
EP_SEARCH_DETAILS
EP_SEARCH_TEXTS
EP_SEARCH_ORDERS
```

### Never-cache (mutations and write endpoints)

```
EP_CAMPAIGN_CREATE / _START / _PAUSE / _STOP / _DELETE / _RENAME
EP_BUDGET_DEPOSIT
EP_BID_SET / EP_BID_MIN
EP_NQ_SET_BIDS / EP_NQ_DEL_BIDS / EP_NQ_SET_MINUS
EP_CAMPAIGN_ITEMS / EP_CAMPAIGN_PLACEMENTS
EP_CSV_CREATE / _LIST / _RETRY  (background-job lifecycle, not pure reads)
EP_STOCKS_WB_WAREHOUSES
EP_WAREHOUSE_REMAINS_*
EP_PRICES_GOODS_FILTER
EP_STATISTICS_SALES
PING_PATH
```

A unit test asserts every entry in `ENDPOINT_LIMITS` is in exactly one of the two sets — future endpoints can't sneak in uncategorised.

### Mutation → invalidation map

```
EP_CAMPAIGN_CREATE → (EP_CAMPAIGN_INFO,)
EP_CAMPAIGN_START  → (EP_CAMPAIGN_INFO,)
EP_CAMPAIGN_PAUSE  → (EP_CAMPAIGN_INFO,)
EP_CAMPAIGN_STOP   → (EP_CAMPAIGN_INFO,)
EP_CAMPAIGN_DELETE → (EP_CAMPAIGN_INFO,)
EP_CAMPAIGN_RENAME → (EP_CAMPAIGN_INFO,)
EP_BUDGET_DEPOSIT  → (EP_CAMPAIGN_BUDGET, EP_ACCOUNT_BALANCE)
EP_BID_SET         → (EP_CAMPAIGN_INFO, EP_RECOMMENDED_BID)
EP_NQ_SET_BIDS     → (EP_NQ_GET_BIDS, EP_NQ_LIST)
EP_NQ_DEL_BIDS     → (EP_NQ_GET_BIDS, EP_NQ_LIST)
EP_NQ_SET_MINUS    → (EP_NQ_GET_MINUS,)
```

After a 2xx response on a mutation, the HTTP client calls `cache.invalidate(token_fp, ep)` for each related endpoint. Scoped to the acting token only (no cross-token wipe).

## Changes

### Code

| File | Change |
|------|--------|
| `src/wb/core/constants.py` | Add `REQUEST_CACHE_DB_FILE = 'request_cache.db'` and `REQUEST_CACHE_ENV_VAR = 'WB_REQUEST_CACHE'`. |
| `src/wb/core/cache_policy.py` *(new)* | `CACHEABLE_ENDPOINTS`, `_NEVER_CACHE`, `MUTATION_INVALIDATES`, `canonical_hash(params, body) -> str`, `cache_ttl_seconds(endpoint, token_type) -> float`. |
| `src/wb/storage/request_cache.py` *(new)* | `RequestCache` class — get / put / invalidate / clear / prune / read_all. SQLite WAL, opportunistic expiry pruning per `(token_fp, endpoint)` access. |
| `src/wb/client/http.py` | Wrap `request()` and `request_raw()` with the cache lookup → reserve → double-check → send → observe → put → invalidate flow. `__init__` accepts `request_cache: RequestCache | None = None` and `no_cache: bool = False`. |
| `src/wb/services/_factory.py` | Add `_Container.request_cache()`; thread it through `http_client(...)` along with the `no_cache` flag (read from CLI ctx via `os.environ`). |
| `src/wb/cli/app.py` | Add `--no-cache` global option in `main_callback`; register a new `api_cache_app` typer group. Read `WB_REQUEST_CACHE` env var for the same purpose. |
| `src/wb/cli/api_cache.py` *(new)* | `api_cache_app = typer.Typer(...)`; `wb api-cache status` (table + JSON) and `wb api-cache clear` (--endpoint / --token / --all / default = active token). |
| `src/wb/cli/_helpers.py` | `get_no_cache(ctx)` accessor mirroring `get_compact / get_fields`. |

### Docs

| File | Change |
|------|--------|
| `RATE_LIMITS.md` | New "Request cache" section explaining TTL = period / calls, the bypass flag, and the diag commands. Cross-reference each endpoint's cache eligibility in the per-endpoint tables. |
| `docs/web/rate-limits.md` | Add a paragraph noting the cache exists and what it does — this file is the authoritative low-level reference. |
| `docs/phases/I-15-request-cache.md` *(this file)* | Phase doc. |
| `docs/IMPROVEMENTS.md` | Add I-15 row on completion (handled by `phase-complete`). |
| `docs/PROGRESS.md` | Status flip on completion (handled by `phase-complete`). |

### Tests

- `tests/unit/test_cache_policy.py` *(new)* — `CACHEABLE_ENDPOINTS ∪ _NEVER_CACHE` covers `ENDPOINT_LIMITS` exactly; `cache_ttl_seconds` returns `period / calls`; `canonical_hash` is order-independent on dict params; mutation map keys are all in `_NEVER_CACHE`; mutation invalidation targets are all in `CACHEABLE_ENDPOINTS`.
- `tests/unit/test_request_cache.py` *(new)* — get/put/invalidate/expiry; cross-process visibility via two `sqlite3.connect`s on the same file; opportunistic prune on access; `force_memory=True` works without a file; concurrent `INSERT OR REPLACE` doesn't corrupt rows.
- `tests/unit/test_http_cache_integration.py` *(new)* — mock `httpx.Client.request`; assert: cacheable GET hits HTTP once, second call returns from cache; non-2xx never written; mutation invalidates related cacheable entries; `no_cache=True` fully bypasses; ineligible endpoints (no prior) bypass; `RateLimitError` triggers the double-check path and returns cached on hit.
- `tests/unit/test_cli_api_cache_commands.py` *(new)* — `api-cache status` JSON shape; `api-cache clear --endpoint X` deletes only matching rows; `api-cache clear --all` requires `--yes` in interactive mode and proceeds in JSON mode.
- Existing tests: rerun `tests/unit/test_factory.py`, `tests/unit/test_http_client.py`, `tests/unit/test_endpoint_budget.py` to confirm no regressions.

## Verification

- Full suite green (`pytest tests/unit/ -v`).
- Manual on the local Base profile:
  - `wb stats product-spend --nms 1,2,3 --from <past> --to <past>` twice within 60 min — second call returns identical payload without firing HTTP. Verify by `wb rate status` showing `last_seen_ago_s` does not reset on the second call.
  - `wb campaign list` populates cache; `wb campaign start <id> --apply` invalidates `EP_CAMPAIGN_INFO`; the next `wb campaign list` fires a fresh HTTP call.
  - `wb --no-cache stats product-spend ...` always hits WB regardless of cache state.
  - `wb api-cache status` shows entries grouped by `(seller, token, endpoint)` with `cached_at`, `expires_at`, byte size.
  - `wb api-cache clear --endpoint /api/advert/v2/adverts` deletes only matching rows; status confirms the wipe.
- Cross-process: open two terminals, run the same `stats product-spend` simultaneously. One hits WB; the other returns from cache (or fails with `retry_after` if the race lost narrowly).

## Risks / unknowns

- **Curated allowlist requires upkeep.** New endpoints added without categorising will be silently uncached. Mitigated by the policy assertion test.
- **Mutation invalidation is hand-curated.** A new mutation that doesn't update `MUTATION_INVALIDATES` leaves stale reads in cache for up to TTL. Documented in the contract; `wb --no-cache` and `wb api-cache clear` are the escape hatches.
- **Externally-modified state** (someone changes a campaign in the WB seller portal) is invisible until TTL — for Base tokens up to 60 min. Document `--no-cache` prominently.
- **Personal tokens see no benefit.** TTLs are sub-second. Acceptable: no regression, no win. The cache simply doesn't trigger.
- **Concurrency double-check is best-effort, not single-flight.** Real coalescing would need an in-flight claims table. Listed in out-of-scope; revisit if real concurrency pain emerges.

## Out of scope (potential follow-ups)

- Single-flight / request coalescing via in-flight claims table.
- `--allow-stale` flag to serve expired payloads when the budget is locked.
- Auto-detection of token type from the JWT (covered by future R-6).
- Cache-warming command (`wb api-cache warm` to pre-populate before a heavy workflow).

## Sequencing

I-15 lands after R-5 (we depend on `select_prior` for TTL derivation) and before F-16 (the script-side fix benefits from the cache being in place; without the cache, F-16 needs more defensive code).

## Live test results (2026-04-27)

Verified end-to-end against the operator's local Base-token profile (`seller_id 407bbe2b-…`):

1. **Cache populates on first call:** `wb --json campaign list` → 79 KB response cached at
   `(token_fp=def07bba…, endpoint=/api/advert/v2/adverts)` with TTL = 3600 s
   (`soonest_expires_in_s: 3599.6`). Confirmed via `wb --json api-cache status`.
2. **Second call hits cache:** identical `wb --json campaign list` returned the
   same payload without firing HTTP. Verified via `wb rate status` —
   `last_seen_ago_s` advanced with real-time elapsed (1 s) but did NOT reset to
   zero, which would happen on a network call.
3. **`--no-cache` bypass:** `wb --no-cache --json campaign list` correctly
   ignored the cache and tried to hit WB. WB's Base 1/h budget was already
   exhausted from step 1, so the call exited with `RateLimitError(retry_after=3576)`
   — the exact F-16 bug scenario, now visibly fixed by the cache when not
   bypassed.
4. **Test suite:** 1275 passed, 1 deselected (the pre-existing
   `test_auth_list_empty` env-related failure documented in PROGRESS.md).
   No regressions.

This live demonstration proved the structural fix: under default behavior,
the cache absorbs the second N-th call inside the cooldown window, eliminating
the 1-hour lockout class of bugs that motivated F-16.

## Naming note

The plan originally proposed `wb cache status / clear` for the diagnostic
commands. That namespace was taken at I-15 ship time by the existing
snapshot-cache CLI from phase 7 (`wb cache list / snapshot / clear`), which
manages a different concern (manually-triggered campaign-state snapshots for
time-series tracking). I-15 therefore shipped its commands under
`wb api-cache status / clear` to avoid the clash.

**Renamed in I-16 (v0.33.0):** the I-15 HTTP cache commands moved to their
preferred namespace `wb cache status / clear`; the phase-7 snapshot CLI moved
to `wb snapshot ...` (with the `snapshot` / `snapshot-all` subcommands renamed
to `capture` / `capture-all`). All references to `wb api-cache` in this
document describe the original I-15 ship; the live commands are now `wb cache`.
See [I-16 phase doc](I-16-rename-cache-snapshot.md).
