# Phase R-3 — `wb rate status` overhaul (v0.29.0)

**Status:** ✅ DONE — shipped in v0.29.0
**Date:** 2026-04-26
**Plan:** [analyze-why-the-wb-gentle-lightning.md](../../../../Users/teocci/.claude/plans/analyze-why-the-wb-gentle-lightning.md) · **Resolves:** F-14 (in conjunction with R-1..R-2)
**Tests:** 11 status tests + 7 untouched probe tests; full suite 1177/1178 (lone failure is the pre-existing `test_auth_list_empty` env-isolation flake; net +3 tests vs. the R-2 baseline)

## Goal

Rewrite `wb rate status` to surface the new per-`(token, endpoint)` state from `endpoint_budget`, grouped by plaintext `seller_id`. Eliminates the per-token-gated lookup that caused F-14 — every operator sees every active cooldown regardless of which token their shell is currently configured with.

## What's built in R-3

- **`src/wb/cli/rate.py`** — `rate_status` rewritten:
  - Reads `EndpointBudget.read_all()` directly. No `SellerCooldownLock` lookup, no `rate_limit_log` activity panel.
  - Groups rows by plaintext `seller_id` (alphabetical, unknowns last), then by token fingerprint (alphabetical), then by endpoint (locked first, then by ascending `reset_in_s`).
  - Each endpoint row carries `endpoint`, `remaining`, `bucket_limit`, `reset_in_s`, `last_seen_ago_s`, and `locked` (true when `remaining == 0 AND reset_at > now`).
  - Top-level payload: `{now_epoch, profile, sellers: [...]}`.
  - Table mode prints one block per seller; one rich table per token; columns `Endpoint | Remaining | Reset (s) | Last seen (s ago) | State`. Empty state prints `No rate-limit state recorded yet.`
  - `_recent_activity()` helper deleted (no consumer left).
  - `sqlite3` import dropped (no longer touched at this layer).
  - `wb rate probe` is untouched — it still uses `SellerCooldownLock` directly. R-4 cleanup deletes that path.
- **`tests/unit/test_cli_rate.py`** — `TestRateStatus` rewritten in full:
  - `test_locked_endpoint_surfaces`, `test_unlocked_endpoint_not_marked_locked`: the basic shape contract.
  - **`test_lock_visible_from_unrelated_token_shell`**: the F-14 regression test — seeds a row under `token_fp=locked_token_fp1`, then runs `rate status` with `WB_API_TOKEN` set to a different token. The lock still surfaces.
  - `test_grouping_by_seller_and_token`: two tokens for the same seller appear under one seller block.
  - `test_unknown_seller_id_falls_through`: rows with NULL `seller_id` render as `seller_id: null`.
  - `test_table_output_contains_key_fields`, `test_table_output_clean_state`: table-mode rendering.
  - `test_no_token_no_crash`, `test_compact_json_is_single_line`, `test_help`, `test_json_output_clean_state`: same coverage as before, ported to the new shape.
  - New helper `_seed_budget_row` writes directly to the `endpoint_budget` table; the old `_insert_rate_log_row` helper is gone.
  - `ServiceContainer.reset()` is called in fixtures and the no-token test because the `EndpointBudget` singleton is process-cached.

## JSON shape (breaking change)

```json
{
  "now_epoch": 1714000000.123,
  "profile": "default",
  "sellers": [
    {
      "seller_id": "abc-123" | null,
      "tokens": [
        {
          "token_fp": "a1b2..ef02",
          "endpoints": [
            {
              "endpoint": "/adv/v3/fullstats",
              "remaining": 0,
              "bucket_limit": 3,
              "reset_in_s": 3499.2,
              "last_seen_ago_s": 12.5,
              "locked": true
            }
          ]
        }
      ]
    }
  ]
}
```

The pre-R-3 keys (`seller_fingerprint`, `token_fingerprint`, `seller_cooldown_seconds`, `locked` at top level, `endpoint_activity_5min`) are gone. The `wb-rate-recover` skill and `scripts/generate_daily_wb_report.py` still reference them; updates land in R-4.

## What's NOT in R-3

- **`SellerCooldownLock`, `SELLER_GLOBAL_BUDGET`, the static seller-global limiter** — still defined in `rate_limiter.py` / `constants.py`. R-4 deletes them.
- **`wb rate probe`** — unchanged. Still uses `SellerCooldownLock` directly per the R-3 plan ("continues to function unchanged").
- **Skill / script call-site updates** — `wb-rate-recover` and `generate_daily_wb_report.py` need to learn the new shape. R-4 sweeps them.

## Verification

```bash
$VENV/python -m pytest tests/unit/test_cli_rate.py -v   # 18 passed
$VENV/python -m pytest tests/unit/ -q                   # 1177 passed, 1 pre-existing flake
```

Cross-token visibility regression test (`test_lock_visible_from_unrelated_token_shell`) demonstrates the original F-14 bug is impossible by construction — `read_all()` ignores token gating entirely.

## Risks

- **JSON shape is breaking.** Documented in CHANGELOG. The pre-R-3 payload was small and already in flux; downstream consumers (the rate-recover skill and one report script) update in R-4.
