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
| `bid get` (paused campaigns) | Returns 400 for campaigns not currently running. |

---

## Rate Limiting

The CLI applies preemptive throttling for rate-sensitive endpoints. If exit code 5 is returned, the API is over capacity — retry after a short wait or reduce call frequency. The promotion client enforces limits automatically via a sliding-window `RateLimiter`; no manual sleep is needed between consecutive CLI calls.
