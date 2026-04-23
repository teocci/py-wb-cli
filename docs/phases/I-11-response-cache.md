# Phase I-11 — Response Cache + 5xx/429 Retry Split (v0.24.0)

**Date:** 2026-04-24
**Tests:** 1098/1099 (1 pre-existing env-isolation failure in `test_auth_list_empty`, unrelated)

## What Was Built

- **Response cache for past-day queries.** New `src/wb/storage/response_cache.py` — SQLite WAL-mode store at `~/.wb-cli/response_cache.db`. Read-through cache keyed by `(endpoint, sha256-prefix(token), canonical_params)`; entries pruned after 90 days.
- **Past-day gate.** `is_past_day_range(date_from, date_to)` cached only when both dates are strictly before today. Current-day and future queries always hit WB.
- **Services wired.** `StatsService.get_product_spend`, `StatsService.get_daily_report`, `AnalyticsService.get_product_funnel`, `get_product_history`, `get_grouped_history` now pass through `_cached_or_fetch`.
- **Retry classification.** `wb.client.http` splits 5xx from 429 — 5xx uses a longer backoff (5 s → 15 s → 45 s + jitter) and raises the new `UpstreamError` (exit 6, code `UPSTREAM_ERROR`) on exhaustion; 429 keeps short backoff + `RateLimitError` (exit 5, code `RATE_LIMITED`).
- **Token fingerprinting.** Raw tokens never touch the cache file — only the first 16 hex chars of their SHA-256 digest appear in keys.

## Files Changed

| File | Change |
|------|--------|
| `src/wb/storage/response_cache.py` | New module: `ResponseCache`, `is_past_day_range`, `make_cache_key`, `token_fingerprint` |
| `src/wb/core/exceptions.py` | Added `UpstreamError(ApiError)` with `error_code='UPSTREAM_ERROR'` |
| `src/wb/core/constants.py` | `RESPONSE_CACHE_DB_FILE`, `RESPONSE_CACHE_RETENTION_DAYS=90`, `UPSTREAM_RETRY_BASE_DELAY=5.0`, `UPSTREAM_RETRY_MULTIPLIER=3.0` |
| `src/wb/client/http.py` | Retry delay chosen per status class; 5xx exhaustion raises `UpstreamError` |
| `src/wb/services/stats.py` | `_cached_or_fetch` helper; `get_product_spend` / `get_daily_report` split into cache-wrap + `_*_fresh` fetcher |
| `src/wb/services/analytics.py` | `_cached_or_fetch` helper; funnel methods split into cache-wrap + `_fetch_*` fetcher; history serializer handles nested `FunnelHistoryDay` |
| `src/wb/services/_factory.py` | `ServiceContainer.response_cache()`; `create_stats_service` / `create_analytics_service` pass cache + token fingerprint |
| `tests/unit/test_response_cache.py` | 25 new tests (date gate, key derivation, get/put round-trips, pruning, persistence, sqlite-error handling) |
| `tests/unit/test_response_cache_integration.py` | 7 new tests (past-day cache hit, current-day bypass, nested history reconstruction) |
| `tests/unit/test_exceptions.py` | 4 new tests for `UpstreamError` |
| `tests/unit/test_http_client.py` | 8 new tests for 5xx→UpstreamError, 429→RateLimitError, mixed-status flows, upstream delay schedule |
| `CLAUDE.md` | Exit codes table documents `UPSTREAM_ERROR`; new "Response Cache" section |
| `docs/PROGRESS.md`, `docs/IMPROVEMENTS.md` | I-11 row flipped to DONE |

## Live Test Results

```bash
# Past-day query — first call ~2.08 s (hits WB).
$ time wb --json --compact analytics sales-funnel products \
    --from 2026-04-22 --to 2026-04-22 --limit 3
real    0m2.080s

# Same query — second call ~0.56 s (cache hit, zero API calls, no warnings).
$ time wb --json --compact analytics sales-funnel products \
    --from 2026-04-22 --to 2026-04-22 --limit 3
real    0m0.560s

# Current-day query — both runs hit WB (correctly bypass cache).
$ rows in response_cache.db: 1   # past-day row only; current-day never cached
```

## Agent Usage

Agents that repeat past-day queries (skills like `wb-assess`, `wb-pulse`, `wb-daily-report`) now pay zero API cost on the second run within the 90-day retention window. Cross-process: two parallel `wb` invocations querying the same past date share the cache via SQLite WAL.

Error diagnosis is clearer: a 5xx storm surfaces as `UPSTREAM_ERROR` (exit 6), not `RATE_LIMITED` (exit 5) — so agents can tell WB infra stress apart from a genuine rate-limit event and react differently (e.g. wait longer on upstream vs. slow the call cadence on 429).
