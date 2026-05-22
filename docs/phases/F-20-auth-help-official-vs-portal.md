# F-20 — `wb auth login` vs `login-portal` help & docs clarify official-API vs portal-scraping

- **Version:** 0.37.1
- **Status:** ✅ DONE
- **Scope:** `src/wb/cli/auth.py`, `src/wb/cli/portal.py`, `CLAUDE.md`, `AGENT.md`

## Problem

`wb auth login` and `wb auth login-portal` are two completely different authentication paths, but the existing CLI help text and docs don't communicate the distinction:

- **`wb auth login`** — official WB API auth. Stores a JWT issued via the seller portal UI; used for the documented `/api/advert/...`, `/analytics/...`, `/statistics/...`, etc. endpoints.
- **`wb auth login-portal`** — *unofficial* seller-portal scraping. Stores browser session credentials (`authorizev3` + `cookie`) copied from DevTools. Reaches endpoints the public API does not expose (e.g. product cards via `tableListv6`, render-token generation via JRPC). No public documentation.

Today both subcommands' help text just says "store credentials" or "authenticate with seller portal" — agents and humans frequently confuse them or assume `login-portal` is a richer version of `login`. This blocks the wb-cli AI agents from picking the right auth path for the task at hand.

## Fix

Add the official-vs-unofficial framing to:

| Surface | Change |
|---|---|
| `auth_app` Typer help | One-line summary that names both methods and what each unlocks. |
| `auth_login` docstring | "Store an **official WB API token** (JWT). Used for documented endpoints (Promotion / Analytics / Statistics / Content / etc.)." |
| `auth_login_portal` docstring | "Store **unofficial seller-portal session** credentials (cookie + authorizev3). Scrapes the seller portal as a logged-in manager — used to read data the public API does not expose (product cards, render-token generation). No public documentation." |
| `portal_app` Typer help | "Unofficial seller-portal scraping. Requires `wb auth login-portal` first." |
| `CLAUDE.md` Auth Methods section | Expand both bullets with the official/unofficial framing and call out what data each unlocks. |
| `AGENT.md` auth section | Agent-voice framing: "use `login` for X data, use `login-portal` for Y data". |

## Non-changes

- No credential-resolution code is touched. A-2 (drop runtime env fallback) is the place for that.
- No new commands or behavior. This is help-text + markdown only.
- Existing tests stay green — there's no asserted help-text in the test suite.

## Verification

- `wb auth --help`, `wb auth login --help`, `wb auth login-portal --help`, `wb portal --help` — eyeball the new framing.
- `pytest tests/unit/ -v` — no regressions.
- `grep -n 'official\|unofficial\|portal' CLAUDE.md AGENT.md` shows the new wording.

## Relationship to A-2 / A-3

This is a pull-forward slice of A-3's "docs sweep". Cleanly self-contained — does not depend on A-2 and does not block it. A-3 will revisit the wording once A-2 ships and may add `wb auth whoami` as a third help target.
