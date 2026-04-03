# WB CLI — AI Agent Improvement Roadmap

This document tracks improvements to make the WB CLI optimally usable by AI agents.
Discovered during real agent sessions (2026-04-03) where the CLI's limitations forced
the agent to bypass it and call raw HTTP endpoints.

---

## Best Practices for AI Agent CLIs

### 1. Token Efficiency

- **Compact output** — Agents pay per-token; offer `--compact` for single-line JSON.
- **Field selection** — `--fields spend,orders,views` to return only what's needed.
- **Batch everything** — Every command that accepts a single ID should also accept
  comma-separated IDs. One call returning 50 results is cheaper than 50 calls.

### 2. Structured Output

- **Response envelope** — Every response (success or error) follows:
  ```json
  {"status": "ok|error", "data": ..., "meta": {"count": N, "timestamp": "..."}}
  ```
- **JSON errors** — When `--json` is active, errors must be JSON, not colored text.
- **Machine-readable error codes** — `VALIDATION_ERROR`, `RATE_LIMITED`, not just messages.

### 3. Batch Operations

- **Array inputs** — `--ids 1,2,3`, `--nms 100525085,227403075`.
- **Auto-chunking** — When input exceeds API limits (e.g., 50 campaigns for fullstats),
  automatically split into chunks, call the API for each, and merge results.
- **N+1 elimination** — Never loop single API calls when a batch endpoint exists.

### 4. No Interactive Prompts

- **Never block on stdin** — Remove `prompt=True` from CLI options.
- **`--yes` flag** — Skip confirmation prompts. When `--json` is active, auto-skip.
- **Fail fast** — If a required value is missing, return a structured error immediately.

### 5. Idempotent Operations

- **Safe retries** — `campaign start` on an already-running campaign returns
  `{"already_applied": true}` instead of an error.
- **Consistent state** — Same input always produces same output.

### 6. Composite Commands

- **Reduce round-trips** — `product summary --nms 100525085` returns sales + ad spend +
  clusters + bids in one call instead of 4 separate commands.

---

## Current Issues Found

### CRITICAL

| Issue | Location | Impact |
|-------|----------|--------|
| Errors are colored text, not JSON, even with `--json` | `src/wb/cli/app.py:79-80` | Agents can't parse errors |
| Interactive prompts block agents | `src/wb/cli/auth.py:30` (`prompt=True`) | Agent hangs on stdin |
| CampaignStats loses per-NM breakdown | `src/wb/domain/models.py:262-307` | Agent must bypass CLI for per-product spend |
| Campaign model drops product NM IDs | `src/wb/domain/models.py:66-81` | Agent can't discover which products are in a campaign |

### HIGH

| Issue | Location | Impact |
|-------|----------|--------|
| N+1 in set_item_bids | `src/wb/services/bids.py:125-127` | N HTTP calls instead of 1 batch call |
| No multi-campaign start/pause/stop | `src/wb/cli/campaign.py` | Agent must loop one-at-a-time |
| Hardcoded exit codes | `src/wb/cli/auth.py`, `bid.py`, etc. | Inconsistent machine-readable codes |
| No structured error codes in exceptions | `src/wb/core/exceptions.py` | No programmatic error matching |
| set_item_bid wraps single in array | `src/wb/client/promotion.py:385-391` | Forces N+1 at service layer |

### MEDIUM

| Issue | Location | Impact |
|-------|----------|--------|
| Batch size limits scattered | Multiple service files | Not auto-chunked |
| Analytics NM ID limit (20), no auto-chunking | `src/wb/services/analytics.py:114` | Silent truncation |
| Cache not auto-queried by services | `src/wb/storage/cache.py` | Redundant API calls |
| No per-product ad spend command | — | #1 agent question unanswerable in one call |
| No booster stats / search position | API returns `boosterStats[]` | Useful data discarded |
| Bid mutations require file input | `src/wb/cli/bid.py:172` | Agent must write temp files |

### LOW

| Issue | Location | Impact |
|-------|----------|--------|
| No rate-limit-aware batching | `src/wb/client/http.py` | Fullstats is 3 calls/min |
| DI patterns simplistic | `src/wb/services/_factory.py` | Re-reads config every call |

---

## Phased Improvement Roadmap

### Phase 1 — Agent-Critical Fixes (v0.9.0)

**Theme:** Make the CLI reliably usable by AI agents without workarounds.

| Task | Files | Description |
|------|-------|-------------|
| Structured JSON errors | `exceptions.py`, `output.py`, `app.py` | Add `error_code` to exceptions, emit JSON errors when `--json` is active |
| No interactive prompts | `auth.py`, `bid.py`, `budget.py` | Remove `prompt=True`, add `--yes` flag, auto-skip confirms in JSON mode |
| Campaign NM IDs | `models.py`, `campaign.py` | Add `nm_ids: list[int]` to Campaign, parse from `nm_settings[]` |
| Per-NM stats breakdown | `models.py`, `stats.py` | Add `NmStats`/`DayStats`, parse `days[].apps[].nms[]` from fullstats |
| Exit code consistency | All CLI files | Replace hardcoded integers with `ExitCode` enum |
| Shared CLI helpers | `_helpers.py` (new) | Extract `_get_renderer`, `_get_profile`, `_confirm_or_abort` |

---

### Phase 2 — Batch Operations (v0.10.0)

**Theme:** Make every operation batch-aware; eliminate N+1 patterns.

| Task | Files | Description |
|------|-------|-------------|
| Batch item bids | `promotion.py`, `bids.py` | Add `set_item_bids(list)`, single PATCH call |
| Multi-campaign actions | `campaign.py`, `campaigns.py` | `--ids 1,2,3` for start/pause/stop/delete |
| Inline bid mutations | `bid.py` | `--bids '[{"nm_id":123,"cpm":450}]'` (no file needed) |
| Centralize batch limits | `constants.py`, `batching.py` (new) | `chunk()` generator, limits in constants |
| Auto-chunking | `analytics.py` | Split large NM lists into API-sized chunks |
| Field selection | `app.py`, `output.py` | `--fields spend,orders,views` global flag |

---

### Phase 3 — Per-Product Cost Tracking (v0.11.0)

**Theme:** Answer the #1 agent question: "how much did we spend on ads for product X?"

| Task | Files | Description |
|------|-------|-------------|
| `stats product-spend` | `models.py`, `stats.py`, CLI | New command: per-NM ad spend across all campaigns |
| Booster stats | `models.py`, `stats.py` | Parse `boosterStats[]` (avg_position per NM) |
| Cache auto-populate | `stats.py`, `campaigns.py` | Write-through to SQLite cache on API calls |

---

### Phase 4 — Composite Commands (v1.0.0)

**Theme:** High-level commands that reduce agent round-trips. The 1.0 release.

| Task | Files | Description |
|------|-------|-------------|
| `product summary` | `product.py` (new), `product_service.py` (new) | Sales + ad spend + clusters + bids in one call |
| `campaign overview` | `campaign.py` | Details + budget + stats + per-NM + clusters |
| Idempotent mutations | `models.py`, `campaigns.py` | `already_applied: bool` on MutationResult |
| SDK parity | `sdk.py` | Every CLI command has a Python SDK function |

---

### Phase 5 — Rate Limiting & Resilience (v1.1.0)

**Theme:** Production-grade reliability for long-running agent sessions.

| Task | Files | Description |
|------|-------|-------------|
| Rate-limit-aware batching | `batching.py`, `http.py` | `RateLimiter` class, preemptive throttling |
| Auto-pagination | `analytics.py`, `batching.py` | Fetch all pages and concatenate |
| Service container | `_factory.py` | Cache `Settings`, HTTP clients, services |

---

### Phase 6 — Polish & Ergonomics (v1.2.0)

**Theme:** Quality-of-life improvements that compound agent efficiency.

| Task | Files | Description |
|------|-------|-------------|
| Compact JSON | `app.py` | `--compact` flag: single-line JSON output |
| Cache auto-query | Services | Check cache first (with TTL), fall back to API |
| Agent documentation | `AGENT.md` (new) | Command reference, response format, workflows |

---

## Version Scheme

| Version | Milestone |
|---------|-----------|
| 0.9.0 | Phase 1 — Agent-critical fixes |
| 0.10.0 | Phase 2 — Batch operations |
| 0.11.0 | Phase 3 — Per-product cost tracking |
| 1.0.0 | Phase 4 — Composite commands (stable release) |
| 1.1.0 | Phase 5 — Rate limiting & resilience |
| 1.2.0 | Phase 6 — Polish & agent ergonomics |
