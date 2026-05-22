# Phase A-1 — `wb auth login` JWT-driven profile bootstrap

**Status:** ✅ DONE · **Version:** 0.36.0 · **Date:** 2026-05-22 · **Tests:** 1370/1371 (1 pre-existing env failure in `test_auth_list_empty`)
**Plan:** [warm-toasting-garden.md](../../../../Users/teocci/.claude/plans/warm-toasting-garden.md)

## What was built

`wb auth login --token <JWT>` is now self-configuring. The CLI decodes the
JWT payload (no signature check needed) and pulls three claims directly
from the token:

- `oid` → `Profile.seller_id` — the WB seller account identifier. Confirmed
  against the user's existing profiles: their manually-named profiles
  `668554` and `25169` match the `oid` value of the tokens they hold.
- `exp` → `Profile.token_expires_at` — unix timestamp so the CLI can warn
  about (or refuse) expired tokens without an API round-trip.
- `t` → auto-detects `token_type='test'` when true; otherwise `--token-type`
  wins, then JWT `t`, then existing-profile preservation on re-login, then
  the default `'base'`. This preserves the original "re-login keeps your
  token_type" behaviour (covered by
  `test_existing_token_type_kept_when_flag_omitted`).

Profile naming becomes optional. When `--profile` is omitted, the CLI
auto-names the profile `{seller_id}_{token_type}` (e.g. `668554_base`,
`25169_personal`). Manual `--profile` values are slug-validated against
`^[a-z0-9][a-z0-9_]*$` (lowercase letters/digits/underscores, no spaces or
special chars). Auto-name collisions error out and instruct the user to
pass `--profile <name>` — no silent suffixing.

Both `wb auth status` and `wb auth list` surface the new fields in both
text (table) and JSON modes.

Earlier-A-1 spec referenced JWT claim `sid` as the seller key. That was
incorrect: `sid` is a per-token UUID, not the seller ID. The phase MD now
documents this correction; F-10's use of `sid` as a rate-limit scope key
is flagged for a separate audit.

### Three-line example of the new UX

```bash
$ wb auth login --token <JWT> --category all
# → auto-creates profile '668554_base', populates seller_id + token_expires_at
$ wb auth status --json | jq '.seller_id, .token_expires_at'
"668554"
1790136818
```

## Files changed

| File | Change |
|------|--------|
| `src/wb/auth/token_utils.py` | **NEW** — `decode_jwt_payload`, `extract_token_claims` (payload-only, never raises) |
| `src/wb/auth/profiles.py` | New `Profile.token_expires_at: int \| None`; `save_portal_session` auto-sets `seller_id` from `user_id`; new methods `find_all_by_seller_id`, `set_seller_id`, `set_token_expires_at` |
| `src/wb/cli/auth.py` | `auth_login` decodes JWT, auto-names profile, slug-validates `--profile`; `auth_status` and `auth_list` surface `seller_id` + `token_expires_at` in both text and JSON modes |
| `src/wb/core/constants.py` | Added `PROFILE_SLUG_RE`, `PROFILE_NAME_TEMPLATE`; added to `__all__` |
| `tests/unit/test_token_utils.py` | **NEW** — 16 tests covering JWT decode edge cases (malformed, non-base64, invalid JSON, padding recovery) and claim extraction |
| `tests/unit/test_profiles.py` | +10 tests: `token_expires_at` field, portal auto-populate, `find_all_by_seller_id`, `set_seller_id`, `set_token_expires_at`, persistence roundtrip |
| `tests/unit/test_cli_auth.py` | New `TestAuthLoginAutoNaming` class (+15 tests, with 7 parametrized slug rejections): auto-naming, collision error, slug validation, test-token auto-type, undecodable-token fallback, JSON surfacing |

## Verification

- `pytest tests/unit/test_token_utils.py tests/unit/test_profiles.py tests/unit/test_cli_auth.py -v` → 114/114 passing.
- Full suite: `pytest tests/unit/ -v` → 1370/1371 passing (1 pre-existing
  env failure in `test_auth_list_empty` that reads the developer's real
  `~/.wb-cli` — unrelated to this phase, documented in CLAUDE.md).
- CLI smoke: `wb auth login --help` reflects the new docstring and
  `--profile` semantics; `wb --json auth status` includes the new
  `seller_id` and `token_expires_at` fields.

## Risk

- Non-breaking for existing profiles: legacy `name='default'` still loads;
  new fields default to `None` when absent in stored JSON.
- `--profile` slug validation is user-visible — passing a name with a
  space, dash, or uppercase letter now errors out with a clear message
  citing the regex. The auto-name format `{oid}_{type}` only uses
  characters that pass validation.
- `--profile` default flipped from `'default'` to `None`. Behaviour in
  practice is equivalent — when no seller_id can be derived (token isn't a
  JWT), the helper falls back to the active profile name (`'default'` on
  a fresh install).
- Existing profiles (created before A-1) keep `seller_id = None` and
  `token_expires_at = None` until the user re-runs `wb auth login` with
  the same token to backfill the JWT-derived fields.

## Out of scope (deferred)

- Scope bitmask (`s`) → category auto-detection (needs WB bit→category map).
- JWT UUID (`id`) → exact-token-dedup.
- Manager ID (`uid`) storage.
- `login-portal` symmetric auto-naming (follow-up).
- Env-bootstrap variant of original A-1 (`--token` omitted, read from
  `.env`) — defer to A-1B or A-2.
- F-10's use of `sid` as rate-limit scope key — separate audit.
- JWT signature verification (WB doesn't publish JWKS).
