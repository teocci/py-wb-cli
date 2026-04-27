# Fix F-17 — CLI hardcoded `'default'` profile fallback + `cache list` table render

**Status:** ✅ DONE · **Version:** 0.32.2 · **Date:** 2026-04-28 · **Tests:** +2 (1295 total)
**Plan:** [fix-this-bug-but-velvet-muffin.md](../../../../Users/teocci/.claude/plans/fix-this-bug-but-velvet-muffin.md)

## Problem

Running any of `wb cache list`, `wb budget history`, `wb cluster set-bids`, etc. from a directory without a `.env` file failed with:

```
Error: Profile 'default' does not exist
```

The user's registered profiles were `668554` and `25169` (active) — none named `default`. The CLI worked from the project directory only because `.env` loaded `WB_API_TOKEN` and short-circuited the profile lookup; from any other cwd, the fallback kicked in and broke.

Thirteen call sites across six CLI files used the pattern

```python
profile = get_profile(ctx) or 'default'
```

This treats `'default'` as a magic profile name instead of asking the profile store for the *active* profile. [`ProfileStore.get_profile(name=None)`](../../src/wb/auth/profiles.py) at lines 203-212 already returns the active profile when given `None`, and the service factory at [_factory.py:249-271](../../src/wb/services/_factory.py) already forwards `None` correctly. Only the CLI shim was wrong — it converted the `None` from `get_profile(ctx)` into a hardcoded literal string.

## Bonus bug — `cache list` table render

While diagnosing F-17, [src/wb/cli/cache.py:44](../../src/wb/cli/cache.py) was found to pass a dict to `renderer.display()` for table mode. `render_table` calls `add_row(*row)`, and iterating a dict yields its keys, so each table-name string got unpacked into single-character columns:

```
┃ Table ┃ Rows ┃                                 (16 more empty columns)
│ c     │ a    │ m │ p │ a │ i │ g │ n │ s │ … │
```

The function already built a correct `rows` variable on line 43 but discarded it on line 44.

## Fix

### `resolve_profile_name(ctx)` helper

New helper in [src/wb/cli/_helpers.py](../../src/wb/cli/_helpers.py) that returns the effective profile name — `--profile` flag if present, otherwise the active profile from `ProfileStore`. Mirrors the auth layer's own active-profile fallback so commands never invent the literal `'default'`:

```python
def resolve_profile_name(ctx: typer.Context) -> str:
    explicit = get_profile(ctx)
    if explicit:
        return explicit
    from wb.auth.profiles import ProfileStore
    from wb.services._factory import _Container
    return ProfileStore(_Container.settings().config_dir).active_profile_name
```

### Call site replacements

All 13 `or 'default'` patterns replaced with `resolve_profile_name(ctx)`:

| File | Lines | Notes |
|------|-------|-------|
| `src/wb/cli/cache.py` | 38, 76, 104, 125, 156, 187, 215 | All seven cache subcommands |
| `src/wb/cli/budget.py` | 83, 92, 139 | Two audit-log call sites + `budget history` |
| `src/wb/cli/bid.py` | 113 | `_log_bid_mutation` helper signature changed from `str | None` → `str`; both call sites updated |
| `src/wb/cli/campaign.py` | 255 | `_log_mutation` helper signature changed; 7 call sites updated |
| `src/wb/cli/cluster.py` | 38 | `_log_mutation` helper signature changed; 6 call sites updated |

The bootstrap default at `src/wb/core/constants.py:120` (`DEFAULT_PROFILE_NAME = 'default'`) and `ProfileStore`'s own initial-state / JSON-load fallbacks at lines 163 and 173 are intentional and untouched.

### Table render fix

[src/wb/cli/cache.py:42-47](../../src/wb/cli/cache.py) now branches on `renderer.is_json` so JSON mode keeps the dict shape and table mode passes the pre-built `rows` list:

```python
counts = svc.summary(profile)
if renderer.is_json:
    renderer.display(counts, fields=get_fields(ctx))
    return
rows = [[k, str(v)] for k, v in counts.items()]
renderer.display(rows, headers=['Table', 'Rows'], title='Cache Summary', fields=get_fields(ctx))
```

## Changes

### Code

| File | Change |
|------|--------|
| `src/wb/cli/_helpers.py` | New `resolve_profile_name()` helper; added to `__all__`. |
| `src/wb/cli/cache.py` | 7 fallback fixes; table-render fix at the summary path. |
| `src/wb/cli/budget.py` | 3 fallback fixes (topup audit, topup event recorder, history). |
| `src/wb/cli/bid.py` | 1 fallback fix; `_log_bid_mutation` signature tightened to `profile: str`. |
| `src/wb/cli/campaign.py` | 1 fallback fix; `_log_mutation` signature tightened. |
| `src/wb/cli/cluster.py` | 1 fallback fix; `_log_mutation` signature tightened. |

### Tests

`tests/unit/test_cli_cache.py` — 2 new regression tests:

- `test_list_summary_table_renders_full_table_names` — asserts the rendered output contains `'campaign_stats'`, `'cluster_snapshots'`, `'budget_events'` as full strings (not per-character cells).
- `test_list_summary_json` — asserts the dict shape is preserved end-to-end through `wb --json cache list`.

### Docs

| File | Change |
|------|--------|
| `docs/FIXES.md` | F-17 row added on completion (handled by `phase-complete`). |
| `docs/PROGRESS.md` | Status flip on completion (handled by `phase-complete`). |

## Verification

- Full unit suite green: 1295 passed (1293 prior + 2 new), 1 pre-existing env-related test (`test_auth_list_empty`) deselected as documented.
- Live-tested from a non-project cwd:
  ```
  $ cd /tmp && wb cache list
         Cache Summary
  ┏━━━━━━━━━━━━━━━━━━━┳━━━━━━┓
  ┃ Table             ┃ Rows ┃
  ┡━━━━━━━━━━━━━━━━━━━╇━━━━━━┩
  │ campaigns         │ 0    │
  │ campaign_stats    │ 0    │
  │ cluster_snapshots │ 0    │
  │ budget_events     │ 1    │
  └───────────────────┴──────┘
  ```
  No `Profile 'default' does not exist` error. Profile resolved to active `25169`. Two-column table; full table names in the first column.
- JSON mode preserved: `wb --json cache list` still emits `{"campaigns": 0, "campaign_stats": 0, "cluster_snapshots": 0, "budget_events": 1}`.

## Out of scope

Other dict / list-of-dicts → table-mode bugs in the same file at lines 52, 86, 161, 192, 220 — those need real example data to design correct columns and are deferred to a separate fix.
