# Changelog

All releases. Detailed phase notes: [docs/phases/](docs/phases/).

## v0.28.0 (2026-04-26)
- R-1+R-2: metadata-driven rate-limit redesign — new `EndpointBudget` (`src/wb/core/endpoint_budget.py`) keys per-(token, endpoint) bucket state in a new `endpoint_budget` SQLite table, populated from WB's own `X-Ratelimit-*` response headers (parsed via `parse_rate_limit_wait` with the corrected preference order `X-Ratelimit-Retry > Retry-After > X-Ratelimit-Reset` per the official WB doc); `WbHttpClient.request` / `request_raw` now call `_pre_flight(path)` (delegates to `EndpointBudget.reserve` with `max_wait_seconds=60.0` for the F-12 bail-out) and `_observe(path, response)` after every response; the legacy three-layer gate (F-13 `SellerCooldownLock` + static seller-global limiter + per-path limiters) is no longer wired into the runtime path; `ServiceContainer.endpoint_budget()` is the new singleton factory (honours `WB_RATE_LIMITER=memory`); `_extract_seller_id` extracts plaintext `sid` from the JWT for diagnostics. Net change: a 429 on any one endpoint blocks ONLY that endpoint until WB's own reset deadline, not the whole seller. F-13's astronomic compounded cooldowns are eliminated. Live-verified via `wb campaign list` against `/api/advert/v2/adverts`.

## v0.27.0 (2026-04-24)
- I-14: `wb rate probe` — single-call cooldown probe that respects the F-13 lock (no HTTP when already locked), reads WB's `x-ratelimit-remaining` header on 200 so agents can see how close we are to a trip, and writes `x-ratelimit-reset` into the lock on 429. Probes `/adv/v1/balance` (cheapest per-seller endpoint). JSON + table output, 10 s timeout, no retries — `calls_remaining: 0` is the signal agents should treat as "stop before next window resets"

## v0.26.0 (2026-04-24)
- I-13: `wb rate status` diagnostic command — read-only subcommand prints seller cooldown remaining (from F-13 lock) plus 5-minute endpoint activity roll-up from `rate_limits.db`. JSON + table output, no-token no-crash. Lets agents check "am I locked?" without making a network call

## v0.25.5 (2026-04-24)
- F-13: `SellerCooldownLock` short-circuit — new SQLite-backed TTL lock in `~/.wb-cli/rate_limits.db` (new `seller_cooldown` table) records WB-reported cooldown deadlines per seller; `WbHttpClient.request` / `request_raw` consult the lock before any HTTP call and raise `RateLimitError` immediately when active. Populated from F-12's `x-ratelimit-reset`. Cross-process coordination; in-memory fallback on DB errors. Eliminates penalty compounding across `wb` invocations

## v0.25.4 (2026-04-24)
- F-12: honor `x-ratelimit-reset` / `x-ratelimit-retry` on 429 — new `_parse_rate_limit_reset` helper reads WB's undocumented cooldown-timer headers (absent from swagger 429 schema), populates `RateLimitError.retry_after`; `_retry_or_raise` bails out without retrying when reset > 60 s to stop seller-scope penalties from extending under our own retries. Standard `Retry-After` still preferred when present

## v0.25.3 (2026-04-24)
- F-11: dedup `list_campaigns` in `stats daily-report` — `_get_daily_report_fresh` now makes one unfiltered `list_campaigns` call and threads the raw list through `_get_product_spend_fresh` + `_find_campaign_ids_for_nms`, eliminating the duplicate full-scan request. Status filter moves to a new in-memory helper `_collect_nm_ids_from_campaigns`

## v0.25.2 (2026-04-24)
- F-10: seller-scope global rate limiter — new `compute_seller_fingerprint` extracts the JWT `sid` claim so tokens of the same seller share a single budget; `_build_seller_limiter` wires a `SharedRateLimiter` (30 calls / 60 s) at the `_seller_global` scope key in `~/.wb-cli/rate_limits.db`; `WbHttpClient` acquires the seller limiter before the per-path limiter on every request. Falls back to per-token scope for non-JWT tokens; honours `WB_RATE_LIMITER=memory` opt-out

## v0.25.1 (2026-04-24)
- F-9: patient 429 backoff on seller-global throttle — `RateLimitError` now carries `response_body`; `_calculate_delay` switches to the UPSTREAM schedule (5/15/45 s + jitter) when the body contains `"global limiter"`, matching how WB's gateway surfaces seller-wide throttles. Per-endpoint 429s and explicit `Retry-After` headers keep existing semantics

## v0.25.0 (2026-04-24)
- I-12: SQLite-backed cross-process rate limiter — new `SharedRateLimiter` coordinates preemptive throttling across parallel `wb` invocations via `~/.wb-cli/rate_limits.db` (WAL mode, per-`(token_fingerprint, endpoint)` rows, `BEGIN IMMEDIATE` serialisation). Transparent fallback to in-memory `RateLimiter` on DB errors with a single warning per process; `WB_RATE_LIMITER=memory` forces the legacy in-process behaviour

## v0.24.0 (2026-04-24)
- I-11: response cache for past-day stats/analytics + 5xx/429 retry split — read-through SQLite cache at `~/.wb-cli/response_cache.db` for past-day `stats product-spend`, `stats daily-report`, and `analytics sales-funnel` queries; 5xx retries now raise `UpstreamError` (exit 6) with longer backoff (5/15/45s), keeping `RATE_LIMITED` (exit 5) reserved for true 429 events

## v0.23.0 (2026-04-21)
- I-10: `analytics sales-funnel products` — `--min-orders` filter + `--all` auto-pagination (`paginate_all`, page_size=1000)

## v0.22.0 (2026-04-21)
- I-9: `stats daily-report` — per-product ad spend + total platform orders joined from Analytics funnel; `wb-daily-report` skill

## v0.21.0 (2026-04-21)
- I-8: `stats campaigns --status` filter — running/paused/active virtual alias, `get_stats_by_status()` service method

## v0.20.6 (2026-04-20)
- F-8: Empty `PaymentType` crash fix — guard null `payment_type` in `Campaign.from_api()`

## v0.20.5 (2026-04-19)
- F-7: `campaign list --fields` projection fix — route through `renderer.display()`; column/key filtering now honored

## v0.20.4 (2026-04-19)
- F-6: TTY-aware ANSI output — `force_terminal=sys.stdout.isatty()`; plain text when piped

## v0.20.3 (2026-04-19)
- F-5: Budget deposit unit fix (rubles not kopecks) + unified `bid_type` omits `placement_types`

## v0.20.2 (2026-04-17)
- F-4: UTF-8 pipe fix — `sys.stdout.reconfigure` at startup + centralized `_stdout_console` across all CLI modules

## v0.20.0 (2026-04-17)
- I-7: Agent skills — `wb assess` / `wb pulse` native commands + 7 Claude Code skills (wb-launch, wb-optimize, wb-manage, wb-keywords, wb-calibrate)

## v0.19.0 (2026-04-08)
- I-6: Full token category support — 11 categories, `--category all`, `wb auth categories` command

## v0.18.0 (2026-04-07)
- I-5: Polish & agent ergonomics — `--compact` single-line JSON, `--sort-by`/`--top N` on funnel products, `AGENT.md`

## v0.17.0 (2026-04-07)
- I-4: Rate limiting & resilience — `RateLimiter` (sliding window), `RATE_LIMITS.md`, `paginate_all` helper, `_Container` service cache

## v0.16.0 (2026-04-06)
- I-3: Composite commands — `wb product summary`, `wb campaign overview`, idempotent mutations, SDK parity

## v0.15.0 (2026-04-06)
- I-2: Per-product cost tracking — `wb stats product-spend`, booster `avg_position`, fullstats auto-chunking, stats cache write-through

## v0.14.0 (2026-04-06)
- I-1: Batch operations — N+1 elimination, `--ids` multi-campaign, `--bids` inline JSON, auto-chunk analytics, `--fields` output filtering

## v0.13.0 (2026-04-06)
- 8D: Prices & Discounts command — base price, discount %, final buyer price via `discounts-prices-api`

## v0.12.0 (2026-04-04)
- 8C: Report caching & multi-seller storage — 6h TTL file cache + SQLite metadata, `--cache`/`--no-cache` flag

## v0.11.0 (2026-04-04)
- 8B: Stock runway — days-until-stockout via Statistics API sales velocity

## v0.10.0 (2026-04-04)
- 8A: Warehouse inventory reports — async report lifecycle + top products

## v0.9.0 (2026-04-03)
- F-3: Agent-critical fixes — JSON errors, per-NM stats, `Campaign.nm_ids`, shared CLI helpers, `ExitCode` enum

## v0.8.0 (2026-04-03)
- 7: Local SQLite cache — historical snapshots, `wb budget history`, `wb cache` commands

## v0.7.0 (2026-04-03)
- 6: Agent platform support — Python SDK facade (~50 functions), `wb campaign clone`

## v0.6.0 (2026-04-03)
- 5: Optimization workflows — `OptimizerService`, 5 heuristic rules, `wb optimize` commands with `--apply`

## v0.5.0 (2026-04-03)
- 4: Analytics bridge — `AnalyticsClient`, sales funnel, search reports, CSV exports; separate analytics token

## v0.4.0 (2026-04-02)
- 3: Search-cluster control — normquery API, cluster bid mutations, minus phrases, daily stats

## v0.3.2 (2026-04-02)
- F-2: Full API migration — all 14 dead `EP_*` constants replaced; 8 normquery constants added; `PromotionClient` rewritten

## v0.3.1 (2026-03-19)
- F-1: Auth fix — dual auth (API key + portal session), `WB_API_TOKEN` env fallback, `/ping` fix

## v0.3.0 (2026-03-18)
- 2: Core write controls — lifecycle (start/pause/stop/rename/delete), item/placement/budget/bid mutations, `--dry-run`

## v0.2.0 (2026-03-18)
- 1: Read-only visibility — campaign list/get, bids, budget, stats, clusters; `PromotionClient`; 5 service classes

## v0.1.0 (2026-03-18)
- 0: Foundation — CLI scaffold, config, auth, HTTP client, domain models, audit log
