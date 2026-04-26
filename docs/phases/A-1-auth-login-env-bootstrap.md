# Phase A-1 — `wb auth login --profile NAME` env bootstrap

**Status:** 🔲 PLANNED · **Depends on:** R-1..R-4 shipped (sequencing — independent at the code level)
**Plan:** [auth-homogenization.md](../../../../Users/teocci/.claude/plans/auth-homogenization.md)

## Goal

Make `wb auth login --profile NAME` (no `--token` flag) bootstrap a profile from environment variables / `.env`. Non-breaking: both old (env-fallback at runtime) and new (profile-only) credential paths still work after this phase. A-2 makes the runtime change.

## Changes

| File | Change |
|------|--------|
| `src/wb/cli/auth.py` | Make `--token` optional on `login`. When omitted, read from env/`.env` via the new `BootstrapEnv`. Defaults `--category` to `all` when bootstrapping. Errors with a clear message if neither `--token` nor env vars are present. Also extract JWT `sid` and store on `Profile.seller_id` for any token saved (env or `--token`). |
| `src/wb/core/config.py` | Add `BootstrapEnv` dataclass exposing `api_token`, `analytics_token`, `authorizev3`, `portal_cookie`, `seller_id` as `str \| None`. Keep `Settings.api_token` etc. unchanged (deprecation note added). |
| Tests | `wb auth login --profile X` with `WB_API_TOKEN` in env creates a profile correctly; without it, errors with the bootstrap message. `Profile.seller_id` is populated after login from a JWT. |

## Verification

- `pytest tests/unit/test_auth_*.py -v`.
- Manual: empty `~/.wb-cli`, `WB_API_TOKEN` in `.env`, `wb auth login --profile default` succeeds and `wb auth list` shows the profile with the correct `seller_id`.

## Risk

- None breaking — this phase only adds a code path. The runtime credential resolution chain still reads env first (per CLAUDE.md). A-2 is the breaking change.
