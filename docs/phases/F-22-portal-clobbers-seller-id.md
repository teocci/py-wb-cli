# F-22 — `wb auth login-portal` clobbers JWT-derived `seller_id` + add `wb auth refresh`

- **Version:** 0.40.1
- **Status:** ✅ DONE
- **Date:** 2026-05-23
- **Scope:** `src/wb/auth/profiles.py`, `src/wb/cli/auth.py`, `tests/unit/test_profiles.py`, `tests/unit/test_cli_auth.py`, docs

## Live test

Reproduced the bug and validated the fix end-to-end against the user's actual `25169_personal` profile:

```
$ wb auth status
Seller ID: 10799201   ← bug
Portal user ID: 10799201

$ wb auth refresh
Profile     : 25169_personal
Seller ID   : 10799201 → 25169
Token expires: 1794946657 → 1794946657

$ wb auth status
Seller ID: 25169      ← restored from JWT oid
Portal user ID: 10799201
```

## Test results

- 8 new tests added (3 in `test_profiles.py`, 5 in `TestAuthRefresh` in `test_cli_auth.py`); 2 existing tests in `test_profiles.py` rewritten to reflect new behavior.
- Full suite: 1450/1451 passing — same 1 pre-existing failure (`test_auth_list_empty`, env leakage) that's been on the books since pre-F-21.

## Problem

When a profile has been authenticated with a JWT via `wb auth login` (which decodes `seller_id` from the JWT `oid` claim), and then `wb auth login-portal` is run against the same profile to add an unofficial portal session, the JWT-derived `seller_id` is **silently overwritten** with the portal `user_id` — a separate identifier in WB's system.

Live reproduction:

```
wb auth login --token <JWT> --profile 25169_personal --category all
wb auth status   →   Seller ID: 25169         (from JWT `oid`)

wb auth login-portal --profile 25169_personal --authorizev3 … --cookie …
wb auth status   →   Seller ID: 10799201      ← WRONG — overwritten with portal user_id
                     Portal user ID: 10799201
```

## Root cause

`src/wb/auth/profiles.py:307-308` in `save_portal_session()`:

```python
if user_id:
    profile.seller_id = user_id   # ← unconditional overwrite
```

Phase A-1 introduced this line under the (incorrect) assumption that the portal `user_id` IS the seller account identifier (see the `Profile.seller_id` docstring at lines 40-42). They are in fact distinct identifiers — JWT `oid` is the seller ID (e.g. `25169`), portal `user_id` is a different per-user value (e.g. `10799201`).

## Fix

### 1. Profile data model — `src/wb/auth/profiles.py`

- Add `portal_user_id: str | None = None` field to the `Profile` dataclass with a docstring noting it is distinct from `seller_id`.
- Fix the misleading `Profile.seller_id` docstring (only `auth login` populates it).
- Update `to_dict` / `from_dict` to persist + read the new field, with a legacy-migration fallback that back-fills `portal_user_id` from `portal_session['user_id']` for older on-disk profiles.

### 2. `save_portal_session()` — stop the clobber

- Replace the `profile.seller_id = user_id` line with `profile.portal_user_id = user_id`.
- Update its docstring to describe the new behavior.

### 3. `wb auth status` read sites — `src/wb/cli/auth.py`

- Lines 394 (JSON `portal_user_id`) and 415 (table `Portal user ID`) now read `profile.portal_user_id` (typed field) instead of `portal_session['user_id']` (dict lookup).

### 4. New command `wb auth refresh` — recovery for already-broken profiles

```
wb auth refresh [--profile NAME] [--json]
```

Re-decodes the stored JWT for the target profile (default: active) and restores `seller_id` + `token_expires_at` from the JWT claims. Reuses existing helpers:

- `extract_token_claims()` (`src/wb/auth/token_utils.py:42`)
- `ProfileStore.set_seller_id()` (`src/wb/auth/profiles.py:322`)
- `ProfileStore.set_token_expires_at()` (`src/wb/auth/profiles.py:333`)

If the profile has no JWT, exits `AUTH_FAILURE` with a hint to run `wb auth login`.

## Tests

### `tests/unit/test_profiles.py`

- **Replace** `test_save_portal_session_auto_populates_seller_id` → `test_save_portal_session_writes_portal_user_id_not_seller_id`
- **Replace** `test_save_portal_session_without_user_id_leaves_seller_id_none` → assert both `seller_id` AND `portal_user_id` stay `None`
- **New** `test_save_portal_session_does_not_clobber_existing_seller_id` — the F-22 regression: pre-set `seller_id='25169'`, call `save_portal_session(user_id='10799201')`, assert `seller_id == '25169'` and `portal_user_id == '10799201'`
- **New** `test_portal_user_id_persists_through_save_reload` — roundtrip via a fresh `ProfileStore`
- **New** `test_from_dict_back_fills_portal_user_id_from_portal_session` — legacy migration

### `tests/unit/test_cli_auth.py`

- **New** `TestAuthRefresh` class:
  - `test_refresh_restores_seller_id_from_jwt`
  - `test_refresh_no_token_exits_auth_failure`
  - `test_refresh_json_mode_outputs_structured_data`

## Non-changes

- `portal_session['user_id']` is still written by `set_portal_session()` — kept for on-disk shape continuity.
- `find_all_by_seller_id()` is unchanged (not called by production code).
- No new HTTP calls; `wb auth refresh` is purely local.

## Verification

1. `pytest tests/unit/test_profiles.py tests/unit/test_cli_auth.py -v` — new regression test must fail BEFORE fix, pass AFTER.
2. `pytest tests/unit/ -v` — full suite stays green.
3. Repair the user's broken `25169_personal`:
   ```
   wb auth status         # shows wrong Seller ID: 10799201
   wb auth refresh        # decodes JWT, restores seller_id
   wb auth status         # Seller ID: 25169, Portal user ID: 10799201
   ```
4. Fresh combined flow:
   ```
   wb auth login --token <JWT> --profile combo
   wb auth login-portal --profile combo --authorizev3 … --cookie …
   wb auth status --json | jq '.seller_id, .portal_user_id'
   # → "25169"   ← preserved
   # → "10799201"
   ```
