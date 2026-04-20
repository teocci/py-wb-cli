# WB CLI - Claude Code Instructions

## How to Resume Implementation

1. Read `PROGRESS.md` — it shows which phase is complete and what comes next.
2. Read `DESIGN.md` — for architecture decisions and command taxonomy.
3. Say **NEXT** to implement the next pending phase.

Each phase follows this pattern:
- Implement in `src/wb/` following the file layout in DESIGN.md
- Write tests in `tests/unit/`
- Run `pytest tests/unit/ -v` — all must pass
- Bump version in `src/wb/__init__.py` and `pyproject.toml`
- Update `PROGRESS.md` with what was built and test results

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

## Version Scheme

Phase naming: `N` = core implementation · `NA` = sub-phase of N · `F-N` = fix · `I-N` = improvement

| Version | Phase | Milestone |
|---------|-------|-----------|
| 0.1.0 | 0 | Foundation |
| 0.2.0 | 1 | Read-only visibility |
| 0.3.0 | 2 | Core write controls |
| 0.3.1 | F-1 | Auth fix — dual auth, portal session, env var fallback |
| 0.3.2 | F-2 | API fix — full endpoint migration to current WB API |
| 0.4.0 | 3 | Search-cluster control |
| 0.5.0 | 4 | Analytics bridge |
| 0.6.0 | 5 | Optimization workflows |
| 0.7.0 | 6 | Agent platform support (SDK) |
| 0.8.0 | 7 | Local SQLite cache |
| 0.9.0 | F-3 | Agent-critical fixes — JSON errors, per-NM stats, shared helpers |
| 0.10.0 | 8A | Warehouse inventory reports |
| 0.11.0 | 8B | Stock runway (days-until-stockout) |
| 0.12.0 | 8C | Report caching & multi-seller storage |
| 0.13.0 | 8D | Prices & Discounts command |
| 0.14.0 | I-1 | Batch operations — multi-ID, auto-chunking, --fields |
| 0.15.0 | I-2 | Per-product cost tracking — product-spend, booster stats |
| 0.16.0 | I-3 | Composite commands (stable release) |
| 0.17.0 | I-4 | Rate limiting & resilience |
| 0.18.0 | I-5 | Polish & agent ergonomics |
| 0.19.0 | I-6 | Full token category support |
| 0.20.0 | I-7 | Agent skills — wb assess/pulse native commands + 7 Claude Code skills |
| 0.20.2 | F-4 | UTF-8 pipe fix — stdout reconfigure + centralized console |
| 0.21.0 | I-8 | stats campaigns --status filter — running/paused/active |

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

| Code | Meaning |
|------|---------|
| 0 | success |
| 2 | validation error |
| 3 | authentication failure |
| 4 | authorization / missing scope |
| 5 | rate-limited |
| 6 | WB API error |
| 7 | config/profile error |

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

> A single `WB_API_TOKEN` with full-scope permissions is sufficient to run all CLI commands
> (promotion + analytics). No profile registration needed when env vars are set.

Full design: `wb_cli_authorization_plan.md`

## API Documentation

- **Authoritative source**: `dev-wb-adv.md` (extracted from `https://dev.wildberries.ru/en`)
- **Never** use endpoint paths from memory or older code — always verify against `dev-wb-adv.md`
- WB deprecates endpoints without notice; if any call returns 404, check the docs for the new path
- All endpoint constants live in `src/wb/core/constants.py` — no hardcoded paths elsewhere

## Rate Limits

- **Authoritative reference**: `RATE_LIMITS.md` — maps every CLI command → endpoint → limit → source
- **Machine-enforced**: `src/wb/core/rate_limits.py` — endpoint→(calls, period) map consumed by `_factory.py`
- **Implementation**: `src/wb/core/rate_limiter.py` — sliding-window `RateLimiter` injected into `WbHttpClient` via `path_limiters`
- **Source**: Limits are sourced from `docs/swagger/08-promotion.yaml`, `11-analytics.yaml`, `12-reports.yaml` (authoritative), and empirical observation (noted inline in `rate_limits.py`)
- The CLI throttles **preemptively** — agents do not need to add sleeps between calls
- Most critical: `EP_CAMPAIGN_FULLSTATS` → 1 call/20 s (burst=1), analytics funnel/history → 3 calls/min

### Known WB API quirks

| API | Field/Behavior | Wrong assumption | Correct behavior |
|-----|----------------|-----------------|-----------------|
| Analytics v3 `sales-funnel/*` | `selectedPeriod` start key | `begin` | `start` |
| Analytics v3 `sales-funnel/products/history` | Date range limit | Any 30-day window accepted | Max ~7-day lookback; farther dates → 400 "invalid start day: excess limit on days" |
| Analytics v3 `sales-funnel/products/history` | Rate limit | Same as other analytics endpoints | 3/min, 20 s interval — CLI enforces preemptively. Space calls or accept exit 5 in integration tests |
| Analytics v3 `sales-funnel/products/history` | Unknown NM IDs | Returns empty list | Returns 400 — only use real seller NM IDs in integration tests |
| Promotion `/adv/v3/fullstats` | Campaigns with no data | Returns empty list | Returns HTTP 400 — don't call for never-started campaigns |
| Promotion `/adv/v3/fullstats` | Rate limit | Relaxed | 3/min, burst=1 → CLI enforces 1 call/20 s. Space calls ≥ 20 s apart in integration tests |
| Normquery `/adv/v0/normquery/list` | `items` field | Always a list | Can be `null` when campaign has no clusters — use `(raw.get('items') or [])` |
| Analytics v3 `sales-funnel/products/history` | `dt` field | ISO date string | Returns empty string `""` — date is not reliably parsed from this endpoint |
| Promotion `/api/advert/v0/bids/recommendations` | Paused campaigns | Returns bid data | Returns HTTP 400 for campaigns not currently running |
| Analytics `search-report` | Any API token | Works with standard token | Requires `Analytics/Advanced` scope — returns HTTP 403 otherwise |
| Promotion `/adv/v1/budget/deposit` | `sum` field unit | Kopecks | Rubles — minimum 1000, must be a multiple of 50 |

## CLI Output Rendering Pattern

`OutputRenderer.display()` is **JSON-only**. For table mode it passes `data` straight to
`render_table()` which calls `table.add_row(*row)` — this only works when `data` is a
**list of lists** (strings). Passing a list of dicts produces the dict *keys* as cell
values, not the values.

**Rule:** Every command must branch on `renderer.is_json`:

```python
if renderer.is_json:
    typer.echo(json.dumps([asdict(s) for s in results], indent=2, ensure_ascii=False))
    return

from wb.core.output import render_table
rows = [[str(s.field_a), str(s.field_b), ...] for s in results]
render_table(['Col A', 'Col B', ...], rows, title='My Table')
```

Never pass `[asdict(s) for s in results]` directly to `renderer.display()` for table output.
The `--fields` filtering provided by `renderer.display()` only works in JSON mode. For table
field filtering, filter `headers`/`rows` manually or omit columns.

## Null-Safety Pattern for WB API Responses

WB API sometimes returns `null` where a list is expected (e.g. `normquery/list` returns
`{"items": null}` for campaigns with no clusters). Always guard list fields:

```python
# Wrong — crashes on null
for item in raw.get('items', []):

# Correct — handles null and missing key
for item in (raw.get('items') or []):
```

Apply this to any `raw.get(key, [])` call that processes API responses.

## Key Design Decisions

- Promotion = execution core; Analytics = discovery extension (separate tokens)
- All mutations support `--dry-run`; never auto-apply without explicit confirmation
- `--json` flag on every command for agent/script compatibility
- Multi-profile from day one — no single-account shortcuts
- Optimizer is recommendation-first; mutations only with `--apply`
- Full spec in `wb_cli_implementation_plan.md`

## Commit Style

- Never add `Co-Authored-By` trailers to commit messages.
