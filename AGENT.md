# WB CLI — AI Agent Reference

Quick reference for AI agents using the WB CLI to manage Wildberries advertising.

---

## Setup

```bash
# Minimum: one full-scope API token covers all commands
export WB_API_TOKEN="<your-jwt>"

# Optional: separate analytics token (higher priority for analytics commands)
export WB_ANALYTICS_TOKEN="<analytics-jwt>"

# Optional: portal session (required only for wb portal and wb auth generate-token)
export WB_AUTHORIZEV3="<key>"
export WB_PORTAL_COOKIE="<browser-cookie>"
```

No profile registration needed when env vars are set.

To store a token under all 11 API categories at once use `--category all`:
```bash
wb auth login --token "<jwt>" --category all
```
Run `wb auth categories` (or `wb auth categories --json`) to list all valid `--category` values.

---

## Global Flags

| Flag | Effect |
|------|--------|
| `--json` | Machine-readable JSON output (always use in agent sessions) |
| `--compact` | Single-line JSON — fewer tokens, same data |
| `--fields a,b` | Return only listed keys (JSON mode only) |
| `--quiet` | Suppress all non-essential output |
| `--profile <name>` | Use a named credential profile |

**Recommended agent invocation pattern:**

```bash
wb --json --compact <command> [args]
```

---

## Response Format

All JSON responses are bare arrays or objects — no envelope wrapper.

**Success (list):**
```json
[{"nm_id": 123456, "order_count": 42, ...}, ...]
```

**Success (single object):**
```json
{"campaign_id": 7890, "status": "running", ...}
```

**Error (WbCliError):**
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

Morning account snapshot. Aggregates balance + campaign status + 7-day product spend in one command. Also saves bid baselines to `~/.wb-cli/pulse_baseline.json` for intraday drift detection.

```bash
# Full snapshot (balance + campaigns + product spend — ~20-25s due to fullstats rate limit)
wb --json --compact assess

# Quick snapshot (no product spend — fast, under 5s)
wb --json --compact assess --quick

# With single-product detail
wb --json --compact assess --nm 100525085
```

**Returns:** `{data_as_of, balance_rub, running[], paused[], ready[], product_spend_7d[]}`

> Run once per morning before making any bid or budget decisions. Full mode saves bid baselines required by `wb pulse`.

### `wb pulse`

Intraday health check using real-time endpoints only (no analytics). Detects bid drift, budget depletion, and campaign pauses.

```bash
# Check specific campaigns
wb --json --compact pulse --campaigns 29156792,34926371

# Single campaign
wb --json --compact pulse -c 29156792
```

**Returns:** `{timestamp, campaigns[], action_needed}` where each campaign has:
- `budget_remaining_rub` — current budget balance
- `bid_recommend_drift_pct` — % change vs morning baseline
- `bid_floor_drift_pct` — % change in minimum bid vs morning
- `alerts[]` — any of: `competitor_surge`, `budget_low`, `campaign_paused`, `bid_floor_rising`

**Alert thresholds:**

| Alert | Trigger | Action |
|-------|---------|--------|
| `competitor_surge` | bid recommendation up >15% since morning | Raise bids via `wb bid set-items` |
| `budget_low` | balance < 500 RUB or < 20% of morning balance | `wb budget topup` |
| `campaign_paused` | status changed to paused | Topup then `wb campaign start` |
| `bid_floor_rising` | minimum bid up >10% since morning | Verify current bids still above floor |

> Requires `wb assess` (full mode) to have run today — baseline must exist in `~/.wb-cli/pulse_baseline.json`.

### `wb campaign`

```bash
wb --json campaign list                         # all campaigns
wb --json campaign list --status running        # filter by status
wb --json campaign get --id 123456              # single campaign with nm_ids
wb campaign start --ids 1,2,3                   # start multiple
wb campaign pause --ids 1,2,3
wb campaign stop  --ids 1,2,3
wb campaign delete --id 123456 --yes
```

### `wb bid`

```bash
wb --json bid get --nm 100525085
wb bid set --nm 100525085 --cpm 450
wb bid set --bids '[{"nm_id":100525085,"cpm":450},{"nm_id":227403075,"cpm":380}]'
wb --json bid min --nm 100525085               # minimum allowed bid
```

### `wb budget`

```bash
wb --json budget get                            # current balance
wb budget deposit --campaign-id 7890 --amount 5000 --yes
```

### `wb stats`

```bash
# Per-campaign stats
wb --json stats campaign --id 7890 --from 2026-04-01 --to 2026-04-07

# All campaigns stats (auto-chunked, up to 50 per API call)
wb --json stats campaigns --from 2026-04-01 --to 2026-04-07

# Per-NM ad spend across all campaigns
wb --json stats product-spend --nms 100525085,227403075 --from 2026-04-01 --to 2026-04-07
```

### `wb analytics sales-funnel`

```bash
# Product sales stats for a period (all products, no filter)
wb --json analytics sales-funnel products \
  --from 2026-03-31 --to 2026-04-07 --limit 100

# Top 10 by orders
wb --json --compact analytics sales-funnel products \
  --from 2026-03-31 --to 2026-04-07 \
  --sort-by orders --top 10

# Filter by NM IDs, sort by revenue
wb --json analytics sales-funnel products \
  --from 2026-03-31 --to 2026-04-07 \
  --nm-ids 100525085,227403075 --sort-by revenue

# Per-day breakdown (max 7-day window, 1-20 NM IDs)
wb --json analytics sales-funnel history \
  --from 2026-04-01 --to 2026-04-07 \
  --nm-ids 100525085,227403075
```

**Sort field aliases for `--sort-by`:**

| Alias | Field |
|-------|-------|
| `orders` | `order_count` |
| `opens` | `open_count` |
| `cart` | `cart_count` |
| `revenue` | `order_sum` |
| `buyouts` | `buyout_count` |

### `wb prices`

```bash
wb --json prices list                           # all products
wb --json prices list --nm-ids 100525085,227403075
wb --json prices list --min-discount 10        # filter by min discount %
```

### `wb product`

```bash
# Composite snapshot: sales + ad spend + clusters + bids in one call
wb --json product summary --nms 100525085,227403075
wb --json --compact product summary --nms 100525085
```

### `wb cluster`

```bash
wb --json cluster list --nm 100525085          # search clusters for a product
wb --json cluster get-bids --campaign-id 7890
wb cluster set-bids --campaign-id 7890 --bids '[{"cluster_id":1,"cpm":300}]'
wb --json cluster stats --campaign-id 7890 --from 2026-04-01 --to 2026-04-07
```

### `wb optimize`

```bash
wb --json optimize recommend                   # recommendations (dry-run safe)
wb optimize apply --yes                        # apply all recommendations
```

### `wb report`

```bash
wb --json report warehouse list                # warehouse inventory
wb --json report warehouse stock-runway        # days until stockout
wb report warehouse list --no-cache            # force fresh API call
```

### `wb portal`

```bash
wb --json portal products --limit 100          # product cards from portal
```

### `wb cache`

```bash
wb --json cache campaigns                      # cached campaign snapshots
wb --json cache stats --from 2026-04-01        # cached stats
```

---

## Common Agent Workflows

### Daily monitoring routine

```bash
# Morning — run once after 9h
wb --json --compact assess

# Parse running campaign IDs from output, then intraday (every 1-2h)
wb --json --compact pulse --campaigns 29156792,34926371,35823936

# If budget_low alert fires
wb budget topup --campaign 29156792 --sum 100000 --yes   # 1000 RUB = 100000 kopecks

# If campaign_paused alert fires
wb budget topup --campaign 29156792 --sum 100000 --yes
wb campaign start --ids 29156792 --yes
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
# 1. Get all running campaign NM IDs
NMS=$(wb --json campaign list --status running \
  | python -c "import sys,json; print(','.join(str(n) for c in json.load(sys.stdin) for n in c.get('nm_ids',[])))")

# 2. Per-NM spend
wb --json stats product-spend --nms "$NMS" --from 2026-04-01 --to 2026-04-07
```

### Composite product snapshot

```bash
# Sales funnel + ad spend + clusters + bids + prices in one call
wb --json product summary --nms 100525085,227403075
```

### Bid optimization loop

```bash
# 1. Get recommendations
wb --json optimize recommend

# 2. Review, then apply
wb optimize apply --yes
```

---

## Known API Quirks

| Command | Behaviour |
|---------|-----------|
| `analytics sales-funnel history` | Max ~7-day lookback. Farther dates → 400. |
| `analytics sales-funnel history` | Rate-limited: >2 rapid calls → 429 (exit 5). |
| `stats campaign` (fullstats) | Never-started campaigns → 400. |
| `stats campaign` (fullstats) | Strict rate limit: ~3 calls/min. CLI auto-throttles. |
| `analytics search-report` | Requires Analytics/Advanced token scope → 403 otherwise. |
| `bid get` (paused campaigns) | Returns 400 for campaigns not currently running. `wb pulse` handles this gracefully — returns `bid_recommend_rub: 0.0` and skips drift computation. |
| `wb assess` (full mode) | Takes ~20-25s — fullstats rate limit (1 call/20s) applies per campaign batch. Use `--quick` when speed matters more than spend data. |
| `wb pulse` bid drift | `bid_recommend_drift_pct` is 0.0 and `competitor_surge` cannot fire if `wb assess` was run with `--quick` (no baseline) or baselines are older than today. |

---

## Rate Limiting

The CLI applies preemptive throttling for rate-sensitive endpoints. If exit code 5 is returned, the API is over capacity — retry after a short wait or reduce call frequency. The promotion client enforces limits automatically via a sliding-window `RateLimiter`; no manual sleep is needed between consecutive CLI calls.
