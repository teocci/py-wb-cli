# Phase A-3 — `wb auth whoami` + docs sweep

**Status:** 🔲 PLANNED · **Depends on:** A-2
**Plan:** [auth-homogenization.md](../../../../Users/teocci/.claude/plans/auth-homogenization.md)

> **Note (2026-05-23):** the official-API-vs-portal-scraping clarification
> in CLI help text, CLAUDE.md, and AGENT.md was pulled forward and shipped
> as [F-20](F-20-auth-help-official-vs-portal.md) in 0.37.1. The remaining
> docs sweep here is the bootstrap-then-login model (depends on A-2) and
> `wb auth whoami`. Re-read F-20's wording when rewriting CLAUDE.md
> Authentication section in this phase — F-20 already covers the auth-
> method dichotomy.

## Goal

Add the `wb auth whoami` diagnostic and rewrite the documentation that taught the env-only model to teach the profile-bootstrap model. Closes the auth-homogenization initiative.

## Changes

| File | Change |
|------|--------|
| `src/wb/cli/auth.py` | New `whoami` subcommand. Prints active profile, plaintext seller ID (from `Profile.seller_id` or extracted on-the-fly from a JWT), token fingerprints per category, portal status, **and the resolved credential source** ("active-profile" / "cli-flag"). The source field is the diagnostic that closes the F-19/F-20 confusion loop: agents/users who were used to env-overrides-profile can immediately see which token is in flight. JSON mode supported. |
| `tests/unit/test_auth_whoami.py` | Standard JSON / table coverage for `whoami` including the no-active-profile case and the source-field assertion. |
| `CLAUDE.md` | Rewrite the "Credential Resolution Priority" section. Today it documents `CLI flags > Env > .env > profiles.json`. Post-A-2 the chain shrinks to `CLI flags > active profile` for runtime, and `.env` / env vars become input to `wb auth login` only. Add `wb auth whoami` to the quick-commands. **Do NOT redo the official-API-vs-portal-scraping dichotomy text** — F-20 already shipped that wording in the "Auth Methods — official vs unofficial" section (0.37.1). Just layer the bootstrap-then-login model on top. |
| `docs/PROGRESS.md`, `docs/IMPROVEMENTS.md` | Flip A-1..A-3 to ✅ DONE; assign final versions. |
| `README.md` | Update first-time setup example to `wb auth login` (reading `.env` on first run) with a `.env`. Show what `wb auth whoami` returns. |
| `CHANGELOG.md` | Release entry summarising the homogenisation + the breaking change from A-2. Quote the F-19/F-20 motivation so the lesson is preserved in release history. |
| `.claude/skills/wb-*` | Sweep all agent skills for assumptions about env-only auth. Replace with the new bootstrap step where needed. Particularly audit `wb-assess`, `wb-pulse`, `wb-optimize`, `wb-calibrate` which run unattended and currently assume env vars work at runtime. |

## Verification

- `wb auth whoami` round-trips through `json.loads` and prints the right fields in both modes, including the new `source` field.
- **F-19/F-20-regression in agent voice:** `wb auth whoami` with a stale `.env` correctly shows the active profile's fingerprint (NOT the env's), and the `source` field reads `active-profile` — proving the env override is gone.
- README quickstart works end-to-end from a fresh `~/.wb-cli`.
- Every agent skill referenced in `.claude/skills/` runs against the new auth model.

## Already shipped during the A-1 → A-3 gap

Two slices that originally belonged here have already landed and reduce A-3's scope:

- **F-20 (0.37.1)** — official-API-vs-portal-scraping clarification in `wb auth login` / `wb auth login-portal` help, `CLAUDE.md` "Auth Methods" section, and `AGENT.md` setup. A-3's CLAUDE.md rewrite only needs to add bootstrap-then-login on top of F-20's framing.
- **F-19 (0.37.0)** — `wb bid recommend / minimum / get-items` real implementation. Surfaced the env-override trap that A-2 is the only durable fix for; the live-test failure during F-19 verification is the canonical motivation quoted in A-2's "Motivation — real-world trap" section.
