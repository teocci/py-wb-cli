# Phase A-2 — Drop runtime env fallback (BREAKING)

**Status:** ✅ DONE · **Version:** 0.38.0 · **Date:** 2026-05-23 · **Tests:** 1418/1419 (1 pre-existing env failure in `test_auth_list_empty`)
**Plan:** [auth-homogenization.md](../../../../Users/teocci/.claude/plans/auth-homogenization.md)

## What was built

Runtime credential resolution is now **`CLI flag → active profile → ConfigError`**. Environment variables (`WB_API_TOKEN`, `WB_ANALYTICS_TOKEN`, `WB_AUTHORIZEV3`, `WB_PORTAL_COOKIE`) are no longer consulted by service factories — they are bootstrap-only material for `wb auth login` and `wb auth login-portal`.

This is the regression-prevention contract for F-19/F-20: a stale `.env` can no longer silently override a registered profile, which was the root cause of the per-shell rate-limit fingerprint drift documented in those fixes.

### New behavior

- `wb <runtime-cmd>` with no profile and no `--token` → `ConfigError` (exit 7) with message: *"no active profile and no --token flag. Run 'wb auth login --profile <name>' to register one. If WB_API_TOKEN is in env, it will be picked up automatically."*
- `wb <runtime-cmd>` with a registered profile + stale `WB_API_TOKEN` in env → profile token wins (env is ignored).
- `wb auth login` (no `--token`) reads `WB_API_TOKEN` (or `WB_ANALYTICS_TOKEN` for `--category analytics`) from env / `.env` and registers a profile. `--category` defaults to `'all'` in this bootstrap mode (single full-scope token is the common case); the explicit-`--token` path keeps the historical `'promotion'` default.
- `wb auth login-portal` (no `--authorizev3` / `--cookie`) falls back to `WB_AUTHORIZEV3` + `WB_PORTAL_COOKIE` from env / `.env`. Missing values exit 7.

### Three-line example

```bash
$ rm -rf ~/.wb-cli && echo "WB_API_TOKEN=<JWT>" > .env
$ wb stats orders --from 2026-05-22 --to 2026-05-22
ConfigError: no active profile and no --token flag. Run 'wb auth login --profile <name>' to register one.
$ wb auth login
# → auto-bootstraps profile '668554_base' [all 11 categories]
$ wb stats orders --from 2026-05-22 --to 2026-05-22   # now works
```

## Files changed

| File | Change |
|------|--------|
| `src/wb/auth/bootstrap_env.py` | **NEW** — `BootstrapEnv` pydantic-settings class exposing `api_token`, `analytics_token`, `authorizev3`, `portal_cookie` from env / `.env`. Used only by `wb auth login` / `login-portal`. |
| `src/wb/core/config.py` | Dropped runtime fields `api_token`, `analytics_token`, `authorizev3`, `portal_cookie`, `user_id`, `token_expiration` from `Settings`. Docstring rewritten — credentials no longer bound here. |
| `src/wb/services/_factory.py` | `_get_promotion_token` and `_get_analytics_token` now go `cli_flag → profile → ConfigError` (no env fallback). `create_portal_client` same. New `_bootstrap_required_error` helper emits the canonical bootstrap message. |
| `src/wb/cli/auth.py` | `auth_login` — `--token` made Typer-optional; when omitted, reads from `BootstrapEnv`. `--category` default flipped to `None`: resolves to `'all'` for env-bootstrap, `'promotion'` for explicit `--token`. `auth_login_portal` — `--authorizev3` / `--cookie` made optional with the same env fallback. New helper `_bootstrap_token_from_env`. |
| `tests/unit/test_factory.py` | **NEW** — 12 tests pinning the F-19/F-20 contract: no env fallback at runtime, CLI flag wins, profile beats stale env (promotion / analytics / portal). |
| `tests/unit/test_cli_auth.py` | +8 tests across `TestAuthLoginEnvBootstrap` (6) and `TestAuthLoginPortalEnvBootstrap` (2): env-bootstrap creates profile, default `--category` is `'all'` when bootstrapping vs `'promotion'` with explicit `--token`, analytics env preferred for `--category analytics`, missing-creds exits 7. `isolated_home` fixture extended to clear all four auth env vars and `chdir` into tmp. |

## Verification

- `pytest tests/unit/test_factory.py tests/unit/test_cli_auth.py -v` → 43/43 passing (12 factory + 31 auth).
- Full suite: `pytest tests/unit/ -v` → 1418/1419 passing (1 pre-existing env failure in `test_auth_list_empty` that reads the developer's real `~/.wb-cli` — unrelated to this phase, documented in CLAUDE.md).
- Behavioral spot-checks:
  - `wb auth login --help` shows the new optional-`--token` semantics and the env-bootstrap mention.
  - `wb auth login` with no `--token` and no env exits 7 with the bootstrap message.
  - `wb auth login` with `WB_API_TOKEN` in env materializes the profile under all 11 categories.

## Risk

- **Breaking for env-only setups.** Anyone running `wb` from CI / cron / a script with `WB_API_TOKEN` in env and no registered profile must add a one-time `wb auth login` step. The bootstrap-error message itself is the migration guide.
- **Skills audit deferred to A-3.** `wb-assess`, `wb-pulse`, `wb-optimize`, `wb-calibrate` and the agent-facing CLAUDE.md credential-chain section still describe the pre-A-2 model. Updating them is the explicit scope of A-3 alongside the new `wb auth whoami` command.

## Out of scope (deferred to A-3)

- `wb auth whoami` subcommand (active profile + token fingerprint + portal status + `Source` field).
- CLAUDE.md "Credential Resolution Priority" rewrite.
- Agent skills sweep (`wb-{assess,pulse,optimize,calibrate}` setup sections).
- CHANGELOG migration note long-form.
