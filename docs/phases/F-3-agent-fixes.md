# Fix F-3 — Agent-Critical Fixes (v0.9.0)

**Date:** 2026-04-03 | **Tests:** 635 passed (+31)

## Problems Found During Real Agent Session

- Campaign `get` dropped product NM IDs → agent bypassed CLI for raw HTTP
- Campaign stats lost per-NM breakdown → agent manually aggregated from raw API
- Errors were colored text, not JSON → agent couldn't parse failures
- Interactive prompts blocked automated calls

## What Was Fixed

- **Structured JSON errors**: `error_code` field on all exceptions, `to_dict()` method, JSON error output in `main()` when `--json` active
- **No interactive prompts**: Removed `prompt=True` from auth options; added `--yes` to `auth logout`; all confirms skip in JSON mode
- **`Campaign.nm_ids`**: Parses `nm_settings[]` from API response; displayed in `campaign get`
- **Per-NM stats**: New `NmStats` and `DayStats` dataclasses; `CampaignStats.from_api()` parses `days[].apps[].nms[]`; JSON output includes full breakdown
- **Exit code consistency**: All hardcoded `typer.Exit(code=N)` replaced with `ExitCode` enum
- **Shared CLI helpers**: New `_helpers.py` — `get_renderer`, `get_profile`, `confirm_or_abort`; eliminates copy-paste across 8 CLI modules
- Created `IMPROVEMENTS.md` (AI agent improvement roadmap)
