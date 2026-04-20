---
name: wb-rate-guide
description: Pre-flight rate limit reference for agents planning multi-call sequences. Lookup before writing any sequence of wb CLI calls.
triggers:
  - "will this hit rate limits"
  - "rate limit reference"
  - "how fast can I call"
  - "safe call sequence"
  - "plan api calls"
---

# wb-rate-guide

Pre-flight reference. Consult before writing any sequence of wb CLI calls. Source of truth: `RATE_LIMITS.md`.

## How the preemptive limiter works

The CLI acquires a rate-limit slot **before** each HTTP request (sliding window, per-endpoint, per-process). You do not need to add sleeps — unless you are chaining write operations on the same resource in rapid succession (see safe patterns below).

## Command → limit table

| Command | Limit | Safe rate | Key constraint |
|---|---|---|---|
| `wb campaign stop` | 5/s | 5/s | server aggregates write ops on same campaign |
| `wb campaign pause` | 5/s | 5/s | server aggregates write ops on same campaign |
| `wb campaign start` | 5/s | 5/s | — |
| `wb campaign delete` | 5/s | 5/s | server aggregates write ops on same campaign |
| `wb campaign create` | 5/min | 1/12 s | — |
| `wb stats campaign` | 3/min, burst=1 | **1/20 s** | slowest; fullstats bottleneck |
| `wb stats daily-report` | composite | **1/20 s** | bottleneck = fullstats leg |
| `wb budget get` | 4/s | 4/s | — |
| `wb budget topup` | 1/s | 1/s | — |
| `wb budget balance` | 1/s | 1/s | — |
| `wb bid set-items` | 5/s | 5/s | — |
| `wb bid recommend` | 5/min | 1/12 s | — |
| `wb analytics sales-funnel products` | 3/min | 1/20 s | `--all` triggers pagination → multiple calls |
| `wb analytics sales-funnel history` | 3/min, burst=3 | 1/20 s avg | batch ≤20 NM IDs |
| `wb cluster minus set` | 5/s | 5/s | — |

## Critical bottlenecks

| Command | Why it's slow | Mitigation |
|---|---|---|
| `wb stats campaign` | burst=1 → must space 20s apart | batch up to 50 campaign IDs per call |
| `wb stats daily-report` | calls fullstats + funnel; fullstats=1/20s | runs as one composite call; no extra sleep needed |
| `wb bid recommend` | 5/min → 12s between calls | 7 campaigns = ~84s in wb-pulse |
| `wb analytics sales-funnel products` | 3/min; `--all` paginates at 1000/page | each pagination page = one EP_FUNNEL_PRODUCTS call |
| `wb analytics sales-funnel history` | 3/min, burst=3 | batch NM IDs; max 20/call |
| `wb campaign create` | 5/min | one creation per 12s minimum |

## Composite command timing

| Command | Approx time | Bottleneck |
|---|---|---|
| `wb assess --json --compact` | ~20-25s | `EP_CAMPAIGN_FULLSTATS` (1/20s) |
| `wb assess --quick --json --compact` | <5s | fast endpoints only |
| `wb pulse --campaigns <ids>` | ~1s/campaign | `EP_RECOMMENDED_BID` (1/12s) |

## Safe multi-step patterns

### stop → delete (single campaign)

```bash
wb campaign stop <id> --yes
sleep 10
wb campaign delete <id> --yes
```

WB server aggregates write operations per campaign — even though stop and delete hit different endpoints, rapid back-to-back writes on the same campaign ID trigger a server-side 429.

### stop → delete (multiple campaigns)

```bash
wb campaign stop <id1> --yes
wb campaign stop <id2> --yes
sleep 15
wb campaign delete <id1> --yes
wb campaign delete <id2> --yes
```

Batch all stops before any deletes. Never interleave stop+delete pairs. Each endpoint is single-ID only (no batch API exists).

### create → fund → start

```bash
wb campaign create --name '[goal] Name' --nms <nm_id> --placements search --payment-type cpc --yes
wb budget topup --campaign <campaign_id> --sum <rub> --yes
wb campaign start <campaign_id> --yes
```

These hit different endpoints; no extra sleep needed.

### multi-campaign stats

```bash
wb stats campaign --id <id1,id2,...id50> --from <date> --to <date> --json --compact
```

Batch IDs into one call (max 50). Do not loop per-campaign — the 20s CLI throttle applies per call.
