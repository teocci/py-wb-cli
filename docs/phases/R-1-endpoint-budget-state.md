# Phase R-1 — `EndpointBudget` state layer (v0.28.0)

**Status:** ✅ DONE — shipped in v0.28.0 (combined release with R-2)
**Date:** 2026-04-26
**Plan:** [analyze-why-the-wb-gentle-lightning.md](../../../../Users/teocci/.claude/plans/analyze-why-the-wb-gentle-lightning.md) · **Resolves:** F-14 (in conjunction with R-2..R-4)
**Tests:** 38 new tests in `tests/unit/test_endpoint_budget.py`, all green

## Goal

Land the new state-of-truth module — `wb.core.endpoint_budget.EndpointBudget` — with full unit-test coverage, but no integration into the HTTP client yet (that's R-2). Until R-2 lands, the existing F-13 lock + seller-global limiter continue to govern runtime behaviour, so this phase is a pure addition (no regression risk).

## What's built in R-1

- **`src/wb/core/endpoint_budget.py`** — new module:
  - `BudgetRow` frozen dataclass: `token_fp`, `endpoint`, `seller_id`, `bucket_limit`, `remaining`, `reset_at`, `last_seen`.
  - `EndpointBudget` class wrapping the new SQLite table `endpoint_budget` (PK `(token_fp, endpoint)`) on the same `~/.wb-cli/rate_limits.db` file. WAL mode, mirrors the fallback-to-in-memory pattern from `SellerCooldownLock`.
  - `reserve(token_fp, endpoint, *, prior, seller_id=None)` — blocks until a slot is available. Falls back to `SharedRateLimiter` (per-endpoint sliding window) when no live header data exists or the previous window has expired. Decrements `remaining` provisionally between calls; sleeps until `reset_at` when the bucket is empty.
  - `observe(token_fp, endpoint, response, *, seller_id=None)` — UPSERT bucket state from `x-ratelimit-limit` / `x-ratelimit-remaining` / `x-ratelimit-reset`. No-op when no headers present. `seller_id` non-key column for diagnostics.
  - `observe_headers(...)` — same as `observe`, takes a raw headers mapping for tests.
  - `read_all() -> list[BudgetRow]` — full table dump for `wb rate status` (R-3).
  - `parse_int_header`, `parse_rate_limit_reset` — module-level header parsers reused by tests and (later) by the HTTP client during R-2.
- **`tests/unit/test_endpoint_budget.py`** — coverage for: reserve/observe round-trip, expired-bucket re-bootstrap, missing-headers no-op, in-memory fallback on corrupt DB, cross-process via two instances on the same `tmp_path`, lock-and-wait when `remaining == 0`, observe overwrites bootstrap state, plaintext `seller_id` round-trips through schema.

## What's NOT in R-1

- **No HTTP-client integration** — `EndpointBudget` is dead code at runtime until R-2 wires it into `WbHttpClient.request` / `request_raw`.
- **No deletion** of `SellerCooldownLock`, `SharedRateLimiter`, or `_seller_limiter` — those still own the runtime path. R-2 disconnects them; R-4 deletes them.
- **No changes to `wb rate status`** — that command still reads `seller_cooldown` until R-3.

## Verification

```bash
$VENV/python -m pytest tests/unit/test_endpoint_budget.py -v
$VENV/python -m pytest tests/unit/ -v  # full suite must still pass
```

No behaviour change observable through the CLI in R-1.

## Findings from the live test on 2026-04-26

Two safe calls to `/adv/v1/balance` against a temp DB validated the design and surfaced two corrections (now fixed in R-1):

1. **WB sends only `X-Ratelimit-Remaining` on 200s** — no `Limit`, no `Reset`, no `Retry`. The official rate-limits doc ([docs/web/rate-limits.md](../web/rate-limits.md)) confirms this is by design ("X-Ratelimit-Remaining ... appears in all response statuses except for error 429"). On 429, WB sends all four headers.
2. **`X-Ratelimit-Retry` ≠ `X-Ratelimit-Reset`** — they encode different things. From the doc's example:
   ```
   X-Ratelimit-Reset: 29   ← burst back to max in 29 s
   X-Ratelimit-Retry: 2    ← can retry next request in 2 s
   ```
   The original parser preferred `Retry-After` then `Reset` then `Retry`, picking `Reset` when only WB's headers were sent — over-waiting by ~14×. Fixed: preference order is now `X-Ratelimit-Retry → Retry-After → X-Ratelimit-Reset` (most precise → HTTP standard fallback → worst-case "full burst back" fallback). The parser was also renamed `parse_rate_limit_reset → parse_rate_limit_wait` to match the corrected semantics.
3. **Fallback wait must be `interval = period / calls`, not `period`** — per the doc's "interval = period/limit" formula. For 300/min, the interval is 200 ms, not 60 s. Using the period would over-wait by a factor of `calls` for any burst-style endpoint. Fixed in `EndpointBudget.reserve`.

Bonus observation: WB's penalty mode genuinely slows the refill rate dramatically. The two-call test triggered a real `X-Ratelimit-Reset: 1800` (30-minute) cooldown on the seller's `/adv/v1/balance` slot. The new design honours this verbatim — there's no point trying to outsmart it; the only defence is to not exhaust the bucket in the first place. Bootstrap priors for burst-1 endpoints (e.g. `EP_ACCOUNT_BALANCE = (1, 1.0)`) should be reviewed at R-4 — empirically WB tolerates less than 1/s on these.

## Risks (resolved)

- ~~**WB header semantics on 200 responses** are not in `dev-wb-adv.md`; we assume the same shape WB sends on 429.~~ Resolved by the live test + official doc cross-reference: 200s carry only `X-Ratelimit-Remaining`. The interval-based fallback in `reserve` covers this case.
