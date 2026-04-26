# Phase R-5 — Token-type-aware rate handling + `wb rate` overhaul + skill refresh

**Status:** 🔲 PLANNED · **Depends on:** R-4 (metadata-driven substrate must be in place)
**Resolves:** F-15
**Plan:** [analyze-why-the-wb-gentle-lightning.md](../../../../Users/teocci/.claude/plans/analyze-why-the-wb-gentle-lightning.md) (out-of-scope follow-up)

## Context

WB applies **per-token-type** rate limits on every advert endpoint we use. The swagger
files in `docs/swagger/` carry the full per-type table (4 rows: Personal / Service /
Base / Test) for each endpoint that has one — earlier reading missed this because the
column header is "Type", not "Token type". For most endpoints Personal == Service and
Base is dramatically tighter (typical: 1–5 requests per hour with multi-minute burst
intervals).

The CLI currently keys `ENDPOINT_LIMITS` on path only and assumes the
Personal / Service numbers everywhere. For Base tokens — which are what is in use
locally — this is wrong from the very first call: `EndpointBudget` bootstraps with
the Personal prior, fires the request, and either (a) gets `remaining=0` and falls
back to the interval-based wait derived from the wrong period, or (b) trips a 429
that locks the endpoint for 30 minutes before WB's headers correct the budget.

R-5 gives the CLI the missing dimension (token type), persists it on the profile so
agents can act on it deterministically, switches `wb rate probe` to a Base-safe
default, and refreshes the agent skills so they don't blindly recommend a probe that
costs a 30-minute lockout. The metadata-driven `EndpointBudget` from R-1..R-4
remains the runtime authority — R-5 only fixes the bootstrap prior so first-call
behaviour matches the Base reality before any header data exists.

## What stays out of scope

- **Auto-detecting token type from the JWT.** The discriminating claim is unknown
  until we have a non-Base token to diff against; the local profiles are all Base.
  Defer to a future R-6 phase. Until then, `Profile.token_type` defaults to `'base'`
  (the safer assumption) and is overridable via CLI flag.
- **`wb auth whoami`** — A-3 will surface token type alongside other profile fields.
- **Test tokens.** Not in production use; we keep them as a valid enum value but
  don't ship `BASE_OVERRIDES`-style entries for them.
- **Per-category token types.** A single `token_type` per profile, applied to every
  category in `Profile.tokens`. Real sellers use one token type across the board; if
  this turns out to be wrong we can elevate to per-category later.

## Catalog (extracted from swagger)

Built by parsing every `| Type | Period | Limit | Interval | Burst |` table in
`docs/swagger/*.yaml` and matching to each `EP_*` constant in `wb.core.constants`.
Units are normalised to `(burst, interval_seconds)` matching the existing
`ENDPOINT_LIMITS` convention (when `burst=1`, the entry is the interval; otherwise
the burst over the period).

| Endpoint constant | Personal/Service prior (current) | **Base override (new)** |
|---|---|---|
| `EP_CAMPAIGN_FULLSTATS`     | `(1, 20.0)`   | `(1, 3600.0)` — 1 req per hour |
| `EP_RECOMMENDED_BID`        | `(5, 60.0)`   | `(1, 180.0)` — 20/h, burst=1 → 3 min interval |
| `EP_ELIGIBLE_SUBJECTS`      | `(1, 12.0)`   | `(1, 1800.0)` — 2/h, burst=1 → 30 min interval |
| `EP_CAMPAIGN_INFO`          | `(5, 1.0)`    | `(1, 3600.0)` — 1 req per hour |
| `EP_CAMPAIGN_RENAME`        | `(5, 1.0)`    | `(1, 1800.0)` — 2/h, 30 min interval |
| `EP_BUDGET_DEPOSIT`         | `(1, 1.0)`    | `(1, 720.0)` — 5/h, 12 min interval |
| `EP_ACCOUNT_BALANCE`        | `(1, 1.0)`    | `(1, 1800.0)` — 2/h, 30 min interval |
| `EP_BID_SET`                | `(5, 1.0)`    | `(1, 1800.0)` — 2/h, 30 min interval |
| `EP_NQ_STATS`               | `(10, 60.0)`  | `(1, 720.0)` — 5/h, 12 min interval |
| `EP_NQ_STATS_DAILY`         | `(10, 60.0)`  | `(1, 1800.0)` — 2/h, 30 min interval |
| `EP_NQ_SET_BIDS` / `_DEL_BIDS` | `(2, 1.0)` | `(1, 720.0)` — 5/h, 12 min interval |
| `EP_FUNNEL_PRODUCTS` / `_HISTORY` / `_GROUPED` | `(3, 60.0)` | `(1, 1800.0)` — 2/h, 30 min interval |
| `EP_SEARCH_REPORT` / `_GROUPS` / `_DETAILS` / `_TEXTS` / `_ORDERS` | `(3, 60.0)` | `(1, 3600.0)` — 1/h |
| `EP_CSV_CREATE` / `_LIST` / `_RETRY` | `(3, 60.0)` | `(1, 3600.0)` — 1/h |
| `EP_WAREHOUSE_REMAINS_CREATE` | `(1, 60.0)` | `(1, 900.0)` — 4/h, 15 min interval |
| `EP_WAREHOUSE_REMAINS_STATUS` | `(1, 5.0)` | `(1, 900.0)` — 4/h, 15 min interval |

`EP_CAMPAIGN_BUDGET` (`/adv/v1/budget` GET) is uniform across all token types
(`(4, 1.0)` everywhere) — no `BASE_OVERRIDES` entry. Only `EP_BUDGET_DEPOSIT`
(`/adv/v1/budget/deposit` POST) is Base-stratified.

Endpoints with no per-type table in swagger (`EP_CAMPAIGN_CREATE` /
`_START` / `_PAUSE` / `_STOP` / `_DELETE`, `EP_NQ_LIST` / `_GET_BIDS` /
`_GET_MINUS` / `_SET_MINUS`, `EP_STOCKS_WB_WAREHOUSES`) keep the Personal prior
for Base too. Header-driven `EndpointBudget` will self-correct from the first WB
response if the real Base limit is tighter; this matches our current behaviour and
avoids over-throttling endpoints we have no data on.

## Changes

### Code

| File | Change |
|------|--------|
| `src/wb/core/rate_limits.py` | Add `BASE_OVERRIDES: dict[str, tuple[int, float]]` (the right column above) and a `select_prior(path, token_type) -> tuple | None` helper. Lookup logic: `BASE_OVERRIDES[path]` when `token_type == 'base'` and the entry exists, else `ENDPOINT_LIMITS[path]`, else `None`. |
| `src/wb/core/constants.py` | Add `TOKEN_TYPES: tuple[str, ...] = ('personal', 'service', 'base', 'test')` and `DEFAULT_TOKEN_TYPE = 'base'`. |
| `src/wb/auth/profiles.py` | Add `Profile.token_type: str` field (default `DEFAULT_TOKEN_TYPE`); persist in `to_dict` / `from_dict`. Add `ProfileStore.set_token_type(profile_name, token_type)` that validates against `TOKEN_TYPES` and saves. Backward compat: missing key in JSON → default 'base'. |
| `src/wb/cli/auth.py` | Add `--token-type` option to `auth login` (default unset). When set, validate against `TOKEN_TYPES` and call `store.set_token_type(...)` after `save_token`. Echo the resolved type in the success line. |
| `src/wb/services/_factory.py` | In `http_client(...)`, when `with_rate_limits=True`, resolve token_type: prefer profile's stored value; fall back to `DEFAULT_TOKEN_TYPE`. Pass it into `WbHttpClient`. |
| `src/wb/client/http.py` | `WbHttpClient.__init__` accepts `token_type`; `_pre_flight` calls `select_prior(path, token_type)` instead of `ENDPOINT_LIMITS.get(path)`. |
| `src/wb/cli/rate.py` `rate_probe` | **Removed.** Vestigial since R-1..R-4 made the runtime header-driven — every real call updates `endpoint_budget`. The two replacement workflows already exist: `wb auth ping` for connectivity / token-validity (uniform `/ping` rate, not Base-stratified) and `wb rate status` for budget visibility (no network). Tests for the probe are removed; the only remaining test verifies the subcommand is no longer registered. |
| `src/wb/cli/rate.py` `rate_status` | Add `token_type` to each token group in the JSON payload and to the table header line. |

### Skills (`.claude/skills/`)

| File | Change |
|------|--------|
| `wb-rate-guide/SKILL.md` | New "Token-type caveats" section. State that the rates in the table are Personal/Service. Base limits are 30–60× tighter on the same endpoints. Point at `wb rate status` (budget) and `wb auth ping` (connectivity) — note that `wb rate probe` no longer exists. |
| `wb-rate-recover/SKILL.md` | Drop the entire probe-based "verification probe" section; replace with a "When `rate status` shows nothing locked but the call still fails" narrative. Simplified decision tree: Base waits the documented Base interval; Personal/Service just retries (the budget layer blocks if WB still says no). |
| `wb-pulse/SKILL.md` | Single line confirming the bid-baseline read is one `EP_RECOMMENDED_BID` call per product — already 1/3-min for Base, so no behaviour change but flag it. |
| `wb-assess/SKILL.md` | Note that the morning balance read counts against a 2/h Base bucket; do not run more than once per session. |
| `wb-daily-report/SKILL.md` | Note that the per-product breakdown chains `EP_CAMPAIGN_FULLSTATS` (1/h Base) and `EP_FUNNEL_PRODUCTS` (2/h Base) — for Base sellers, expect a multi-minute throttle on a 5+ campaign report. |

### Docs

| File | Change |
|------|--------|
| `RATE_LIMITS.md` | Add a "Base override" column to the per-command table for every endpoint with a `BASE_OVERRIDES` entry. New section "Token type" near the top explaining the bootstrap-prior selection. |
| `docs/phases/F-15-rate-base-token-blindspot.md` | Mark the swagger-blindspot bullet as resolved (the data was always there, our regex missed it). Cross-reference this plan. |
| `docs/PROGRESS.md` | Status flip happens in the post-implementation `phase-complete` step, not now. |
| `docs/IMPROVEMENTS.md` | Add R-5 entry on completion. Also handled by `phase-complete`. |
| `docs/FIXES.md` | Add F-15 closure entry on completion. Also handled by `phase-complete`. |

### Tests

- `tests/unit/test_rate_limits.py` (new) — `select_prior(path, 'base')` returns the
  override; `select_prior(path, 'personal')` returns the standard prior;
  `select_prior(unknown_path, ...)` returns `None`.
- `tests/unit/test_profiles.py` — round-trip `Profile.token_type` through
  `to_dict` / `from_dict`; missing key defaults to `'base'`; invalid value raises.
- `tests/unit/test_factory.py` — given a profile with `token_type='base'`, the
  HTTP client receives the Base override prior on a known stratified endpoint.
  Repeat for `personal` → standard prior.
- `tests/unit/test_cli_rate.py` (existing) — drop the entire `TestRateProbe` /
  `TestRateProbeBaseGuard` blocks (probe removed). New `TestRateProbeRemoved`
  asserts the subcommand is no longer registered. New `TestRateStatusTokenType`
  covers the `token_type` field in the `rate status` payload.
- `tests/unit/test_cli_auth.py` — `wb auth login --token-type base` persists the
  field; invalid value rejected with exit code 2.

## Verification

- Full suite green (`pytest tests/unit/ -v`).
- Manual on the local Base profile:
  - `wb auth list` shows `token_type: base` for both profiles (legacy profiles
    read as the default 'base' from `Profile.from_dict` — no migration needed).
  - `wb auth status` shows `Token type: base`.
  - `wb rate status` shows `token_type` per token group.
  - `wb rate --help` lists only the `status` subcommand; `wb rate probe` is
    gone (exits with usage error mentioning the unknown command).
  - `wb stats campaign <id>` on a previously-untouched campaign: pre-flight wait
    matches the 1/h Base prior for `EP_CAMPAIGN_FULLSTATS`, not the 1/20-s
    Personal prior. The slow path is the correct path here — 30-minute Base
    bucket, not a stuck CLI.

## Risks / unknowns

- **JWT discriminator unknown.** Until we identify the claim that signals token
  type, switching from Base default to auto-detect is impossible. R-5 ships with
  manual override; auto-detect lands in R-6 once a Personal token reference is
  available.
- **The Base catalog might miss a future endpoint** WB ships under an unmapped
  path. The metadata-driven `EndpointBudget` is the safety net: even when the
  prior is wrong, the first 429 corrects the bucket and locks only the offending
  endpoint, not the seller.
- **Non-stratified swagger endpoints** (campaign mutations, normquery list/get,
  stocks-warehouses) might quietly have Base-tighter limits not documented in
  the YAML. We accept this — same posture as today, with header self-correction.

## Sequencing

R-5 lands after R-4 (R-4 already shipped — v0.30.0) and before A-3 (which
displays seller info via `wb auth whoami` and benefits from token-type
detection landing first).
