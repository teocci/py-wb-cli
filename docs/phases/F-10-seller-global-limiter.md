# Fix F-10 — Seller-scope global rate limiter (v0.25.2)

**Status:** 🔲 PLANNED
**Scope:** `src/wb/core/constants.py`, `src/wb/core/rate_limits.py`, `src/wb/services/_factory.py`, `src/wb/client/http.py`

## Problem

The preemptive rate limiter (`ENDPOINT_LIMITS`) throttles per endpoint path. WB's gateway also enforces a **per-seller global budget** across *all* advert + analytics endpoints — the same seller token hitting `list_campaigns`, `fullstats`, and `sales-funnel` in quick succession consumes one shared budget. The CLI has no representation of this scope, so calls pass the per-endpoint limiter and are rejected by WB with `429 Limited by global limiter, per seller <sid>`.

## Solution

Add a second `SharedRateLimiter` keyed by the **seller UUID** (extracted from the JWT `sid` claim in the token payload), with a conservative fixed budget of **30 calls / 60 s**. Acquire this seller-scope limiter **before** the per-endpoint limiter in `WbHttpClient.request` / `request_raw`. Because WB's global budget spans every endpoint for the seller, keying by `sid` (not by token fingerprint) makes different tokens of the same seller coordinate.

If JWT parsing fails (malformed, encrypted, or non-JWT token), fall back silently to keying by token fingerprint — the seller-scope limiter degrades into a per-token scope, which is still better than no global limiter.

## Steps

- [ ] Add `SELLER_GLOBAL_BUDGET = (30, 60.0)` and `SELLER_GLOBAL_SCOPE_KEY = '_seller_global'` to `src/wb/core/constants.py`.
- [ ] Add JWT `sid` extractor (`compute_seller_fingerprint(token)`) in `src/wb/core/rate_limiter.py`; fall back to `compute_token_fingerprint` on parse error.
- [ ] Extend `_build_limiters(token)` in `src/wb/services/_factory.py` to build the seller-scope limiter as an extra entry.
- [ ] Update `WbHttpClient.__init__` to accept an optional `seller_limiter`; acquire it in `request` / `request_raw` **before** the per-path limiter.
- [ ] Unit tests: `compute_seller_fingerprint` determinism, JWT-parse failure fallback, factory emits seller limiter, `WbHttpClient.request` acquires seller limiter first.
- [ ] Live test: fire ≥5 sequential `wb campaign list` calls — seller limiter should pace them; no 429 exits.
