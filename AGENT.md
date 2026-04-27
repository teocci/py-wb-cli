# WB CLI — AI Agent Reference

Quick reference for AI agents managing Wildberries advertising via the WB CLI.

---

## Setup

```bash
# Minimum: one full-scope token covers all commands
export WB_API_TOKEN="<your-jwt>"

# Optional: separate analytics token (higher priority for analytics commands)
export WB_ANALYTICS_TOKEN="<analytics-jwt>"

# Optional: portal session (required only for wb portal and wb auth generate-token)
export WB_AUTHORIZEV3="<key>"
export WB_PORTAL_COOKIE="<browser-cookie>"
```

> Full env var list and credential resolution priority: see [CLAUDE.md](CLAUDE.md) Authentication section.

No profile registration needed when env vars are set.

To store a token under all 11 API categories at once:
```bash
wb auth login --token "<jwt>" --category all
wb auth categories --json   # list all valid --category values
```

---

## Global Flags

| Flag | Effect |
|------|--------|
| `--json` | Machine-readable JSON output (always use in agent sessions) |
| `--compact` | Single-line JSON — fewer tokens, same data |
| `--fields a,b` | Return only listed keys (JSON mode only) |
| `--quiet` | Suppress all non-essential output |
| `--profile <name>` | Use a named credential profile |

**Recommended agent invocation:**
```bash
wb --json --compact <command> [args]
```

---

## Response Format

**Success (list):**
```json
[{"nm_id": 123456, "order_count": 42, ...}, ...]
```

**Success (single object):**
```json
{"campaign_id": 7890, "status": "running", ...}
```

**Error:**
```json
{"status": "error", "error": {"message": "...", "code": "RATE_LIMITED"}}
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 2 | Validation error |
| 3 | Authentication failure |
| 4 | Authorization / missing scope |
| 5 | Rate-limited |
| 6 | WB API error |
| 7 | Config / profile error |

---

## Command Reference

### `wb assess`

Morning account snapshot. Aggregates balance + campaign status + 7-day product spend. Saves bid baselines to `~/.wb-cli/pulse_baseline.json` for intraday drift detection.

```bash
wb --json --compact assess           # full (~20-25s due to fullstats rate limit)
wb --json --compact assess --quick   # no product spend, <5s
wb --json --compact assess --nm 100525085
```

**Returns:** `{data_as_of, balance_rub, running[], paused[], ready[], product_spend_7d[]}`

> Run once per morning. Full mode saves baselines required by `wb pulse`.

### `wb pulse`

Intraday health check using real-time endpoints only. Detects bid drift, budget depletion, campaign pauses.

```bash
wb --json --compact pulse --campaigns 29156792,34926371
```

**Returns:** `{timestamp, campaigns[], action_needed}` — each campaign has `budget_remaining_rub`, `bid_recommend_drift_pct`, `bid_floor_drift_pct`, `alerts[]`.

| Alert | Trigger | Action |
|-------|---------|--------|
| `competitor_surge` | bid recommendation up >15% since morning | Raise bids |
| `budget_low` | balance < 500 RUB or < 20% of morning balance | `wb budget topup` |
| `campaign_paused` | status changed to paused | Topup then `wb campaign start` |
| `bid_floor_rising` | minimum bid up >10% since morning | Verify bids above floor |

> Requires `wb assess` (full mode) to have run today.

### `wb campaign`

```bash
wb --json campaign list                         # all campaigns
wb --json campaign list --status running        # filter by status
wb --json campaign get --id 123456              # single campaign with nm_ids
wb campaign start --ids 1,2,3 --yes
wb campaign pause --ids 1,2,3 --yes
wb campaign stop  --ids 1,2,3 --yes
wb campaign delete --id 123456 --yes
```

### `wb bid`

```bash
wb --json bid get --nm 100525085
wb bid set --nm 100525085 --cpm 450
wb bid set --bids '[{"nm_id":100525085,"cpm":450},{"nm_id":227403075,"cpm":380}]'
wb --json bid min --nm 100525085
```

### `wb budget`

```bash
wb --json budget get
wb budget deposit --campaign-id 7890 --amount 5000 --yes   # amount in RUBLES
```

### `wb stats`

```bash
wb --json stats campaign --id 7890 --from 2026-04-01 --to 2026-04-07
wb --json stats campaigns --from 2026-04-01 --to 2026-04-07
wb --json stats campaigns --status running --from 2026-04-01 --to 2026-04-07
wb --json stats product-spend --nms 100525085,227403075 --from 2026-04-01 --to 2026-04-07
wb --json stats daily-report --date 2026-04-21
```

### `wb analytics sales-funnel`

```bash
wb --json analytics sales-funnel products \
  --from 2026-03-31 --to 2026-04-07 --limit 100

wb --json --compact analytics sales-funnel products \
  --from 2026-03-31 --to 2026-04-07 \
  --sort-by orders --top 10

# All products with at least 1 order, single call
wb --json analytics sales-funnel products \
  --from 2026-04-20 --to 2026-04-20 \
  --sort-by orders --min-orders 1 --all

# Per-day breakdown (max 7-day window, 1-20 NM IDs)
wb --json analytics sales-funnel history \
  --from 2026-04-01 --to 2026-04-07 \
  --nm-ids 100525085,227403075
```

**`--sort-by` aliases:** `orders`=`order_count` · `opens`=`open_count` · `cart`=`cart_count` · `revenue`=`order_sum` · `buyouts`=`buyout_count`

### `wb prices`

```bash
wb --json prices list
wb --json prices list --nm-ids 100525085,227403075
wb --json prices list --min-discount 10
```

### `wb product`

```bash
# Sales + ad spend + clusters + bids + prices in one call
wb --json product summary --nms 100525085,227403075
```

### `wb cluster`

```bash
wb --json cluster list --nm 100525085
wb --json cluster get-bids --campaign-id 7890
wb cluster set-bids --campaign-id 7890 --bids '[{"cluster_id":1,"cpm":300}]'
wb --json cluster stats --campaign-id 7890 --from 2026-04-01 --to 2026-04-07
```

### `wb optimize`

```bash
wb --json optimize recommend
wb optimize apply --yes
```

### `wb report`

```bash
wb --json report warehouse list
wb --json report warehouse stock-runway
wb report warehouse list --no-cache    # force fresh API call
```

### `wb portal`

```bash
wb --json portal products --limit 100
```

### `wb snapshot`

Local domain snapshots — campaign configs, daily stats, clusters, budget events. Captured explicitly with `wb snapshot capture`; queried via `wb snapshot history ...`.

```bash
wb --json snapshot history campaigns
wb --json snapshot history stats --campaign 12345 --from 2026-04-01
```

### `wb cache`

HTTP response cache diagnostics (transparent perf layer; populated automatically). Read `~/.wb-cli/request_cache.db` directly — no network calls.

```bash
wb --json cache status
wb cache clear --endpoint /api/advert/v2/adverts
```

---

## Common Agent Workflows

### Daily monitoring

```bash
# Morning — once after 9h
wb --json --compact assess

# Intraday — every 1-2h; parse running campaign IDs from assess output
wb --json --compact pulse --campaigns 29156792,34926371,35823936
```

### Top sellers last 7 days

```bash
TODAY=$(date +%F)
WEEK_AGO=$(date -d '7 days ago' +%F)
wb --json --compact analytics sales-funnel products \
  --from "$WEEK_AGO" --to "$TODAY" \
  --sort-by orders --top 20
```

### Per-product ad spend

```bash
NMS=$(wb --json campaign list --status running \
  | python -c "import sys,json; print(','.join(str(n) for c in json.load(sys.stdin) for n in c.get('nm_ids',[])))")
wb --json stats product-spend --nms "$NMS" --from 2026-04-01 --to 2026-04-07
```

### Composite product snapshot

```bash
wb --json product summary --nms 100525085,227403075
```

---

## Known API Behaviors

| Command | Behaviour |
|---------|-----------|
| `analytics sales-funnel history` | Max ~7-day lookback. Farther dates → 400. |
| `analytics sales-funnel history` | >2 rapid calls → 429 (exit 5). |
| `stats campaign` (fullstats) | Never-started campaigns → 400. |
| `stats campaign` (fullstats) | CLI auto-throttles: ~3 calls/min. |
| `analytics search-report` | Requires Analytics/Advanced token scope → 403 otherwise. |
| `bid get` (paused campaigns) | Returns 400; `wb pulse` handles gracefully. |
| `wb assess` full mode | ~20-25s due to fullstats rate limit. Use `--quick` when speed matters. |
| `budget deposit` | Amount in **rubles**, not kopecks. Minimum 1000 RUB, multiple of 50. |

> Full quirks list with wrong vs correct behavior: see [CLAUDE.md](CLAUDE.md) Known WB API Quirks section.

---

## Rate Limiting

The CLI throttles preemptively — no manual sleeps needed. If exit code 5 is returned, retry after a short wait. See `RATE_LIMITS.md` for the full command → endpoint → limit table.
