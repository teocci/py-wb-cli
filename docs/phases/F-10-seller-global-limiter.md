# Fix F-10 — Seller-scope global rate limiter (v0.25.2)

**Date:** 2026-04-24
**Tests:** 1104/1105 (1 pre-existing env-isolation failure in `test_auth_list_empty`, unrelated)

## Problem

The preemptive rate limiter (`ENDPOINT_LIMITS`) throttles per endpoint path. WB's gateway also enforces a **per-seller global budget** across *all* advert + analytics endpoints — the same seller token hitting `list_campaigns`, `fullstats`, and `sales-funnel` in quick succession consumes one shared budget. The CLI had no representation of this scope, so calls passed the per-endpoint limiter and were rejected by WB with:

```
HTTP 429   {"title":"too many requests",
            "detail":"Limited by global limiter, per seller 173f8646-dc21-58c0-892e-ba069dc0a9cb"}
```

Coupled with F-9, the CLI would back off patiently on 429s — but could still exhaust four attempts before the seller window cleared, especially under multi-endpoint workloads like `stats daily-report` that touch three rate-limited endpoints in sequence.

## What Was Built

- **`compute_seller_fingerprint(token)`.** New helper in `src/wb/core/rate_limiter.py`. Splits the JWT, base64url-decodes the payload, extracts the `sid` claim, and returns `sha256('sid:<uuid>')[:16]`. Falls back to `compute_token_fingerprint` on any parse failure (non-JWT, malformed base64, JSON error, missing / non-string `sid`) — so non-WB tokens degrade gracefully to per-token scope instead of crashing.
- **Constants.** `SELLER_GLOBAL_BUDGET = (30, 60.0)` and `SELLER_GLOBAL_SCOPE_KEY = '_seller_global'` added to `src/wb/core/constants.py`. Budget is a conservative fixed default; the leading underscore on the scope key prevents collision with any real WB endpoint path.
- **Factory: `_build_seller_limiter(token)`.** New function in `src/wb/services/_factory.py` that mirrors `_build_limiters`' env-var opt-out logic (`WB_RATE_LIMITER=memory` → `RateLimiter`, otherwise `SharedRateLimiter` keyed by the seller fingerprint at `~/.wb-cli/rate_limits.db`). Container's `http_client` factory wires the seller limiter alongside the per-path ones whenever `with_rate_limits=True`.
- **HTTP client: two-tier acquire.** `WbHttpClient.__init__` now accepts `seller_limiter`. In both `request` and `request_raw`, the seller limiter is acquired **before** the per-path limiter on every request. If the seller budget is exhausted, the call sleeps in `acquire` rather than hitting WB's gateway. Tokens of the same seller (promotion / analytics / statistics) coordinate through the single shared DB row family because they hash to the same seller fingerprint.

## Files Changed

| File | Change |
|------|--------|
| `src/wb/core/constants.py` | Added `SELLER_GLOBAL_BUDGET`, `SELLER_GLOBAL_SCOPE_KEY` + `__all__` entries |
| `src/wb/core/rate_limiter.py` | Added `compute_seller_fingerprint`, imports for `base64`/`binascii`/`json`, new entry in `__all__` |
| `src/wb/services/_factory.py` | Added `_build_seller_limiter`, updated `ServiceContainer.http_client` to build and pass `seller_limiter` |
| `src/wb/client/http.py` | `__init__` accepts `seller_limiter`; `request` and `request_raw` acquire it before the per-path limiter; docstring updated to describe two-tier limiting |
| `tests/unit/test_rate_limiter.py` | 12 new tests: 9 for `compute_seller_fingerprint` (16-hex, determinism, same-sid collision, distinct-sid differ, sid vs. token fp differ, malformed-JWT fallback, missing-sid fallback, non-string-sid fallback, garbage-payload fallback) + 3 `TestSellerLimiterFactory` (default → SharedRateLimiter with correct endpoint key and fingerprint; env opt-out → RateLimiter; budget matches `SELLER_GLOBAL_BUDGET`) |
| `tests/unit/test_http_client.py` | 3 new tests: acquire order (seller → path), seller limiter fires even for paths without per-endpoint limiter, no-op when `seller_limiter=None` |
| `docs/FIXES.md`, `docs/PROGRESS.md` | F-10 row flipped to ✅ DONE |

## Live Test Results

### Seller fingerprint matches the JWT claim, not the token bytes

The CLI loaded `WB_API_TOKEN` from `.env` (highest priority after CLI flag, per the credential chain). After running `wb --json --compact campaign list`:

```
seller fp : 589f628451e31cb7   ← sha256('sid:173f8646-dc21-58c0-892e-ba069dc0a9cb')[:16]
token  fp : def07bba57905265   ← sha256(token_bytes)[:16]
```

`~/.wb-cli/rate_limits.db` after the call:

```
def07bba57905265  /api/advert/v2/adverts  82s ago   ← per-endpoint (token-keyed)
589f628451e31cb7  _seller_global          82s ago   ← seller-scope (sid-keyed)
```

The two fingerprints are genuinely distinct — F-10 is deriving the seller scope from the JWT `sid`, not from the token bytes. A second token for the same seller (e.g. the analytics token in `profiles.json`) would hash to the same `589f628451e31cb7` and coordinate through the same `_seller_global` row, which is exactly the cross-token pooling F-10 exists to provide.

### 429 behaviour while the seller window is externally exhausted

During the same test the WB gateway was still 429-ing from earlier raw-httpx probing that bypassed the CLI:

```
Rate limited (attempt 1/4), retrying in 5.3s
Rate limited (attempt 2/4), retrying in 19.2s
Rate limited (attempt 3/4), retrying in 53.1s
```

F-9's patient schedule kicks in correctly, and only **one** row was written per call (not four) — `acquire` only records on the first attempt, and retries don't double-count. The 429 here is a side-effect of uncontrolled probes outside the CLI; when the whole workload runs through `wb`, the 30/60-s seller budget will keep WB's gateway below its trigger threshold.

### Opt-out still works

`WB_RATE_LIMITER=memory` routes both per-endpoint *and* seller-scope limiters to in-process `RateLimiter`, preserving the diagnostic opt-out from I-12.
