# Phase I-12 — SQLite-backed cross-process rate limiter (v0.25.0)

**Date:** 2026-04-24
**Tests:** 1085/1086 (1 pre-existing env-isolation failure in `test_auth_list_empty`, unrelated)

## What Was Built

- **`SharedRateLimiter`.** New class in `src/wb/core/rate_limiter.py` that coordinates preemptive throttling across processes via a single SQLite file at `~/.wb-cli/rate_limits.db` (WAL mode). Each `acquire()` opens a `BEGIN IMMEDIATE` transaction, prunes expired rows, counts in-window rows for `(token_fingerprint, endpoint)`, and either inserts a new row (slot available) or releases the lock and sleeps until the oldest row ages out. The sleep happens **outside** the transaction so other processes are never starved on an idle limiter.
- **Token fingerprinting.** `compute_token_fingerprint()` emits the first 16 hex chars of a SHA-256 digest — raw tokens never touch the DB file, only the prefix.
- **Transparent fallback.** On any `sqlite3.Error` at init or during `acquire`, the instance self-downgrades to the existing in-memory `RateLimiter` and the process logs exactly one warning (`_FALLBACK_WARNED` module flag). `WB_RATE_LIMITER=memory` forces the in-memory path before the DB is ever touched.
- **Factory wiring.** `_build_limiters(token)` in `src/wb/services/_factory.py` now picks `SharedRateLimiter` by default, hands each one the token fingerprint + endpoint + shared `db_path`, and short-circuits to `RateLimiter` only when the opt-out env var is set.
- **Docs.** `RATE_LIMITS.md` "For AI agents" callout rewritten (per-process → per-token across processes); `wb assess`/`wb pulse` caveat updated; Implementation Details section now describes both classes. `CLAUDE.md` adds `WB_RATE_LIMITER` to the env-vars table and a shared-SQLite line under Rate Limits.

## Files Changed

| File | Change |
|------|--------|
| `src/wb/core/rate_limiter.py` | Added `SharedRateLimiter`, `compute_token_fingerprint`, `_FALLBACK_WARNED` flag, module docstring updated |
| `src/wb/core/constants.py` | Added `RATE_LIMIT_DB_FILE`, `RATE_LIMITER_ENV_VAR`, `RATE_LIMITER_MEMORY_VALUE` |
| `src/wb/services/_factory.py` | `_build_limiters(token)` picks shared vs memory; `http_client` passes the token through |
| `RATE_LIMITS.md` | Rewrote "For AI agents" callout; updated `wb assess` / `wb pulse` note; new description of both limiter classes in Implementation Details |
| `CLAUDE.md` | `WB_RATE_LIMITER` env var row; Rate Limits section mentions shared SQLite with fallback semantics |
| `tests/unit/test_rate_limiter.py` | 19 new tests: fingerprint determinism, init validation, schema creation, stale pruning, over-limit sleep, per-endpoint & per-token isolation, two-thread cross-process serialisation, corrupt-DB fallback at init/acquire, single-warning-per-process, factory opt-in/opt-out |
| `docs/PROGRESS.md`, `docs/IMPROVEMENTS.md` | I-12 row flipped to DONE |

## Live Test Results

**Cross-process serialisation on `/adv/v3/fullstats` (1/20 s).** Two Python subprocesses called `SharedRateLimiter.acquire()` simultaneously against a fresh `rate_limits.db`:

```
PID=51464 started=…759.131 acquired=…759.144 waited=0.013s
PID=9820  started=…759.161 acquired=…779.146 waited=19.985s
```

Proc 1 got the slot in 13 ms; proc 2 waited **19.985 s** for the row to age out. Total wall time 20.2 s — matches `period=20` exactly. Without the shared limiter both would have fired at once and WB would have 429'd one of them.

**Corrupt-DB fallback mid-run.** Wrote 40 bytes of garbage to `~/.wb-cli/rate_limits.db`, then invoked `wb --json campaign list`:

```
[WARNING] wb.core.rate_limiter: Shared rate limiter DB unavailable (file is not a database);
    falling back to in-memory rate limiter. Parallel wb processes will no longer coordinate
    rate limits. Set WB_RATE_LIMITER=memory to silence.
```

Single warning as specified; CLI continued. Subsequent invocations re-raise the warning only on first fallback of their own process — the module-level `_FALLBACK_WARNED` flag holds per-process.

**`WB_RATE_LIMITER=memory` opt-out.** With the env var set, `rate_limits.db` was not created and `_build_limiters` returned in-memory `RateLimiter` instances for every endpoint.

**Note on WB's 429s during testing.** Parallel `wb stats product-spend --nms 145982347` runs against WB returned 429 at the `/api/advert/v2/adverts` leg before reaching `/adv/v3/fullstats` — WB's server-side limit was actively throttling this token from earlier sessions. That's an environmental condition, not a Phase 2 defect: the CLI-side coordination is directly demonstrated by the subprocess test above, which exercises the strict endpoint with zero WB dependency.

## Agent Usage

Parallel `wb` invocations sharing a token now coordinate through `~/.wb-cli/rate_limits.db` instead of each process independently consuming the full budget. This closes the gap that I-11's response cache couldn't cover — current-day queries, write paths, and anything else that cannot be cached.

Agents and scripts get the coordinated behaviour automatically; nothing to configure. The opt-outs exist for isolated test runs (`WB_RATE_LIMITER=memory`) and for transparent degradation when the DB is unusable (permissions, corruption, missing parent dir — each logged once per process).

The reactive 429/5xx retry in `wb.client.http` is unchanged and remains a second line of defence when WB's server-side tier limits still push back despite our preemptive spacing.
