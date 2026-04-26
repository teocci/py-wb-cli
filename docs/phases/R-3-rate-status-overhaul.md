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

## Live verification (2026-04-26, post-release)

Read-only smoke test against the production env (`wb rate status` makes zero HTTP calls — just queries the local SQLite). The DB already had one row from the R-2 verification call to `/api/advert/v2/adverts` the day before.

**Table mode:**

```
$ wb rate status
Profile : 25169

Seller 407bbe2b-f3f9-404d-906f-99b2ef926815 (1 token)
                            Token def07bba57905265
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Endpoint               ┃ Remaining ┃ Reset (s) ┃ Last seen (s ago) ┃ State ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ /api/advert/v2/adverts │ 0/?       │ 0         │ 29327             │       │
└────────────────────────┴───────────┴───────────┴───────────────────┴───────┘
```

**JSON mode:**

```json
{
  "now_epoch": 1777196150.019,
  "profile": "25169",
  "sellers": [
    {
      "seller_id": "407bbe2b-f3f9-404d-906f-99b2ef926815",
      "tokens": [
        {
          "token_fp": "def07bba57905265",
          "endpoints": [
            {
              "endpoint": "/api/advert/v2/adverts",
              "remaining": 0,
              "bucket_limit": null,
              "reset_in_s": 0.0,
              "last_seen_ago_s": 29327.6,
              "locked": false
            }
          ]
        }
      ]
    }
  ]
}
```

Confirmed end-to-end:

- **Plaintext seller ID** (`407bbe2b-f3f9-404d-906f-99b2ef926815`) renders directly — no opaque hash, matching the R-1 design choice.
- **JSON shape matches the contract above** — top-level `now_epoch` / `profile` / `sellers[]`; per-endpoint `remaining`, `bucket_limit`, `reset_in_s`, `last_seen_ago_s`, `locked`. All pre-R-3 keys gone.
- **`locked: false` despite `remaining: 0`** is the correct evaluation — `reset_in_s = 0.0` (the bucket already refilled ~8 h ago), so the row is no longer actively locked. The `locked` flag follows `remaining == 0 AND reset_at > now`.
- **No `seller_cooldown` row surfaces** — the legacy F-13 row in the same DB file (still present from yesterday's accidental trigger, ~31 h expired) is correctly invisible. `rate_status` reads `endpoint_budget` exclusively.
- **F-14 confirmed fixed by construction** — there is no per-token gating filter in the read path, so the original "rate status reports clear while the next command 429s" failure mode cannot recur.
- **Diagnostic byproduct**: `last_seen_ago_s ≈ 29327` (~8 h) tells us no other `wb` calls have hit `/api/advert/v2/adverts` since the R-2 verification — the next call there will bootstrap fresh through the static prior, which is exactly what the metadata-driven model expects.

## Risks

- **JSON shape is breaking.** Documented in CHANGELOG. The pre-R-3 payload was small and already in flux; downstream consumers (the rate-recover skill and one report script) update in R-4.
