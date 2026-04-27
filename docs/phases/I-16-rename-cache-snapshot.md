# I-16 — Rename `cache` ↔ `api-cache` (BREAKING)

**Status:** ✅ DONE · **Version:** 0.33.0 · **Date:** 2026-04-28 · **Tests:** 1295 passing
**Plan:** [fix-this-bug-but-velvet-muffin.md](../../../../Users/teocci/.claude/plans/fix-this-bug-but-velvet-muffin.md)

## Why

The CLI shipped with two cache-related command groups whose names mismatched common usage:

- `wb cache` actually managed explicit point-in-time **snapshots** (Phase 7 — campaign configs, daily stats, clusters, budget events). Driven by `wb cache snapshot --campaign N`. Time-series / audit purpose.
- `wb api-cache` was the transparent HTTP response cache (I-15). Populated automatically; cooldown-tied TTL. Performance / rate-limit purpose.

Common usage of "cache" matches the I-15 layer (transparent perf cache — Redis, browser, HTTP); "snapshot" matches the Phase 7 layer (LVM, ZFS, DB backups). The I-15 phase doc explicitly *wanted* `wb cache` but couldn't take it because Phase 7 had the namespace first.

I-16 swaps them.

## Final command surface

| Old | New |
|---|---|
| `wb cache list` | `wb snapshot list` |
| `wb cache snapshot --campaign X` | `wb snapshot capture --campaign X` |
| `wb cache snapshot-all` | `wb snapshot capture-all` |
| `wb cache clear` | `wb snapshot clear` |
| `wb cache history campaigns/stats/clusters …` | `wb snapshot history campaigns/stats/clusters …` |
| `wb api-cache status` | `wb cache status` |
| `wb api-cache clear` | `wb cache clear` |

`wb snapshot clear` and `wb cache clear` coexist — different groups, same verb. Mirrors `git branch -d` vs `git tag -d`.

The `snapshot snapshot` noun-noun stutter is gone: the capture verb is `capture` / `capture-all`. The user explicitly chose this over `create` / `take`.

## Hard rename, no aliases

User-confirmed scope. Old commands fail loudly:

```
$ wb api-cache status
Error: No such command 'api-cache'. Did you mean 'cache'?

$ wb cache snapshot --campaign 1
Error: No such command 'snapshot'.
```

Typer's auto-suggestion catches the obvious typo. No deprecation warnings, no aliasing — clean break, breaking-change minor bump appropriate at 0.x.

## Changes

### Source

| Move | Rename inside |
|------|---------------|
| `git mv src/wb/cli/cache.py` → `src/wb/cli/snapshot.py` | `cache_app` → `snapshot_app`; `cache_list` / `cache_snapshot` / `cache_snapshot_all` / `cache_clear` → `snapshot_list` / `snapshot_capture` / `snapshot_capture_all` / `snapshot_clear`; verb `'snapshot'` → `'capture'`, `'snapshot-all'` → `'capture-all'`; help text rewritten; `__all__ = ['snapshot_app']`; user-prompt "Clear cached data" → "Clear snapshot data"; "Cache Summary" title → "Snapshot Summary". |
| `git mv src/wb/cli/api_cache.py` → `src/wb/cli/cache.py` | `api_cache_app` → `cache_app`; `api_cache_status` → `cache_status`; `api_cache_clear` → `cache_clear`; module docstring rewritten; help text rewritten; `__all__ = ['cache_app']`. |

[src/wb/cli/app.py](../../src/wb/cli/app.py) — imports + `add_typer` calls updated:
```python
from wb.cli.cache import cache_app
from wb.cli.snapshot import snapshot_app
…
app.add_typer(snapshot_app, name='snapshot', help='Local domain snapshots')
app.add_typer(cache_app,    name='cache',    help='HTTP response cache')
```

### Tests

| Move | Rename inside |
|------|---------------|
| `git mv tests/unit/test_cli_cache.py` → `tests/unit/test_cli_snapshot.py` | All `runner.invoke(app, ['cache', ...])` updated to `['snapshot', ...]` (and `'snapshot'` subcommand → `'capture'`, `'snapshot-all'` → `'capture-all'`); class names `TestCacheList` / `TestCacheSnapshot` / `TestCacheSnapshotAll` / `TestCacheClear` / `TestCacheHistory` → `TestSnapshotList` / `TestSnapshotCapture` / `TestSnapshotCaptureAll` / `TestSnapshotClear` / `TestSnapshotHistory`. |
| `git mv tests/unit/test_cli_api_cache_commands.py` → `tests/unit/test_cli_cache.py` | All `'api-cache'` → `'cache'` in argv lists; `TestApiCacheStatus` / `TestApiCacheClear` → `TestCacheStatus` / `TestCacheClear`. |

### Docs

| File | Change |
|------|--------|
| [AGENT.md](../../AGENT.md) | Replaced the stale `wb cache campaigns / wb cache stats` examples with two distinct sections — `wb snapshot` (domain snapshots, with `wb --json snapshot history ...` examples) and `wb cache` (HTTP cache diagnostics with `wb --json cache status` and `wb cache clear --endpoint ...`). |
| [RATE_LIMITS.md](../../RATE_LIMITS.md) | All `wb api-cache` → `wb cache` (3 occurrences). |
| [docs/web/rate-limits.md](../web/rate-limits.md) | Same. |
| [docs/PROGRESS.md](../PROGRESS.md) | I-15 row annotated: `wb api-cache` (renamed to `wb cache` in I-16). |
| [docs/IMPROVEMENTS.md](../IMPROVEMENTS.md) | Same. |
| [docs/phases/7-cache.md](7-cache.md) | Header note added: phase-7 `wb cache` group renamed to `wb snapshot` in v0.33.0; `snapshot` / `snapshot-all` verbs became `capture` / `capture-all`. |
| [docs/phases/I-15-request-cache.md](I-15-request-cache.md) | "Naming note" section augmented with the I-16 rename annotation (kept the original prose for historical accuracy). |
| [src/wb/storage/request_cache.py](../../src/wb/storage/request_cache.py) | Internal docstring on `read_all()` updated from `wb api-cache status` to `wb cache status`. |

CHANGELOG entries for v0.32.0 (I-15) and prior keep their original `wb api-cache` text — historical record.

### Untouched

- Storage layer: `cache.db` and `request_cache.db` paths, table schemas, services. The rename is CLI-facing only.
- Profile resolution: F-17's `resolve_profile_name(ctx)` carries through to all renamed handlers unchanged.
- The `--no-cache` global flag and `WB_REQUEST_CACHE=disabled` env var (still bypass the HTTP layer).

## Verification

Live-tested end-to-end:

```
$ wb snapshot list
      Snapshot Summary
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━┓
┃ Table             ┃ Rows ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━┩
│ campaigns         │ 0    │
│ campaign_stats    │ 0    │
│ cluster_snapshots │ 0    │
│ budget_events     │ 4    │
└───────────────────┴──────┘

$ wb cache status
Profile : 25169

Seller 407bbe2b-… (1 token)
                          Token def07bba57905265
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Endpoint               ┃ Rows ┃ Bytes   ┃ Soonest expires (s) ┃ State   ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ /api/advert/v2/adverts │ 1    │ 77.9 KB │ 0                   │ expired │
└────────────────────────┴──────┴─────────┴─────────────────────┴─────────┘

$ wb snapshot --help
 Local domain snapshots
 …
 Commands
   list         Show stored campaign snapshots …
   capture      Capture current WB API state for a campaign to local storage.
   capture-all  Capture config snapshots for all active campaigns.
   clear        Delete stored snapshots for this profile …
   history      Query stored snapshot history

$ wb api-cache status
Error: No such command 'api-cache'. Did you mean 'cache'?
$ wb cache snapshot --campaign 1
Error: No such command 'snapshot'.
```

Test suite: 1295 passed (no count change vs F-17 — pure rename), 1 pre-existing env-related test deselected as documented.

## Impact on agent skills

Grep across `.claude/skills/` confirmed no skill calls these commands by name. Internal agents use `wb-optimize`, `wb-pulse`, `wb-assess`, etc., which invoke domain commands (`campaign list`, `stats`, …) — none touch the cache or snapshot diagnostics.

The breaking change does not affect any shipped agent skill.
