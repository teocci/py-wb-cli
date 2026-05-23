# Phase I-20 — `wb auth list` surfaces portal identity + correct Type render

**Version:** 0.41.0 · **Date:** 2026-05-23 · **Tests:** 1453 passed (1 pre-existing env failure in `test_auth_list_empty`)

## What was built

Two related fixes to `wb auth list` output, both inside the same command at [src/wb/cli/auth.py:299-348](../../src/wb/cli/auth.py):

- **Portal identity is now visible.** Added a `Portal User` column to the table (next to `Seller ID`) and a `portal_user_id` field to the `--json` payload. Value is read from `Profile.portal_user_id`, the canonical accessor introduced in F-22 — legacy on-disk profiles back-fill from `portal_session['user_id']` transparently via `Profile.from_dict`. Portal-only profiles now show their portal identity directly; profiles with both JWT and portal session show both `seller_id` and `portal_user_id` side by side (they are distinct identifiers — e.g. seller `25169` paired with portal user `10799201`).
- **`Type` column no longer lies for portal-only profiles.** `token_type` is documented as the JWT environment (`base` / `test`), but it defaults to `'base'` even when the profile carries zero JWT tokens — so a profile created via `wb auth login-portal` alone displayed `Type: base, Categories: none`, which is self-contradictory. The table now renders `—` in the Type cell when `Profile.tokens` is empty. **Table-only fix**; JSON `token_type` stays as the stored string so agent consumers parsing `--json` see no schema change.

The fix follows the precedent of the nearby `categories or 'none'` fallback at [src/wb/cli/auth.py:342](../../src/wb/cli/auth.py): an explicit "not applicable" placeholder reads better than an empty cell.

## Files changed

| File | Change |
|------|--------|
| `src/wb/cli/auth.py` | `auth_list`: add `Portal User` column + `portal_user_id` JSON field; dash Type cell when profile has no JWT tokens |
| `tests/unit/test_cli_auth.py` | New `TestAuthListShowsPortalIdentity` class — 3 tests covering JSON-with-portal, JSON-without-portal, and table dash-Type for portal-only |
| `docs/phases/I-20-auth-list-portal-identity.md` | This file |

## Verification

- `pytest tests/unit/test_cli_auth.py -v` → 45 passed (3 new)
- `pytest tests/unit/ -q` → 1453 passed, 1 pre-existing failure (`test_auth_list_empty`, env-leak — same as v0.40.1)
- Manual sanity check against real `~/.wb-cli/profiles.json`:
  - Profile with both JWT and portal session (`25169_personal`): table shows `Type: personal`, `Seller ID: 25169`, `Portal User: 10799201`.
  - Profile with JWT only (`668554`): table shows `Type: base`, `Seller ID: 668554`, `Portal User:` (empty cell).
  - JSON payload carries the new `portal_user_id` key on every entry (string or `null`).

## Out of scope

- `wb auth whoami` portal output — still shows `Portal: configured|not configured`. Surfacing `portal_user_id` there too is a candidate follow-up but not required for the `auth list` use case.
- Expiry / staleness rendering on portal session — kept the list view simple; `wb auth whoami` remains the place for credential-health detail.
