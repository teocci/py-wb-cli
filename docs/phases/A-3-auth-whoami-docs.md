# Phase A-3 — `wb auth whoami` + docs sweep

**Status:** ✅ DONE · **Version:** 0.39.0 · **Date:** 2026-05-23 · **Tests:** 1424/1425 (1 pre-existing env failure in `test_auth_list_empty`)
**Plan:** [auth-homogenization.md](../../../../Users/teocci/.claude/plans/auth-homogenization.md)

## What was built

Closes the auth-homogenization initiative with the diagnostic the post-A-2 model was missing — `wb auth whoami` — and rewrites the docs that taught the env-only mental model so future readers learn the bootstrap-then-login model from the start.

### `wb auth whoami`

A one-shot read on `~/.wb-cli/profiles.json` (no network calls). Surfaces:

- `profile` — the resolved profile name (or `null` when no profile is registered).
- `source` — `active-profile` (no flag) or `profile-flag` (when `--profile <name>` was passed). Closes the F-19/F-20 diagnostic loop: agents and operators who used to see env vars override the active profile can now read which credential is actually in flight at a glance.
- `seller_id`, `token_type`, `token_expires_at` — same fields `auth status` already exposes.
- `tokens` — `{category: sha256_fingerprint[:16]}` map matching what `wb rate status` reports. Cross-reference cooldowns by fingerprint without ever printing the raw token.
- `portal_session` — true / false.

`wb --json auth whoami` returns the structured payload; the table mode prints a compact six-line summary. No active profile returns exit 0 with `profile: null` (it's a diagnostic, not a failure — agents branch on the structure, not the exit code).

The plan's original `source: cli-flag` value was rejected during scope clarification — the CLI has no global `--token` flag, only `--profile`, so the truthful labels are `active-profile` / `profile-flag`.

### Docs sweep

- [CLAUDE.md](../../CLAUDE.md) "Credential Resolution Priority" section rewritten — the chain shrinks from `CLI flags > Env > .env > profiles.json` to `--profile flag > active profile > ConfigError` for runtime, with env / `.env` reframed as bootstrap-only material. Added a `wb auth whoami` example. The "Environment Variables" table dropped the dead `WB_USER_ID` / `WB_TOKEN_EXPIRATION` rows (A-2 removed both from `Settings`) and reframed every remaining row as bootstrap-only. The "Auth Methods — official vs unofficial" subsection from F-20 (0.37.1) is untouched per the plan's explicit instruction.
- [AGENT.md](../../AGENT.md) "Setup" section reframes the env-var snippets as one-time bootstrap input to `wb auth login` / `wb auth login-portal`, not a runtime fallback. Adds `wb auth whoami` to the quick-commands.
- Agent skills audit (`grep -ri 'WB_API_TOKEN\|\.env\|env var' .claude/skills/`) returned zero hits — every skill already assumes the CLI is configured. No edits needed.
- `scripts/*.py` audit — same: no env-var auth references. No edits needed.
- The README referenced in the original plan does not exist in the repo; left as-is per the CLAUDE.md rule "NEVER create documentation files unless explicitly requested".

## Files changed

| File | Change |
|------|--------|
| `src/wb/cli/auth.py` | New `auth_whoami` command (JSON + table modes) and `_emit_whoami_no_profile` helper for the no-profile branch. |
| `tests/unit/test_cli_auth.py` | New `TestAuthWhoami` class — 6 tests: no-profile (table + JSON), JSON includes per-category fingerprints, `--profile X` flips `source` to `profile-flag`, F-19/F-20 stale-env regression (whoami reports profile fingerprint, NOT env's), table mode renders the `Source` line. |
| `CLAUDE.md` | "Credential Resolution Priority" + "Environment Variables" sections rewritten for the post-A-2 model. `wb auth whoami` example added. `WB_USER_ID` / `WB_TOKEN_EXPIRATION` table rows removed. |
| `AGENT.md` | "Setup" reframes env vars as bootstrap input; adds `wb auth whoami` to the quick-commands. |

## Verification

- `pytest tests/unit/test_cli_auth.py::TestAuthWhoami -v` → 6/6 passing.
- Full suite: `pytest tests/unit/ -v` → 1424/1425 (1 pre-existing `test_auth_list_empty` env leak documented in CLAUDE.md).
- `wb auth --help` lists `whoami` between `status` and `ping`.
- `wb auth whoami` with a registered profile + stale `WB_API_TOKEN` in env reports the **profile** fingerprint, not the env's — pinned by `test_stale_env_does_not_change_whoami`.

## Out of scope

- The README file referenced in the original plan does not exist in the repo. Creating one was rejected during scope clarification (CLAUDE.md rule).
- Per-token `last_used` timestamps. `Profile` carries a single `last_used` field at the profile level; per-category tracking would need a schema migration. Deferred.
