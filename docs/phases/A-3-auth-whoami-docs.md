# Phase A-3 — `wb auth whoami` + docs sweep

**Status:** 🔲 PLANNED · **Depends on:** A-2
**Plan:** [auth-homogenization.md](../../../../Users/teocci/.claude/plans/auth-homogenization.md)

## Goal

Add the `wb auth whoami` diagnostic and rewrite the documentation that taught the env-only model to teach the profile-bootstrap model. Closes the auth-homogenization initiative.

## Changes

| File | Change |
|------|--------|
| `src/wb/cli/auth.py` | New `whoami` subcommand. Prints active profile, plaintext seller ID (from `Profile.seller_id` or extracted on-the-fly from a JWT), token fingerprints per category, portal status. JSON mode supported. |
| `tests/unit/test_auth_whoami.py` | Standard JSON / table coverage for `whoami` including the no-active-profile case. |
| `CLAUDE.md` | Rewrite the "Authentication" section. Replace "No profile registration needed when env vars are set" with the new bootstrap-then-login model. Add `wb auth whoami` to the quick-commands. |
| `docs/PROGRESS.md`, `docs/IMPROVEMENTS.md` | Flip A-1..A-3 to ✅ DONE; assign final versions. |
| `README.md` | Update first-time setup example to `wb auth login --profile default` with a `.env`. |
| `CHANGELOG.md` | Release entry summarising the homogenisation + the breaking change from A-2. |
| `.claude/skills/wb-*` | Sweep all agent skills for assumptions about env-only auth. Replace with the new bootstrap step where needed. |

## Verification

- `wb auth whoami` round-trips through `json.loads` and prints the right fields in both modes.
- README quickstart works end-to-end from a fresh `~/.wb-cli`.
- Every agent skill referenced in `.claude/skills/` runs against the new auth model.
