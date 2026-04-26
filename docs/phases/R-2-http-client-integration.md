# Phase R-2 — HTTP client integration (v0.28.0)

**Status:** ✅ DONE — shipped in v0.28.0 (combined release with R-1)
**Date:** 2026-04-26
**Plan:** [analyze-why-the-wb-gentle-lightning.md](../../../../Users/teocci/.claude/plans/analyze-why-the-wb-gentle-lightning.md)
**Tests:** 1174/1175 passing (the lone failure is the pre-existing `test_auth_list_empty` env-isolation flake; net +33 tests across R-1+R-2)

## Goal

Wire `EndpointBudget` into `WbHttpClient` and disconnect F-13's `SellerCooldownLock` + the static seller-global limiter from the runtime path. After R-2, runtime rate-limiting is driven by WB's own `x-ratelimit-*` headers. Other endpoints stay usable when one endpoint hits a long cooldown.

## Changes (as shipped)

| File | Change |
|------|--------|
| `src/wb/client/http.py` | New `_pre_flight(path)` and `_observe(path, response)` helpers. `request` / `request_raw` now: pre-flight (inside the loop), HTTP, observe (always, before status checks), then handle. Dropped `_check_cooldown_lock`, `_record_cooldown`. Constructor surface: `budget` + `token_fp` + `seller_id` (replacing `path_limiters` + `seller_limiter` + `cooldown_lock` + `seller_fingerprint`). Header preference fixed to match the official WB doc: `('x-ratelimit-retry', 'Retry-After', 'x-ratelimit-reset')`. |
| `src/wb/services/_factory.py` | New `ServiceContainer.endpoint_budget()` singleton; new `_extract_seller_id(token)` helper extracting JWT `sid`. Deleted `_build_limiters`, `_build_seller_limiter`, `_build_cooldown_lock`. Removed `SELLER_GLOBAL_BUDGET` / `SELLER_GLOBAL_SCOPE_KEY` imports (still defined in `constants.py`; deleted in R-4). |
| `src/wb/core/endpoint_budget.py` | Added `force_memory: bool = False` ctor flag so `WB_RATE_LIMITER=memory` keeps working without relying on a DB-failure trigger. Added `max_wait_seconds` knob to `reserve` so the F-12 60 s bail-out semantics survive (raise instead of sleeping when WB-supplied wait exceeds the ceiling). |
| `tests/unit/test_http_client.py` | Removed 8 obsolete tests (cooldown lock + seller limiter integration). Added 6 new tests: pre-flight calls budget.reserve with the right prior; observe runs after both 200 and 429; unknown paths skip pre-flight; long-cooldown bail-out propagates; no-token-fp skips budget entirely; no-budget no-op. |
| `tests/unit/test_rate_limiter.py` | Removed `TestSharedRateLimiterFallback` env-var tests, `TestSellerLimiterFactory` (3 tests), `TestCooldownLockFactory`. Added `TestEndpointBudgetFactory` covering DB mode, memory opt-out, singleton. |

## Live verification (2026-04-26)

Single `wb --json --compact campaign list` against the production env:

```
$ wb --json --compact campaign list
[<campaigns returned>...]

$ sqlite3 ~/.wb-cli/rate_limits.db ...
endpoint_budget: 1 row
  tk=def07bba.. ep=/api/advert/v2/adverts sid=407bbe2b... remaining=0 ...

seller_cooldown (legacy F-13 table): 1 row, expired by ~31 h (R-2 ignores it)
```

Confirmed end-to-end:

- `_pre_flight` ran, bootstrap path executed (no prior row), HTTP succeeded.
- `_observe` populated the new `endpoint_budget` row from the response headers.
- The legacy `seller_cooldown` row from F-13 (still in the DB from yesterday's accident) was **not** consulted — exactly the isolation R-2 is meant to give us.
- No spurious `/adv/v1/balance` row, confirming R-2's gate doesn't probe other endpoints.

Bonus F-15 confirmation: even `/api/advert/v2/adverts` returned `remaining=0` for the Base token after one call — Base limits stratify across the whole advert API, not just balance. Tracked in [F-15 phase doc](F-15-rate-base-token-blindspot.md), addressed in R-5.

## Notes

- Net behaviour change: a 429 on any endpoint now blocks **only that endpoint** until WB's reset deadline. Previously the F-13 lock blocked the whole seller for up to 30 minutes.
- `SellerCooldownLock` and `SELLER_GLOBAL_BUDGET` are still **defined** in `rate_limiter.py` / `constants.py` but no longer wired into any code path. R-4 deletes them.
