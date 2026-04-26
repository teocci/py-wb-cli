# Phase A-2 — Drop runtime env fallback (BREAKING)

**Status:** 🔲 PLANNED · **Depends on:** A-1
**Plan:** [auth-homogenization.md](../../../../Users/teocci/.claude/plans/auth-homogenization.md)

## Goal

Remove the runtime env-token fallback from `_get_promotion_token` / `_get_analytics_token` / `create_portal_client`. Profile becomes the only runtime credential source (after the CLI-flag override). Env vars become bootstrap material for `wb auth login` only.

**This is a breaking change** for anyone (scripts, CI, agent skills) currently relying on `WB_API_TOKEN` in env without a registered profile.

## Changes

| File | Change |
|------|--------|
| `src/wb/services/_factory.py` | Delete `if settings.api_token: return settings.api_token` branches in `_get_promotion_token` (line ~290), `_get_analytics_token` (line ~475), and the analogous portal credential lookup in `create_portal_client`. Resolution becomes `cli_flag → profile → ConfigError`. |
| `src/wb/cli/rate.py` | Simplify `_resolve_any_token` to active-profile-only — no env fallback. |
| `src/wb/core/config.py` | Remove the runtime `api_token`, `analytics_token`, `authorizev3`, `portal_cookie`, `user_id`, `token_expiration` fields from `Settings`. Keep `BootstrapEnv` (added in A-1) reading them. |
| Error path | Any command run without a profile and without a `--token` flag exits with `ConfigError` (exit code 7) and the bootstrap message: `Run 'wb auth login --profile <name>' to register one. If WB_API_TOKEN is in env, it will be picked up automatically.` |
| Tests | `_get_promotion_token` raises `ConfigError` when env has a token but no profile is registered. Existing tests asserting env-fallback at runtime are deleted or rewritten. |

## Verification

- `pytest tests/unit/ -v` — green.
- Fresh-install flow:
  - `rm -rf ~/.wb-cli`
  - `.env` contains `WB_API_TOKEN=...`
  - `wb stats orders --from <past-day> --to <past-day>` → fails with bootstrap message.
  - `wb auth login --profile default` → succeeds.
  - `wb stats orders --from <past-day> --to <past-day>` → succeeds.

## Risk

- **Breaking change for env-only setups.** CHANGELOG entry must be loud. Agent-facing skills must be swept (A-3). The bootstrap error message itself is the migration guide.
