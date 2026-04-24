# Improvement I-14 — `wb rate probe` single-call cooldown probe (v0.27.0)

**Date:** 2026-04-24
**Tests:** 1140/1141 (1 pre-existing env-isolation failure in `test_auth_list_empty`, unrelated)

## Problem

`wb rate status` (I-13) is 100 % safe and 100 % local, but only accurate for cooldowns **the CLI has directly observed** — `SellerCooldownLock` rows are written only when our HTTP client sees a 429 (F-13). Two gaps remained:

- **External trippers** — a browser tab, another tool, or a machine without our SQLite file could trip the throttle without populating our lock. `rate status` would misreport `locked: false`.
- **Fresh-process discovery** — a brand-new container with an empty DB has no lock entry to read. Its first `wb` command becomes a "discover by trying" call that could be heavy (e.g. daily-report), inadvertently compounding the penalty during an active throttle.

## What Was Built

- **New `wb rate probe` subcommand** in `src/wb/cli/rate.py`. Makes exactly one controlled GET to `/adv/v1/balance` — the cheapest documented per-seller endpoint that carries the `x-ratelimit-*` headers (1 call/s budget, small response body).
- **Three-path behaviour** driven by the F-13 lock state + WB response:

  | Input state | HTTP call? | Outcome | Exit | Lock write? |
  |---|---|---|---|---|
  | Lock already active | **No** | `lock-active` | 5 | No |
  | 200 OK | Yes, one shot | `ok` + `calls_remaining: N` | 0 | No |
  | 429 | Yes, one shot | `429` + `cooldown_seconds: N` | 5 | **Yes** |
  | 5xx / other | Yes, one shot | `error` + body snippet | 6 | No |
  | Network error | Yes, one shot | `network-error` | 6 | No |
  | No token available | **No** | `no-token` | 7 | No |

- **Raw `httpx` (not `WbHttpClient`)** because the probe needs direct access to response headers — `x-ratelimit-remaining` (on 200) and `x-ratelimit-reset` (on 429) — which the wrapper intentionally hides. Bypassing the wrapper is deliberate: we check the cooldown lock ourselves before the call, and we write to it ourselves after a 429, so F-13's guarantees are preserved end-to-end. The 10 s hard timeout prevents any stuck probe from holding up the pipeline.
- **JSON + table output** mirroring `rate status`.

## Files Changed

| File | Change |
|------|--------|
| `src/wb/cli/rate.py` | Added `rate_probe` command, `_emit_probe_result` helper, `_PROBE_ENDPOINT` and `_PROBE_TIMEOUT_SECONDS` constants; updated typer app help text from "read-only" to "diagnostic and safe single-call probe" |
| `tests/unit/test_cli_rate.py` | 7 new tests under `TestRateProbe`: help, active-lock-no-network, 200 with remaining header, 200 without header, 429 records lock, 500 leaves lock untouched, no-token exit 7. Imports `httpx` + `respx` |
| `docs/IMPROVEMENTS.md`, `docs/PROGRESS.md` | I-14 row flipped to ✅ DONE |

## Live Test Results

### Happy-path probe (lock expired from earlier E2E)

```
$ wb --json --compact rate probe
{"profile":"25169","seller_fingerprint":"589f628451e31cb7","http_status":200,
 "outcome":"ok","locked":false,"cooldown_seconds":0.0,"calls_remaining":0}
```

Probe succeeded. The payload's `calls_remaining: 0` warning flagged that the seller budget was at zero — the next call would 429. This is the forward-looking signal agents can read to avoid self-tripping.

### Ignoring the warning (for demonstration)

Immediately re-ran the probe:

```
$ wb --json --compact rate probe
{"profile":"25169","seller_fingerprint":"589f628451e31cb7","http_status":429,
 "outcome":"429","locked":true,"cooldown_seconds":1799.0,"calls_remaining":0}
real  0m1.676s
```

WB returned 429 with `x-ratelimit-reset: 1799`. F-12's parser populated `retry_after`; I-14's 429 branch wrote **1799 s** to the `SellerCooldownLock`. Exit 5, `RATE_LIMITED`.

### Lock-active short-circuit verified

Third invocation, now with the fresh lock:

```
$ wb --json --compact rate probe
{"profile":"25169","outcome":"lock-active","locked":true,"cooldown_seconds":1779.5,
 "calls_remaining":null}
real  0m0.331s
```

**0.331 s total**, no HTTP call attempted. The `rate status` command agreed (`seller_cooldown_seconds: 1779.8`). Future `wb stats daily-report`, `wb campaign list`, and `wb rate probe` invocations will all short-circuit through the same lock until the deadline passes.

## Design note — why `calls_remaining: 0` is the key signal

The demo above showed exactly the pattern I-14 is meant to enable: **agents should treat `calls_remaining: 0` as "don't call until the next reset window"**, not as "just one more and it'll work." Before I-14 there was no way to get this signal without already being in trouble. Now an agent's pre-flight loop can be:

```
run wb rate probe --json
  if outcome == "lock-active" → sleep cooldown_seconds + 5s
  if outcome == "ok" and calls_remaining == 0 → sleep ~60s (next reset window)
  if outcome == "ok" and calls_remaining > N → proceed with the planned workload
```
