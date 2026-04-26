# Phase R-3 — `wb rate status` overhaul

**Status:** 🔲 PLANNED · **Depends on:** R-2
**Plan:** [analyze-why-the-wb-gentle-lightning.md](../../../../Users/teocci/.claude/plans/analyze-why-the-wb-gentle-lightning.md)

## Goal

Rewrite `wb rate status` to surface the new per-`(token, endpoint)` state from `endpoint_budget`, grouped by plaintext `seller_id`. Eliminates the per-token-gated lookup that caused the original bug — every operator sees every active cooldown regardless of which token their shell is currently configured with.

## Changes

| File | Change |
|------|--------|
| `src/wb/cli/rate.py` | `rate_status`: replace `SellerCooldownLock.read_remaining` call with `EndpointBudget.read_all()`. Group rows by `seller_id` (use `(unknown sid: <token_fp>)` when NULL). For each `(seller, token, endpoint)` row, render `remaining/limit`, `reset_in_s`, `last_seen_ago`. Mark `remaining == 0 AND reset_at > now` as `LOCKED`. Drop the old "last 5-min activity" panel querying `rate_limit_log`; replace with the new state's `last_seen` column. JSON shape changes — bump the docstring. |
| `tests/unit/test_rate_status.py` (or wherever the existing tests live) | Rewrite for the new payload shape. Add a test that an injected lock for an endpoint not matching the resolved token still appears in output. |

## Example output

```
Seller 12345 (2 tokens)
  Token a1b2..ef02 (promotion)
    /adv/v3/fullstats     remaining 0/3   reset in 3499s   ← LOCKED
    /adv/v1/balance       remaining 1/1   reset in 0s
  Token c4d5..1234 (analytics)
    /api/v3/sales-funnel  remaining 2/3   reset in 22s
```

## Verification

- `wb rate status` from a shell where the token does NOT match the locked seller still surfaces the lock — original bug becomes impossible by construction.
- `wb rate status --json` round-trips through `json.loads`.
- `wb rate probe` continues to function unchanged (it still makes a single calibration call — just one that goes through the new `observe` pipeline like any other request).

## Risks

- **JSON shape is breaking** for any external consumer parsing `rate status --json`. Document in the release notes; the pre-existing payload was small and already in flux due to F-14.
