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
---

# wb-rate-recover

Recovery guide for 429 / rate-limit failures. Invoke when CLI output contains `Rate limited (attempt N/4)` or a table row shows `False | Rate limited by WB API`.

## Reading warning messages

```
[WARNING] wb.client.http: Rate limited (attempt 1/4), retrying in 1.0s
[WARNING] wb.client.http: Rate limited (attempt 2/4), retrying in 2.2s
[WARNING] wb.client.http: Rate limited (attempt 3/4), retrying in 5.5s
```

| Field | Meaning |
|---|---|
| `attempt N/4` | N-th try out of 4 total (1 initial + 3 retries) |
| `retrying in Xs` | exponential backoff: ~1s → ~2.2s → ~5.5s (base × 2^attempt + jitter) |
| Warnings appear but command succeeds | Transient spike — no action needed |
| 3 warnings then `False \| Rate limited by WB API` | All 4 attempts exhausted — manual retry required |
| Exit code on exhaustion | 5 |

## Why stop → delete fails despite preemptive limiting

The CLI enforces per-endpoint sliding-window limiters (stop and delete each allow 5/s independently). However, the WB server aggregates write mutations at the campaign level — rapid back-to-back stop+delete on the same campaign ID triggers a server-side 429 that the preemptive limiter cannot predict. This is a WB server constraint, not a CLI bug.

## Decision tree

```
Warnings appeared in CLI output?
├── YES, but final result shows Success → transient spike, no action needed
└── YES, and result row shows False / "Rate limited by WB API"
    ├── campaign stop / delete / pause / start → wait 10s, retry once
    ├── wb stats campaign (fullstats)          → wait 20s, retry once
    ├── wb bid recommend                       → wait 15s, retry once
    └── wb analytics funnel / history          → wait 20s, retry once
        └── Still failing after retry?
            └── wait 60s (full window reset), then retry
```

## Recovery procedures

### Failed delete after stop (most common case)

```bash
# Verify campaign state first
wb campaigns list --json --compact

# Wait, then retry
sleep 10
wb campaign delete <campaign_id> --yes
```

If still failing (exit code 5):

```bash
sleep 60
wb campaign delete <campaign_id> --yes
```

### Failed fullstats

```bash
sleep 20
wb stats campaign --id <campaign_id> --from <date> --to <date> --json --compact
```

### Prevent recurrence — safe stop+delete pattern

```bash
# Single campaign
wb campaign stop <id> --yes
sleep 10
wb campaign delete <id> --yes

# Multiple campaigns — batch all stops first, then all deletes
wb campaign stop <id1> --yes
wb campaign stop <id2> --yes
sleep 15
wb campaign delete <id1> --yes
wb campaign delete <id2> --yes
```

## Minimum wait times before retry

| Operation | Min wait | Reason |
|---|---|---|
| campaign write (stop/delete/start/pause) | 10s | server-side campaign aggregate window |
| `wb stats campaign` | 20s | burst=1, 1/20s enforced |
| `wb bid recommend` | 15s | 5/min → 12s between calls |
| analytics (funnel/history) | 20s | 3/min |
| any — after repeated failure | 60s | full rate-limit window reset |

## Notes

- `sleep` commands here are intentional guards against server-side aggregation that the preemptive limiter cannot see.
- For pre-flight planning of multi-call sequences, see `wb-rate-guide`.
- Authoritative limits: `RATE_LIMITS.md`.
