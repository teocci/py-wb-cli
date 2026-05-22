# WB CLI - Claude Code Instructions

## How to Resume Implementation

1. Read `docs/PROGRESS.md` — current version, phase status, and what comes next.
2. Read `docs/DESIGN.md` — architecture decisions and command taxonomy.
3. Say **NEXT** to implement the next pending phase.

Each phase follows this pattern:
- Implement in `src/wb/` following the file layout in `docs/DESIGN.md`
- Write tests in `tests/unit/`
- Run `pytest tests/unit/ -v` — all must pass
- Run the `phase-complete` skill to finalize (version bump, CHANGELOG, commit)

## Quick Commands

```bash
# Activate env (Windows)
source .venv/Scripts/activate

# Run all tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=wb --cov-report=term-missing

# Run the CLI
python -m wb --help
python -m wb version
python -m wb auth --help
```

## Project Layout

```
src/wb/
  cli/          # Typer commands (one file per command group)
  core/         # constants, exceptions, config, output
  domain/       # enums, models (pure data, no I/O)
  auth/         # profiles, token validation
  client/       # HTTP clients (promotion, analytics, portal)
  services/     # business logic / use-cases
  storage/      # audit log, local cache
tests/
  unit/         # pure unit tests (no real HTTP, no real FS beyond tmp_path)
  integration/  # tests against real WB API (requires token)
  fixtures/     # shared test data
docs/
  PROGRESS.md   # phase status index
  DESIGN.md     # architecture reference
  FIXES.md      # fix index
  IMPROVEMENTS.md  # improvement index
  RELEASE.md    # release procedure
  phases/       # per-phase detail files
```

## Coding Rules

- Single quotes for all strings
- Python 3.11+ syntax: `X | None`, `list[str]`, `match/case`
- No `typing.Optional`, `typing.Union`, `typing.List`, etc.
- `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants
- Google-style docstrings on all public API
- Functions ≤ 30 lines, max 3 nesting levels
- No hardcoded URLs, paths, magic numbers — use `constants.py`
- Never log secrets; mask tokens as `key[:4]...key[-4:]`

## Exit Codes

| Code | Error code | Meaning |
|------|------------|---------|
| 0 | — | success |
| 2 | `VALIDATION_ERROR` | input validation failure |
| 3 | `AUTH_FAILURE` | authentication failed (bad/expired token) |
| 4 | `AUTH_MISSING_SCOPE` | token lacks required scope |
| 5 | `RATE_LIMITED` | 429 after retries exhausted |
| 6 | `API_ERROR` / `UPSTREAM_ERROR` | WB API error — `UPSTREAM_ERROR` is raised specifically after 5xx (500/502/503/504) retries exhaust, so agents can distinguish WB infra stress from a true rate-limit event |
| 7 | `CONFIG_ERROR` | config/profile error |

5xx retries use a longer backoff schedule (5 s → 15 s → 45 s + jitter) than 429 retries, because WB gateway failures rarely clear in a couple of seconds and aggressive retry just amplifies the storm.

## Response Cache

Idempotent past-day responses from `stats product-spend`, `stats daily-report`, and `analytics sales-funnel products/history/grouped` are cached on disk at `~/.wb-cli/response_cache.db` (SQLite WAL). Same-day or future-dated queries bypass the cache entirely — so live data is never served stale.

- Cache is keyed by endpoint + token fingerprint + params (tokens themselves are never stored, only a SHA-256 prefix).
- Cross-process safe: a second `wb` invocation running the same past-day query gets a hit without touching WB.
- Retention: 90 days; old rows are pruned on access.

## Authentication

### Credential Resolution Priority

All credentials follow the same chain (highest to lowest):

```
CLI flags > Environment variables > .env file > ~/.wb-cli/profiles.json
```

### Auth Methods

1. **API Key** — raw JWT in `Authorization` header (no Bearer). Created via seller portal UI.
   - `wb auth login --token <JWT> --category promotion`
   - `wb auth login --token <JWT> --category all` — saves token under all 11 categories at once
   - `wb auth categories` — list all valid `--category` values (table or `--json`)
2. **Portal Session** — `cookie + authorizev3` headers together (both required) to seller portal.
   - `wb auth login-portal --authorizev3 <key> --cookie <str>`
   - `wb auth generate-token` — generate tokens via portal JRPC
   - `wb portal products` — list product cards from portal
   - Auth: cookie + authorizev3 (wb-seller-lk session token is NOT needed)

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `WB_API_TOKEN` | API token — used as fallback for **both** promotion and analytics commands |
| `WB_ANALYTICS_TOKEN` | Dedicated analytics token (takes priority over `WB_API_TOKEN` for analytics) |
| `WB_AUTHORIZEV3` | Portal authorizev3 key (fallback for portal session) |
| `WB_PORTAL_COOKIE` | Portal browser cookie (fallback for portal session) |
| `WB_USER_ID` | Seller user ID |
| `WB_TOKEN_EXPIRATION` | Token expiration timestamp |
| `WB_RATE_LIMITER` | Set to `memory` to force the in-process limiter and skip the shared SQLite coordinator (diagnostic only) |

> A single `WB_API_TOKEN` with full-scope permissions is sufficient to run all CLI commands
> (promotion + analytics). No profile registration needed when env vars are set.

## API Documentation

- **Authoritative source**: `dev-wb-adv.md` (extracted from `https://dev.wildberries.ru/en`)
- **Never** use endpoint paths from memory or older code — always verify against `dev-wb-adv.md`
- WB deprecates endpoints without notice; if any call returns 404, check the docs for the new path
- All endpoint constants live in `src/wb/core/constants.py` — no hardcoded paths elsewhere

## Rate Limits

- **Authoritative reference**: `RATE_LIMITS.md` — maps every CLI command → endpoint → limit → source
- **Machine-enforced**: `src/wb/core/rate_limits.py` — endpoint→(calls, period) map consumed by `_factory.py`
- **Implementation**: `src/wb/core/rate_limiter.py` — `SharedRateLimiter` (SQLite WAL at `~/.wb-cli/rate_limits.db`) by default, `RateLimiter` (in-process) as the fallback. The shared limiter serialises parallel `wb` processes so WB sees a combined call rate that respects the per-token budget. Set `WB_RATE_LIMITER=memory` to force the in-process limiter.
- The CLI throttles **preemptively** — agents do not need to add sleeps between calls
- Most critical: `EP_CAMPAIGN_FULLSTATS` → 1 call/20 s (burst=1), analytics funnel/history → 3 calls/min

### Known WB API Quirks

| API | Field/Behavior | Wrong assumption | Correct behavior |
|-----|----------------|-----------------|-----------------|
| Analytics v3 `sales-funnel/*` | `selectedPeriod` start key | `begin` | `start` |
| Analytics v3 `sales-funnel/products/history` | Date range limit | Any 30-day window | Max ~7-day lookback; farther dates → 400 |
| Analytics v3 `sales-funnel/products/history` | Rate limit | Same as other endpoints | 3/min, 20s interval — CLI enforces preemptively |
| Analytics v3 `sales-funnel/products/history` | Unknown NM IDs | Returns empty list | Returns 400 — only use real seller NM IDs |
| Promotion `/adv/v3/fullstats` | Campaigns with no data | Returns empty list | Returns HTTP 400 — don't call for never-started campaigns |
| Promotion `/adv/v3/fullstats` | Rate limit | Relaxed | 3/min, burst=1 → CLI enforces 1 call/20 s |
| Normquery `/adv/v0/normquery/list` | `items` field | Always a list | Can be `null` — use `(raw.get('items') or [])` |
| Analytics v3 `sales-funnel/products/history` | `dt` date field | `dt` key | Returns date in `date` key — `FunnelHistoryDay.from_api` reads `date` with `dt` fallback (F-18) |
| Promotion `/api/advert/v0/bids/recommendations` | Query params + scope | Single `id`, returns a list, any payment type | Requires **both** `nmId` AND `advertId`; returns one object per call (per item). CPM campaigns only — non-CPM yields HTTP 400. CLI loops per NM (F-19) |
| Promotion `/api/advert/v1/bids/min` | Method/shape | GET like recommendations | **POST** with JSON body `{advert_id, nm_ids[≤100], payment_type, placement_types}`; returns `{bids[].{nm_id, bids[].{type,value}}}` (F-19) |
| Promotion `/api/advert/v2/adverts` | Per-item current bids | Need separate bid endpoint | Live per-NM bids already in `adverts[].nm_settings[].bids_kopecks.{search,recommendations}` — `wb bid get-items` reads these directly with zero extra API calls (F-19) |
| Analytics `search-report` | Any API token | Works with standard token | Requires `Analytics/Advanced` scope — returns HTTP 403 |
| Promotion `/adv/v1/budget/deposit` | `sum` field unit | Kopecks | Rubles — minimum 1000, must be multiple of 50 |

## CLI Output Rendering Pattern

`OutputRenderer.display()` is **JSON-only**. For table mode it passes `data` straight to
`render_table()` which calls `table.add_row(*row)` — this only works when `data` is a
**list of lists** (strings). Passing a list of dicts produces the dict *keys* as cell values.

**Rule:** Every command must branch on `renderer.is_json`:

```python
if renderer.is_json:
    typer.echo(json.dumps([asdict(s) for s in results], indent=2, ensure_ascii=False))
    return

from wb.core.output import render_table
rows = [[str(s.field_a), str(s.field_b), ...] for s in results]
render_table(['Col A', 'Col B', ...], rows, title='My Table')
```

The `--fields` filtering from `renderer.display()` only works in JSON mode.

## Null-Safety Pattern for WB API Responses

```python
# Wrong — crashes on null
for item in raw.get('items', []):

# Correct — handles null and missing key
for item in (raw.get('items') or []):
```

## Key Design Decisions

- Promotion = execution core; Analytics = discovery extension (separate tokens)
- All mutations support `--dry-run`; never auto-apply without explicit confirmation
- `--json` flag on every command for agent/script compatibility
- Multi-profile from day one — no single-account shortcuts
- Optimizer is recommendation-first; mutations only with `--apply`

## Commit Style

- Never add `Co-Authored-By` trailers to commit messages.
- Release commits: `git commit -am 'release: vX.Y.Z — <theme>'`
