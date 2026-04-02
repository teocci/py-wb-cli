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

| Version | Milestone |
|---------|-----------|
| 0.1.0 | Phase 0 - Foundation |
| 0.2.0 | Phase 1 - Read-only visibility |
| 0.3.0 | Phase 2 - Core write controls |
| 0.3.1 | Auth - Dual auth (portal session + env var fallback) |
| 0.3.2 | API Fix - Full endpoint migration to current WB API |
| 0.4.0 | Phase 3 - Search-cluster control |
| 0.5.0 | Phase 4 - Analytics bridge |
| 0.6.0 | Phase 5 - Optimization workflows |

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
2. **Portal Session** — `cookie + authorizev3` headers together (both required) to seller portal.
   - `wb auth login-portal --authorizev3 <key> --cookie <str>`
   - `wb auth generate-token` — generate tokens via portal JRPC
   - `wb portal products` — list product cards from portal
   - Auth: cookie + authorizev3 (wb-seller-lk session token is NOT needed)

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `WB_API_TOKEN` | API token (fallback for profile token) |
| `WB_AUTHORIZEV3` | Portal authorizev3 key (fallback for portal session) |
| `WB_PORTAL_COOKIE` | Portal browser cookie (fallback for portal session) |
| `WB_USER_ID` | Seller user ID |
| `WB_TOKEN_EXPIRATION` | Token expiration timestamp |

Full design: `wb_cli_authorization_plan.md`

## API Documentation

- **Authoritative source**: `dev-wb-adv.md` (extracted from `https://dev.wildberries.ru/en`)
- **Never** use endpoint paths from memory or older code — always verify against `dev-wb-adv.md`
- WB deprecates endpoints without notice; if any call returns 404, check the docs for the new path
- All endpoint constants live in `src/wb/core/constants.py` — no hardcoded paths elsewhere

## Key Design Decisions

- Promotion = execution core; Analytics = discovery extension (separate tokens)
- All mutations support `--dry-run`; never auto-apply without explicit confirmation
- `--json` flag on every command for agent/script compatibility
- Multi-profile from day one — no single-account shortcuts
- Optimizer is recommendation-first; mutations only with `--apply`
- Full spec in `wb_cli_implementation_plan.md`

## Commit Style

- Never add `Co-Authored-By` trailers to commit messages.
