# Changelog

All releases. Detailed phase notes: [docs/phases/](docs/phases/).

## v0.35.0 (2026-05-06) — BREAKING
- I-18: `wb stats daily-report` default JSON shape expanded to 11 fields (spend side: `views`, `clicks`, `ad_orders`, `spend`, `avg_position`; funnel side: `opens`, `cart_adds`, `orders`, `order_sum`, `buyouts`). Adds `--days N`, `--from/--to` date-range modes (max 7 days). **Breaking**: `ad_spend` renamed to `spend`, `total_orders` renamed to `orders` — callers using `--fields` narrow-path must update to `--fields nm_id,name,spend,orders`. Old response-cache entries with the old schema auto-degrade to a fresh fetch.

### Breaking
- `DailyReportRow` field `ad_spend` → `spend`; field `total_orders` → `orders`. Update any `--fields` projection or downstream script that referenced these key names.

## v0.34.0 (2026-05-04)
- I-17: `_find_campaign_ids_for_nms` now filters to running (9) + paused (11) campaigns before building the fullstats batch, preventing stopped/archived legacy campaigns from burning `EP_CAMPAIGN_FULLSTATS` rate-limit slots on Base tokens.

## v0.33.1 (2026-05-04)
- F-18: `FunnelHistoryDay.from_api` now reads the `date` key (real WB API field) with `dt` as fallback, fixing always-empty `dt` on live funnel-history responses.

## v0.33.0 (2026-04-28) — BREAKING
- I-16: rename `wb cache` → `wb snapshot` (Phase 7 domain snapshots) and `wb api-cache` → `wb cache` (I-15 HTTP response cache). The two namespaces were backwards from common usage of "cache" (transparent perf layer) vs. "snapshot" (explicit point-in-time captures); the I-15 phase doc explicitly *wanted* `wb cache` for the HTTP layer but couldn't take it because Phase 7 owned the namespace. Hard rename, no aliases — old commands return `No such command` (Typer's auto-suggester catches `api-cache` → `cache` for free). The capture verb avoids the `snapshot snapshot` noun-noun stutter: `wb cache snapshot --campaign N` becomes `wb snapshot capture --campaign N`, and `wb cache snapshot-all` becomes `wb snapshot capture-all`. `wb cache clear` and `wb snapshot clear` coexist cleanly under their respective groups (mirrors `git branch -d` vs `git tag -d`). Source files renamed via `git mv` to preserve blame: `src/wb/cli/cache.py` → `src/wb/cli/snapshot.py` (with `cache_app` → `snapshot_app` + verb / function renames), `src/wb/cli/api_cache.py` → `src/wb/cli/cache.py` (with `api_cache_app` → `cache_app`). Test files renamed and argv lists updated to match. Docs sweep: `AGENT.md` rewritten with two distinct sections, `RATE_LIMITS.md` and `docs/web/rate-limits.md` updated, `docs/phases/7-cache.md` and `docs/phases/I-15-request-cache.md` annotated with rename notes (originals kept for historical accuracy). Storage layer untouched — `cache.db` and `request_cache.db` paths and schemas are CLI-facing only. No agent skills in `.claude/skills/` reference these commands, so the breaking change has zero impact on shipped automation. 1295 tests still passing.

### Breaking
- `wb cache list/snapshot/snapshot-all/clear/history *` removed — use `wb snapshot list/capture/capture-all/clear/history *`.
- `wb api-cache status/clear` removed — use `wb cache status/clear`.

## v0.32.2 (2026-04-28)
- F-17: CLI hardcoded `'default'` profile fallback fixed across 13 call sites in `src/wb/cli/{cache,budget,bid,campaign,cluster}.py` — running `wb cache list` (or any sibling subcommand) from a directory without `.env` no longer fails with `Profile 'default' does not exist` when no profile literally named `default` exists. New helper `resolve_profile_name(ctx)` in `src/wb/cli/_helpers.py` returns the `--profile` flag value if present, otherwise `ProfileStore.active_profile_name` — mirrors the auth layer's own `get_profile(None)` fallback so commands never invent a magic profile name. Audit-log helper signatures `_log_mutation` (campaign/cluster) and `_log_bid_mutation` (bid) tightened from `profile: str | None` to `profile: str` since they're now always called with a resolved name. Bonus fix discovered while diagnosing: `wb cache list` summary path passed a dict to `renderer.display()` for table mode, making Rich unpack each table-name string into single-character columns (`c | a | m | p | a | i | g | n | s`); now branches on `renderer.is_json` so JSON keeps the dict shape and table mode passes the pre-built rows list. 2 new regression tests in `tests/unit/test_cli_cache.py` cover both the full-string column rendering and the preserved JSON shape. Live-verified from a non-project cwd: command resolves to active profile, two-column table, full table names

## v0.32.1 (2026-04-27)
- F-16: `scripts/generate_daily_wb_report.py` rate-limit handling. Drops the `<repo>/.home` HOME isolation that prevented `wb rate status` from the operator's main shell from seeing locks the script's subprocesses observed (the script copied `profiles.json` and `audit.jsonl` but not `rate_limits.db`). Subprocesses now inherit the parent env and read/write `~/.wb-cli/rate_limits.db` directly. Drops the `SPEND_CHUNK_SIZE = 80` per-chunk loop in `fetch_spend_payload` — the CLI already chunks campaign-stats batches at `FULLSTATS_BATCH_SIZE` and (since I-15) caches `list_campaigns` so repeated invocations share the campaign list; outer chunking added no value and turned every chunk into its own subprocess + rate-limit consumer. Drops the `retry_waits=[20, 60]` retry loop in `run_wb_command` — the CLI already bails fast at `_RETRY_AFTER_BAIL_OUT_SECONDS=60`, so retrying with shorter waits couldn't ride out the multi-minute / multi-hour Base cooldowns that motivated this fix. New `_parse_retry_after_from_envelope` reads `error.retry_after` from the CLI's JSON envelope; new `RateLimitedError(retry_after=...)` carries it. New `find_active_lock_for(status, endpoints)` filters lock detection to a specific endpoint family; `acquire_payloads` re-runs `read_rate_status` between phases scoped to `SPEND_RELEVANT_ENDPOINTS = {/api/advert/v2/adverts, /adv/v3/fullstats}`. When locked and no persisted artifact exists for the date, the script now exits 5 with a single-line message naming the locked endpoint and the WB-supplied cooldown — pre-fix the same path produced a Python traceback after ~80 s of doomed retries. 18 new unit tests in `tests/unit/test_daily_report_script.py` cover envelope parsing, fast-fail on exit 5, the endpoint-scoped lock filter, and confirmation that the legacy HOME-isolation constants no longer exist on the module. Live-verified: clean exit-5 produced under real WB rate limits. Operator follow-up: `rm -rf <repo>/.home` (no longer used). Resolves bug `bugs/2026-04-27-product-spend-endpoint-lock.md`

## v0.32.0 (2026-04-27)
- I-15: cooldown-tied HTTP-layer request cache + `wb api-cache` diag commands. New `RequestCache` (`src/wb/storage/request_cache.py`) at `~/.wb-cli/request_cache.db` (SQLite WAL, cross-process). New `cache_policy.py` (`src/wb/core/cache_policy.py`) defines the cacheable allowlist, the never-cache set, the mutation→read-invalidation map, and `canonical_hash(params, body)`. TTL = `period / calls` from `select_prior(...)` — for Base `EP_CAMPAIGN_INFO` (1/h) the cache lives 3600 s, exactly the window WB will refuse a refresh in, so cache validity is bounded by the rate-limit reality and can never serve data staler than what a real refresh would deliver. For Personal tokens TTLs are sub-second so the cache effectively no-ops. `WbHttpClient.request` now consults the cache before reserve and writes 2xx responses back; on `RateLimitError` from `EndpointBudget.reserve()` it does one extra `cache.get` (the double-check) to handle the realistic race where another process publishes during reserve. Mutations on `MUTATION_INVALIDATES` keys drop their related cached reads scoped to the acting token. New global `--no-cache` flag and `WB_REQUEST_CACHE=disabled` env var bypass the cache for live-data emergencies. New `wb api-cache status` / `wb api-cache clear` diag commands modeled on `wb rate status` (the legacy `wb cache` group from phase 7 — snapshot cache — is unchanged; the new commands ship under `api-cache` to keep the namespaces distinct). 74 new unit tests (`test_cache_policy.py`, `test_request_cache.py`, `test_http_cache_integration.py`, `test_cli_api_cache_commands.py`) cover policy categorisation, SQLite cross-process visibility, get/put/expiry/invalidate/clear, the double-check race path, and CLI command behavior. Live-verified end-to-end on the local Base profile: second `wb campaign list` within the hour hits the cache without firing HTTP (`rate status` `last_seen_ago_s` advances with real time but doesn't reset), `--no-cache` correctly bypasses and produces the expected `RateLimitError(retry_after=3576)`. RATE_LIMITS.md and docs/web/rate-limits.md updated with the cache contract

## v0.31.0 (2026-04-27)
- R-5 + F-15: token-type-aware rate handling. New `Profile.token_type` field (default `'base'` — the safer assumption; legacy profiles auto-default through `from_dict`) settable via `wb auth login --token-type {personal|service|base|test}` and surfaced in `wb auth list` / `wb auth status`. New `BASE_OVERRIDES` map + `select_prior(path, token_type)` helper in `src/wb/core/rate_limits.py` extracted from the per-Type rate-limit tables in `docs/swagger/*.yaml` (most stratified endpoints drop from per-second Personal limits to 1–5 calls per hour on Base). `WbHttpClient._pre_flight` resolves the prior through `select_prior`; `_factory.py` threads token_type from the profile through to the HTTP client. `wb rate status` now shows `token_type` per token group. **`wb rate probe` removed** — vestigial since R-1..R-4 made the runtime header-driven; on Base it would either be a 30-min footgun or a refusal. Replacements already exist: `wb auth ping` for connectivity / token-validity (uniform `/ping` rate), `wb rate status` for budget visibility (no network). Skills updated: `wb-rate-guide`, `wb-rate-recover`, `wb-pulse`, `wb-assess`, `wb-daily-report`, plus `RATE_LIMITS.md` rewritten with side-by-side Personal/Service vs Base columns. Live-verified on local Base profile

## v0.30.0 (2026-04-26)
- R-4 + F-14: cleanup after the metadata-driven rate-limit redesign. Deletes `SellerCooldownLock` (`src/wb/core/rate_limiter.py`) and `compute_seller_fingerprint`; deletes `SELLER_GLOBAL_BUDGET` / `SELLER_GLOBAL_SCOPE_KEY` (`src/wb/core/constants.py`); promotes `_extract_seller_id` from `wb.services._factory` to public `extract_seller_id` in `wb.core.rate_limiter` (only JWT helper left in that module besides `compute_token_fingerprint`). `wb rate probe` now goes through `EndpointBudget`: pre-flight reads the row for `(token_fp, /adv/v1/balance)` instead of a seller-wide TTL lock, so a cooldown on one endpoint no longer blocks `rate probe` on a different one. **Breaking JSON shape for `wb rate probe`**: `seller_fingerprint` is replaced by `seller_id` (plaintext `sid`) alongside the existing `token_fingerprint`. `scripts/generate_daily_wb_report.py` and the `wb-rate-recover` skill (`SKILL.md`) updated to consume the new R-3 `{sellers: [...]}` shape from `wb rate status` (per-endpoint `locked` flag instead of the deleted seller-wide one). RATE_LIMITS.md "How throttling works" section rewritten to describe the bootstrap-prior + header-driven runtime model. Resolves bug `bugs/2026-04-25-rate-status-misses-seller-cooldown.md` and closes phases R-1..R-4 + F-14. Out-of-scope follow-up: dropping the `seller_cooldown` SQLite table is deferred one cycle to keep the migration non-destructive

## v0.29.0 (2026-04-26)
- R-3: `wb rate status` overhaul — reads `EndpointBudget.read_all()` directly and groups output by plaintext `seller_id`, then by token fingerprint, then by endpoint (locked first). Each row carries `remaining`, `bucket_limit`, `reset_in_s`, `last_seen_ago_s`, `locked`. Eliminates F-14 by construction: a cooldown recorded under one token surfaces from any shell, regardless of which token is currently configured. Drops the per-token `SellerCooldownLock` lookup and the `rate_limit_log` 5-minute activity panel. **Breaking JSON shape**: top-level `{now_epoch, profile, sellers: [...]}`; pre-R-3 keys (`seller_fingerprint`, `seller_cooldown_seconds`, top-level `locked`, `endpoint_activity_5min`) are gone. `wb rate probe` is unchanged in this release; `SellerCooldownLock` and the `wb-rate-recover` skill / `generate_daily_wb_report.py` script update in R-4

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
