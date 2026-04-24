# Improvement I-13 — `wb rate-status` diagnostic command (v0.26.0)

**Date:** 2026-04-24
**Tests:** 1133/1134 (1 pre-existing env-isolation failure in `test_auth_list_empty`, unrelated)

## Problem

After F-13 persists seller cooldown state in `~/.wb-cli/rate_limits.db`, there was no way to query it without attempting a network call. Operators and agents recovering from a 429 had to rely on trial-and-error; the `wb-rate-recover` skill had no authoritative "am I locked right now?" answer to pitch off.

## What Was Built

- **`wb rate status` subcommand** in new file `src/wb/cli/rate.py`. Read-only; no network calls. Emits either:
  - A structured JSON payload (`--json`) with `profile`, `seller_fingerprint`, `token_fingerprint`, `seller_cooldown_seconds`, `locked`, and `endpoint_activity_5min`. Suitable for agents to parse before planning bursts.
  - A human table (default) showing profile, seller fingerprint, lock state, and a 5-minute endpoint activity roll-up.
- **Activity summary** queries `rate_limit_log` for rows in the last 300 seconds, groups by endpoint, orders newest-first. Uses only local SQLite state; skips cleanly when the DB doesn't exist yet.
- **No-token resilience** — runs even when neither `.env` nor a registered profile has a token. Shows empty fingerprints and the "clear" lock state without crashing.
- **Compact JSON support** via the global `--compact` flag, matching other JSON-emitting commands for token efficiency.

## Files Changed

| File | Change |
|------|--------|
| `src/wb/cli/rate.py` | New file: `rate_app` typer subapp with a single `status` command and two helpers (`_resolve_any_token`, `_recent_activity`) |
| `src/wb/cli/app.py` | Imports `rate_app`; registers as `wb rate` subcommand |
| `tests/unit/test_cli_rate.py` | New file, 8 tests: help, clean-state JSON, locked-state JSON (real `SellerCooldownLock`), endpoint activity grouping + newest-first ordering, old rows excluded from 5-min window, table-mode output contains key fields, `--compact` produces single-line JSON, no-token no-crash |
| `docs/IMPROVEMENTS.md`, `docs/PROGRESS.md` | I-13 row flipped to ✅ DONE |

## Live Test Results

Run the command three times against a fresh SQLite state:

### Clean state (no lock, no activity)

```
$ wb --json --compact rate status
{"profile":"25169","seller_fingerprint":"589f628451e31cb7","token_fingerprint":"def07bba57905265","seller_cooldown_seconds":0.0,"locked":false,"endpoint_activity_5min":[]}
```

### After injecting a 30-second lock via the API

```
$ wb --json --compact rate status
{"profile":"25169","seller_fingerprint":"589f628451e31cb7","token_fingerprint":"def07bba57905265","seller_cooldown_seconds":29.6,"locked":true,"endpoint_activity_5min":[]}
```

### Cleared lock, table mode

```
$ wb rate status
Profile            : 25169
Seller fingerprint : 589f628451e31cb7
Seller cooldown    : clear

No endpoint activity recorded in the last 5 minutes.
```

## Integration with `wb-rate-recover` skill

The skill's SOP now starts with `wb rate status --json` as the canonical "am I locked?" probe — no more burning retries to find out. When `locked: true`, the skill defers execution until `seller_cooldown_seconds` elapses.
