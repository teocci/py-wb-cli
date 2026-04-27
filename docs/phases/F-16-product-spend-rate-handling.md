# Fix F-16 — `generate_daily_wb_report.py` rate-limit handling

**Status:** ✅ DONE · **Version:** 0.32.1 · **Date:** 2026-04-27 · **Tests:** +18 (1293 total)
**Depends on:** I-15 (request cache eliminates the structural cause; F-16 closes the operator-experience gaps)
**Bug:** `bugs/2026-04-27-product-spend-endpoint-lock.md`
**Plan:** [happy-exploring-fox.md](../../../../Users/teocci/.claude/plans/happy-exploring-fox.md)

## Problem

`scripts/generate_daily_wb_report.py` failed on 2026-04-26:

```
wb stats product-spend --nms ... --from 2026-04-26 --to 2026-04-26
  → RATE_LIMITED: Endpoint /api/advert/v2/adverts locked for ~3518s
    (exceeds max_wait=60s)
```

Three issues compound:

1. **Architectural cause:** `wb stats product-spend` calls `list_campaigns()` → `/api/advert/v2/adverts` first. For Base tokens that endpoint is 1/h. The script's `SPEND_CHUNK_SIZE = 80` chunked invocations turned N NMs into N separate `wb` processes → N `list_campaigns` calls → first chunk succeeds, chunk #2 locks for ~hour. **Resolved by I-15** (the new `RequestCache` makes the second chunk's `list_campaigns` a cache hit).

2. **Diagnostic gap:** the script sets `HOME=<repo>/.home` for every `wb` subprocess and does not copy `rate_limits.db` into that isolated home. So the operator's main shell `wb rate status` reads a different DB and reports "No rate-limit state recorded yet" even when the script's DB has live locks.

3. **Doomed retry loop:** `run_wb_command` retries exit code 5 with hardcoded `[20, 60]` second waits. For a 3500 s WB cooldown, those retries waste ~80 s and then fail. The CLI already emits `error.retry_after` in the JSON envelope; the script ignores it.

## Live evidence

The script's `acquire_payloads` ran a top-of-function `read_rate_status` check, which returned empty (script's HOME-isolated DB had no entries). Orders fetch (analytics endpoint family) succeeded. First product-spend invocation hit `/api/advert/v2/adverts`, observed 429 + `X-Ratelimit-Reset≈3518`, persisted that to the isolated DB. Second product-spend invocation (next chunk) saw the lock at the budget layer and bailed with `exceeds max_wait=60s`. The retry loop slept 20 s, retried, bailed again. Slept 60 s, retried, bailed. Total ~80 s wasted, then `RateLimitedError` raised. No `product_spend_2026-04-26_raw.json` artifact existed for fallback. Process exited 1.

`wb rate status` from the operator's terminal reads `~/.wb-cli/rate_limits.db` — never touched by the isolated subprocess. So pre-run AND post-run output is "No rate-limit state recorded yet".

## Fix approach

I-15 lands first and removes the architectural fragility. F-16 then closes the operator-experience gaps:

1. **Drop HOME isolation.** Delete `WB_HOME_DIR`, `WB_CONFIG_DIR`, and `build_wb_env()`. Script subprocesses inherit the parent env, so they read/write `~/.wb-cli/rate_limits.db` — visible to all interactive `wb rate status` calls. Operator follow-up: `rm -rf <repo>/.home`.

2. **Drop redundant chunking in `fetch_spend_payload`.** The CLI already aggregates internally (`FULLSTATS_BATCH_SIZE` chunking inside `get_campaigns_stats`). The script's outer `SPEND_CHUNK_SIZE = 80` loop adds no value once I-15 caches `list_campaigns`. Replace with a single invocation; preserve the artifact shape under one synthetic chunk entry (or simplify by dropping `chunks` — only this script writes it).

3. **Header-driven fast-fail in `run_wb_command`.** Drop the `retry_waits` parameter. On exit code 5, parse the JSON envelope from stdout: `{"status":"error","error":{"code":"RATE_LIMITED","retry_after":3518.0,...}}`. Raise `RateLimitedError(retry_after=parsed)` immediately — no retry loop. If the envelope can't be parsed, raise with `retry_after=None`.

4. **Mid-run rate-status re-check.** In `acquire_payloads`, after orders fetch and before `fetch_spend_payload`, call `read_rate_status()` again. New helper `find_active_lock_for(status, endpoints)` filters to `{'/api/advert/v2/adverts', '/adv/v3/fullstats'}`. If locked: fall back to `spend_raw_path` if exists; else raise `SystemExit(EXIT_RATE_LIMITED)` with the cooldown surfaced.

5. **Surface `retry_after` in operator-facing log lines.** The existing spend-fetch except branch (`except RateLimitedError as exc: ...`) prints "Spend fetch rate-limited: ...". Augment with `exc.retry_after` when present so the operator sees "rate-limited (~3518s cooldown)".

## Changes

### Code

| File | Change |
|------|--------|
| `scripts/generate_daily_wb_report.py` | Delete `WB_HOME_DIR`/`WB_CONFIG_DIR`/`build_wb_env`; drop `env=` arg from subprocess.run sites; remove `retry_waits` parameter from `run_wb_command` and replace the retry loop with envelope-parse fast-fail; collapse `fetch_spend_payload` to a single CLI invocation; add `find_active_lock_for(status, endpoints)`; insert mid-run re-check in `acquire_payloads`; add `retry_after` attribute to `RateLimitedError`. |
| `bugs/2026-04-27-product-spend-endpoint-lock.md` | Status flip `open → fixed: <commit>`. |

### Tests

- `tests/unit/test_daily_report_script.py` *(new)* — fakes `subprocess.run` to return canned exit-5 JSON envelopes; asserts `run_wb_command` raises `RateLimitedError(retry_after=3518.0)` immediately (no retry sleep); asserts envelope-parse fallback when stdout isn't JSON; asserts `find_active_lock_for` correctly scopes to the supplied endpoint set.

### Docs

| File | Change |
|------|--------|
| `bugs/2026-04-27-product-spend-endpoint-lock.md` | Mark resolved; cross-reference I-15 + F-16. |
| `docs/FIXES.md` | Add F-16 row on completion (handled by `phase-complete`). |
| `docs/PROGRESS.md` | Status flip on completion (handled by `phase-complete`). |

## Verification

- Full suite green (`pytest tests/unit/ -v`).
- Reproduce pre-fix behavior with synthetic lock:
  ```sql
  -- Insert into ~/.wb-cli/rate_limits.db before running the script
  INSERT OR REPLACE INTO endpoint_budget
    (token_fp, endpoint, seller_id, bucket_limit, remaining, reset_at, last_seen)
  VALUES ('<your_token_fp>', '/api/advert/v2/adverts', NULL, 1, 0,
          strftime('%s','now')+1800, strftime('%s','now'));
  ```
  - **No persisted artifact:** `python scripts/generate_daily_wb_report.py --date <past>` exits 5 in <5 s, message names the endpoint and ~1800 s cooldown.
  - **Artifact present:** script logs the lock, falls back to the persisted `product_spend_<date>_raw.json`, exits 0.
- After a normal script run, `wb rate status` from the interactive shell shows the same observations the script wrote (no longer "No state recorded yet").
- Operator follow-up: `rm -rf <repo>/.home` (the directory is no longer used).

## Sequencing

F-16 lands after I-15. With I-15 in place, the architectural cause is gone; F-16 is purely operator-experience cleanup. If shipped without I-15, F-16's mid-run re-check still helps but the script remains structurally fragile against any Base-token endpoint cooldown.

## Live test results (2026-04-27)

Verified end-to-end against the operator's local Base-token profile, with `/adv/v3/fullstats` already exhausted (Base 1/h budget burned earlier in the session):

```
$ python scripts/generate_daily_wb_report.py --date 2026-04-26
wb stats product-spend rate-limited (~3040s cooldown); no persisted artifact for 2026-04-26 to fall back to.
$ echo $?
5
```

Single-line message with the WB-supplied cooldown surfaced, exit code 5, no Python traceback. Pre-fix the same scenario produced an ugly traceback after ~80 s of doomed `[20, 60]` retries.

Other behaviors verified along the way:

- **HOME unification:** `wb rate status` from the operator's interactive shell shows the same observations the script wrote (no longer "No state recorded yet"). `<repo>/.home` directory is no longer created or used.
- **Single-invocation spend:** the script fires one `wb stats product-spend --nms <all>` call instead of N chunks; the I-15 cache reuses `list_campaigns` across any subsequent invocation.
- **Test suite:** 1293 passed (1275 from v0.32.0 + 18 new F-16 unit tests in `tests/unit/test_daily_report_script.py`). One pre-existing env-related test deselected as documented.

## Cleanup

After upgrading, the operator can safely:

```bash
rm -rf <repo>/.home
```

The directory is no longer referenced by the script.
