---
name: wb-rate-recover
description: Diagnose and recover from WB API rate limit warnings (429 errors). Invoke when CLI output contains "Rate limited" warnings or a command returns False with "Rate limited by WB API".
triggers:
  - "rate limited warning"
  - "Rate limited by WB API"
  - "rate limit recovery"
  - "429 error"
  - "retrying in seconds"
  - "attempt 1/4"
  - "seller cooldown active"
---

# wb-rate-recover

Recovery guide for 429 / rate-limit failures. Invoke when CLI output contains `Rate limited (attempt N/4)`, `Seller cooldown lock active`, a table row shows `False | Rate limited by WB API`, or any `RATE_LIMITED` exit code (5).

## Pre-flight — always start here (local, no network)

```bash
wb --json rate status
```

The output is read from local SQLite (no API call). Key fields:

| Field | Meaning |
|---|---|
| `locked: true` | A known seller-wide cooldown is active. Wait, do not run any other `wb` command. |
| `seller_cooldown_seconds: N` | Seconds remaining on that lock. Sleep at least `N + 5 s`. |
| `locked: false`, `endpoint_activity_5min: []` | No known lock and no recent traffic — clean slate. |
| `locked: false` with recent activity | The CLI hasn't seen a 429, but the state is unknown to us. Run `rate probe` to verify (see below). |

**If `locked: true`**, the recovery is: `sleep $(wb --json rate status | jq '.seller_cooldown_seconds')` and retry. Nothing else will succeed while the lock is active.

## Verification probe (one controlled network call)

If `rate status` says clear but you're not sure (fresh process, another tool may have tripped the throttle, reconciliation scenario), run the probe:

```bash
wb --json rate probe
```

This makes exactly one call to `/adv/v1/balance` — the cheapest per-seller endpoint — and interprets WB's rate-limit headers:

| `outcome` | `locked` | `calls_remaining` | What to do |
|---|---|---|---|
| `ok` | false | positive number | Safe to proceed; `calls_remaining` is how many calls before the next reset window |
| `ok` | false | `0` | **Do not call again this window.** Sleep ~60 s for the next reset, do not probe twice |
| `lock-active` | true | `null` | Already known locked — `rate status` was authoritative; sleep cooldown |
| `429` | true | 0 | The probe itself just tripped; the new `cooldown_seconds` is written to the lock automatically; sleep that value |
| `no-token`, `error`, `network-error` | — | — | Configuration / transport problem; investigate before retrying |

**Do not loop `wb rate probe`.** Each probe consumes one token of the seller budget. Once you have a reading, act on it.

## Reading warning messages (legacy path)

Before F-12/F-13 landed, retries generated log lines like:

```text
[WARNING] wb.client.http: Rate limited (attempt 1/4), retrying in 5.5s
[WARNING] wb.client.http: Rate limited (attempt 2/4), retrying in 15.4s
```

| Field | Meaning |
|---|---|
| `attempt N/4` | N-th try out of 4 total (1 initial + 3 retries) |
| `retrying in Xs` | 5/15/45 s patient schedule on seller-global 429 (F-9), 1/2/4 s on per-endpoint 429 |
| `cooldown too large to retry (reset=Ns > 60s), bailing out` | F-12 fail-fast path — no retries; lock is being written by F-13 |
| `Seller cooldown lock active — Ns remaining; skipping HTTP call` | F-13 pre-flight short-circuit — no HTTP made |
| Warnings appear but command succeeds | Transient spike within a per-endpoint window; no action needed |
| Three warnings then `RATE_LIMITED` exit | `wb --json rate status` now carries the `retry_after` value; use it |

## Why stop → delete fails despite preemptive limiting

The CLI enforces per-endpoint sliding-window limiters (stop and delete each allow 5/s independently). However, the WB server aggregates write mutations at the campaign level, so rapid back-to-back stop+delete on the same campaign ID can still trigger a server-side 429 that the preemptive limiter cannot predict. With F-13 in place the first 429 now populates the seller cooldown lock, so subsequent commands short-circuit cleanly — but the first incident still has to happen.

## Decision tree

```text
CLI exited RATE_LIMITED or warnings appeared?
├── Run: wb --json rate status
│   ├── locked == true
│   │   └── sleep seller_cooldown_seconds + 5s, then retry original command
│   └── locked == false
│       ├── Same command raised RATE_LIMITED just now → run wb --json rate probe
│       │   ├── outcome == "429"      → sleep cooldown_seconds + 5s
│       │   ├── outcome == "ok", calls_remaining == 0 → sleep 60s (next window)
│       │   └── outcome == "ok", calls_remaining > 0  → retry original command
│       └── Command succeeded with warnings → no action needed (transient)
```

## Recovery procedures

### Failed follow-up report on a date that was already fetched once

Before retrying, check whether raw artifacts for that same date already exist in `reports/daily/`.

- If `orders_YYYY-MM-DD_raw.json` exists, reuse it instead of recalling `analytics sales-funnel products`.
- If `product_spend_YYYY-MM-DD_raw.json` exists, reuse it instead of recalling `stats product-spend`.
- If `daily_report_YYYY-MM-DD_raw.json` exists, prefer it as the source for reconciliation and follow-up analysis.

For repeated analyst prompts on the same day range, saved raw JSON is the safest recovery path because it avoids consuming another limited window.

### Failed delete after stop (most common case)

```bash
# Authoritative check
wb --json rate status

# If locked, wait exactly that long; if clear, verify with a probe
wb --json rate probe

# Then retry the delete
wb campaign delete <campaign_id> --yes
```

### Failed fullstats / daily-report

```bash
# Check — do not sleep blindly
wb --json rate status          # reads local lock
wb --json rate probe           # optional: confirm with WB

# Only then retry
wb --json stats daily-report --date <YYYY-MM-DD>
```

## Minimum wait times (fallback if rate status is unavailable)

Use these as a last resort when `wb rate status` / `wb rate probe` aren't available or the lock is empty but the throttle is real.

| Operation | Min wait | Reason |
|---|---|---|
| campaign write (stop/delete/start/pause) | 10s | server-side campaign aggregate window |
| `wb stats campaign` / `wb stats daily-report` | 20s | burst=1, 1/20s enforced |
| `wb bid recommend` | 15s | 5/min → 12s between calls |
| analytics (sales-funnel products/history) | 20s | 3/min |
| any, after repeated failure | 60s | full rate-limit window reset |
| seller-scope `Limited by global limiter` | up to 600s | check `wb rate status` for the real number |

## Notes

- `wb rate status` is authoritative whenever a 429 has already been observed by any `wb` process sharing `~/.wb-cli/rate_limits.db`. Cross-process coordination means the lock persists across parallel invocations.
- `wb rate probe` is the only "safe" way to actively ask WB about the current state. It makes one call; do not loop.
- `calls_remaining: 0` on a successful probe means "stop, one more call will 429". Treat it as a hard stop, not a "just one more" signal.
- For pre-flight planning of multi-call sequences, see `wb-rate-guide`.
- Authoritative limits: `RATE_LIMITS.md`.
