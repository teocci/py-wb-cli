# Phase A-2 — Drop runtime env fallback (BREAKING)

**Status:** 🔲 PLANNED · **Depends on:** A-1
**Plan:** [auth-homogenization.md](../../../../Users/teocci/.claude/plans/auth-homogenization.md)

## Goal

Remove the runtime env-token fallback from `_get_promotion_token` / `_get_analytics_token` / `create_portal_client`. Profile becomes the only runtime credential source (after the CLI-flag override). Env vars become bootstrap material for `wb auth login` only — read once at login time via a new `BootstrapEnv` accessor, never consulted again on subsequent CLI calls.

**This is a breaking change** for anyone (scripts, CI, agent skills) currently relying on `WB_API_TOKEN` in env without a registered profile.

## Motivation — real-world trap exposed by F-19 / F-20

The phase was originally framed as a cleanup of the "no profile registered yet" convenience, but live-testing F-19 in 2026-05-23 revealed a sharper failure mode that A-2 is the only durable fix for:

> The active profile was `25169_personal` (personal token, fingerprint `e1bee47e8fc7184d`, fresh bucket).
> The project `.env` had a stale `WB_API_TOKEN=...` from an earlier base-token profile (fingerprint `def07bba57905265`).
> Per the documented chain `CLI > Env > .env > profile`, the stale `.env` won. Every CLI invocation from the project directory hit the base token's WB-imposed seller-wide cooldown (1326s+ at observed time) and blocked entirely, even though the *active profile* was perfectly healthy.

The root cause is structural: **as long as runtime falls back to env, a stale `.env` is invisible state that can silently override the active profile.** The user has no immediate way to tell which credential is actually in flight — `wb auth status` correctly shows the active profile (which is healthy), but the calls go through a different token entirely. A-2 removes this drift surface.

After A-2, the only way for `.env` to influence a CLI call is to first run `wb auth login` to materialize it as a named profile. Drift becomes impossible because the active profile *is* the only runtime credential.

## Changes

| File | Change |
|------|--------|
| `src/wb/services/_factory.py` | Delete `if settings.api_token: return settings.api_token` branches in `_get_promotion_token` (around line 266-268), **both** env-fallback branches in `_get_analytics_token` (around line 475-479 — note this function checks `analytics_token` **and** `api_token`), and the analogous portal credential lookup in `create_portal_client` (around line 327-332). Resolution becomes `cli_flag → profile → ConfigError`. |
| `src/wb/auth/bootstrap_env.py` | **NEW.** Lightweight `BootstrapEnv` reader used only by `wb auth login` to surface env-provided defaults (token, authorizev3, cookie) for one-shot profile creation. A-1 explicitly deferred this — it was NOT created in 0.36.0. |
| `src/wb/cli/auth.py` | `wb auth login` invokes `BootstrapEnv` when `--token` is omitted (today it errors). This preserves the env-bootstrap UX that A-2's CHANGELOG migration message will advertise. |
| `src/wb/core/config.py` | The six runtime fields (`api_token`, `analytics_token`, `authorizev3`, `portal_cookie`, `user_id`, `token_expiration`) stop being read by service factories. Either remove them from `Settings` entirely (cleanest) or repurpose `Settings` into `BootstrapEnv`'s backing store. Comments tagged "Auth env var fallbacks" need updating to "bootstrap-only — consulted by `wb auth login`, not at runtime". |
| Error path | Any command run without a profile and without a `--token` flag exits with `ConfigError` (exit code 7) and a migration-aware message: `No active profile. Run 'wb auth login' to register one. If your .env has WB_API_TOKEN, 'wb auth login' (with no --token) will read it.` |
| Tests | `_get_promotion_token` raises `ConfigError` when env has a token but no profile is registered. `_get_analytics_token` similarly drops both branches. Existing tests asserting env-fallback at runtime are deleted or rewritten. Add a regression test that mirrors the F-19/F-20 trap: registered active profile + stale `WB_API_TOKEN` in env → calls use the *profile* token (fingerprint match), not the env. |

### Not touched (drop from original A-2 spec)

- `src/wb/cli/rate.py` — no `_resolve_any_token` function exists; `wb rate status` reads `~/.wb-cli/rate_limits.db` directly without resolving a runtime token. No changes needed.

## Verification

- `pytest tests/unit/ -v` — green.
- **Regression test for the F-19/F-20 trap** (the primary motivation):
  - Register a clean profile via `wb auth login`.
  - Add a different (stale or otherwise) `WB_API_TOKEN=` to `.env`.
  - Run any CLI command that hits the WB API (e.g. `wb campaign list`).
  - Assert that the HTTP client used the *profile's* token, not the env one. Easiest way: assert the resulting `EndpointBudget` row carries the active profile's token fingerprint.
- **Fresh-install bootstrap flow:**
  - `rm -rf ~/.wb-cli`
  - `.env` contains `WB_API_TOKEN=...`
  - `wb stats orders --from <past-day> --to <past-day>` → fails with the new bootstrap message.
  - `wb auth login` (no `--token`) → reads `WB_API_TOKEN` via `BootstrapEnv` and registers a profile.
  - `wb stats orders --from <past-day> --to <past-day>` → succeeds.
- **Analytics + portal coverage** (not just `WB_API_TOKEN`):
  - Same fresh-install flow but with `WB_ANALYTICS_TOKEN` only → `wb analytics search-funnel ...` must fail with the bootstrap message; `wb auth login` must accept the analytics env var.
  - Same with `WB_AUTHORIZEV3` + `WB_PORTAL_COOKIE` → `wb portal products` fails until `wb auth login-portal` (no flags) materializes them.

## Migration guidance (for the CHANGELOG)

For users with an existing `.env`:

1. Verify what's in the env: `wb auth whoami` (added in A-3) will show which credentials are about to be picked up.
2. Materialize as a profile once: `wb auth login` reads `WB_API_TOKEN`, `WB_ANALYTICS_TOKEN`, etc. from `.env` and writes a profile.
3. From that point on the `.env` token can be deleted, replaced, or left in place — runtime behavior stops depending on it.

The breaking surface is narrow: anyone whose only credential source was env-at-runtime needs exactly one extra `wb auth login` step. No data loss.

## Risk

- **Breaking change for env-only setups.** CHANGELOG entry must be loud and quote the new bootstrap flow verbatim. Agent-facing skills must be swept (A-3). The bootstrap error message itself is the migration guide.
- **The F-19/F-20 trap is the regression we're guarding against.** Any future change that re-introduces a runtime env fallback would re-introduce the drift surface — call this out in the phase MD so the lesson sticks.
