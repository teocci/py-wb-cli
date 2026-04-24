# Improvement I-13 — `wb rate-status` diagnostic command (v0.26.0)

**Status:** 🔲 PLANNED
**Scope:** `src/wb/cli/rate.py` (new), `src/wb/cli/app.py`, `tests/unit/test_cli_rate.py` (new)

## Problem

After F-13 persists seller cooldown state in SQLite, there's no way for an operator (or agent) to ask the CLI "am I locked, and if so how long until I can call again?" without actually attempting a network call. The `wb-rate-recover` skill has to pitch blindly.

## Solution

Add a `wb rate-status` subcommand that reads local state only (no network) and reports:

- **Seller cooldown:** seconds remaining before `SellerCooldownLock` expires (from F-13); `0` when clear.
- **Recent acquires per endpoint:** summary from `rate_limits.db` — rows per `(token_fingerprint, endpoint)` in the last window, useful for diagnosing which endpoint is tightest.
- **Active profile and seller fingerprint:** so multi-seller setups can tell which seller they're looking at.

`--json` mode emits a structured payload for agents; table mode for humans. Hooks into the existing `wb-rate-recover` skill so agents can invoke it instead of making a network probe.

## Steps

- [ ] New `src/wb/cli/rate.py` with a single `status` subcommand under a `rate` typer app.
- [ ] Register `rate_app` in `src/wb/cli/app.py` alongside other top-level subcommands.
- [ ] Read `SellerCooldownLock` + summarise `rate_limits.db` acquires. Zero external calls.
- [ ] Update [.claude/skills/wb-rate-recover/SKILL.md](../../.claude/skills/wb-rate-recover/SKILL.md) to recommend `wb rate-status --json` as the first step.
- [ ] Unit tests: command output shape (table + JSON); clean-state case; active-cooldown case; empty DB case.
- [ ] Live test: `wb rate-status` before a 429 shows `seller_cooldown_seconds=0`; `wb rate-status` immediately after a 429 shows the remaining seconds.
