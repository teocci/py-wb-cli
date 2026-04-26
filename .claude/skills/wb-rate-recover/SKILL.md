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
  - "endpoint locked"
---

# wb-rate-recover

Recovery guide for 429 / rate-limit failures. Invoke when CLI output contains `Rate limited (attempt N/4)`, `Endpoint <path> locked for ~Ns`, a table row shows `False | Rate limited by WB API`, or any `RATE_LIMITED` exit code (5).

## Token type matters (R-5+)

Before any recovery step, check `wb rate status` for the `token_type` field on each token group. The standard cooldown numbers in this guide are for **Personal/Service**; **Base** tokens get 30-min to 1-h refill windows on the same endpoints. On Base, "wait 60 seconds and retry" is rarely correct — wait what `reset_in_s` says, which can be 1800+ s.

**No active probe command.** R-5 removed `wb rate probe` — it was vestigial since R-1..R-4 made the runtime header-driven. Two replacements:
- **Connectivity / token validity** → `wb auth ping`
- **Live budget state** → `wb rate status` (no network call)

Any real `wb` call also refreshes the budget for the endpoint(s) it touches via `EndpointBudget.observe(...)`. There is no longer a way to "ask WB about state" without making a useful call — and that's the right design.

## Pre-flight — always start here (local, no network)

```bash
wb --json rate status
```

The output is read from local SQLite (no API call). Since R-3 the payload is grouped per `(seller, token, endpoint)`; since R-5 each token group includes `token_type`:

```json
{
  "now_epoch": 1745692800.0,
  "profile": "default",
  "sellers": [
    {
      "seller_id": "173f8646-dc21-58c0-892e-ba069dc0a9cb",
      "tokens": [
        {
          "token_fp": "aabbccdd11223344",
          "token_type": "base",
          "endpoints": [
            {"endpoint": "/adv/v3/fullstats", "remaining": 0, "bucket_limit": 1, "reset_in_s": 3499.0, "last_seen_ago_s": 12.0, "locked": true}
          ]
        }
      ]
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `endpoint.locked: true` | This specific endpoint is unreachable until `reset_in_s` passes. Other endpoints under the same token stay reachable. |
| `endpoint.reset_in_s: N` | Seconds remaining before the locked endpoint refills. Sleep at least `N + 5 s` if your retry needs that endpoint. |
| `sellers: []` | Empty `endpoint_budget` table — no rate-limit state observed yet. Clean slate. |
| All endpoints `locked: false` | No active cooldowns. If the previous command failed, the failure was transient or in-process. Just retry. |

**To pick the longest active cooldown** with `jq`:

```bash
wb --json rate status | jq '
  [.sellers[].tokens[].endpoints[]
   | select(.locked == true)
   | .reset_in_s]
  | max // 0
'
```

If this returns `0`, no endpoint is currently locked. Otherwise sleep that many seconds before retrying.

## When `rate status` shows nothing locked but the call still fails

If `rate status` is empty (no rows yet) or every endpoint shows `locked: false`, three things can be true:

1. **Fresh process / fresh DB** — no calls have been observed yet. Just retry the original command; the first response will populate the budget for that endpoint.
2. **The failure was in-process retry exhaustion** — three internal retries already happened; the budget now reflects the lock that was written on the third 429. `rate status` shows it; sleep `reset_in_s + 5s`.
3. **A parallel process or external client tripped the throttle without writing to our `endpoint_budget`** — only the next real call to that endpoint will surface the actual cooldown via WB's response headers. You can either retry the original command (which will block per-endpoint at the budget layer if WB responds with `remaining=0`) or run a cheap unrelated command.

For a connectivity / token-validity sanity check, use `wb auth ping` — it hits `/ping` (uniform 3/30s rate, no Base stratification) and confirms the token is alive without consuming an advert bucket.

## Reading warning messages (legacy log lines)

Before R-1..R-4 landed, retries generated log lines like:

```text
[WARNING] wb.client.http: Rate limited (attempt 1/4), retrying in 5.5s
[WARNING] wb.client.http: Rate limited (attempt 2/4), retrying in 15.4s
```

| Field | Meaning |
|---|---|
| `attempt N/4` | N-th try out of 4 total (1 initial + 3 retries) |
| `retrying in Xs` | 5/15/45 s patient schedule on seller-global 429 (F-9), 1/2/4 s on per-endpoint 429 |
| `Endpoint <path> locked for ~Ns (exceeds max_wait=60s)` | R-1/R-2 fail-fast path — the per-(token, endpoint) bucket has more cooldown than we'll wait inline; the budget row carries the deadline |
| Warnings appear but command succeeds | Transient spike within a per-endpoint window; no action needed |
| Three warnings then `RATE_LIMITED` exit | `wb --json rate status` will show the endpoint that locked; retry only after `reset_in_s` |

## Why stop → delete fails despite preemptive limiting

The CLI enforces per-endpoint sliding-window limiters (stop and delete each allow 5/s independently). However, the WB server aggregates write mutations at the campaign level, so rapid back-to-back stop+delete on the same campaign ID can still trigger a server-side 429 that the preemptive limiter cannot predict. Since R-1..R-4 the first 429 populates the per-(token, endpoint) `endpoint_budget` row, so subsequent commands targeting the same endpoint short-circuit cleanly — but the first incident still has to happen.

## Decision tree

```text
CLI exited RATE_LIMITED or warnings appeared?
├── Run: wb --json rate status
│   ├── any endpoint with locked == true
│   │   └── sleep max(reset_in_s) + 5s, then retry original command
│   └── all endpoints unlocked (or sellers == [])
│       ├── token_type == "base" → wait the documented Base interval for the
│       │   failed endpoint (RATE_LIMITS.md § Endpoints, Base column), then retry
│       └── token_type ∈ {personal, service, test} → just retry; the budget
│           layer will block if WB still says we're throttled
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

# Wait reset_in_s for the campaign-write endpoint, then retry
wb campaign delete <campaign_id> --yes
```

### Failed fullstats / daily-report

```bash
# Check — do not sleep blindly
wb --json rate status          # reads local endpoint_budget table

# Wait reset_in_s for /adv/v3/fullstats, then retry
wb --json stats daily-report --date <YYYY-MM-DD>
```

## Minimum wait times (fallback if rate status is unavailable)

Use these as a last resort when `wb rate status` is unavailable or no relevant row exists in `endpoint_budget` but the throttle is real. Numbers below are **Personal/Service**; for Base, see the Base column in `RATE_LIMITS.md`.

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
- Since R-5 there is no `wb rate probe` command. Use `wb auth ping` for connectivity checks; use `wb rate status` for budget visibility. Any real `wb` call refreshes the budget for the endpoint it touches.
- Per-endpoint scope: a 429 on `/adv/v3/fullstats` no longer locks `/adv/v1/balance` (R-1..R-4 redesign). Other endpoints stay reachable; only the throttled bucket waits.
- For pre-flight planning of multi-call sequences, see `wb-rate-guide`.
- Authoritative limits: `RATE_LIMITS.md`.
