# F-21 — `wb portal bids` (CPC/CPM bid recommendations from seller portal)

- **Version:** 0.40.0
- **Status:** ✅ DONE
- **Date:** 2026-05-23
- **Scope:** `src/wb/core/constants.py`, `src/wb/client/portal.py`, `src/wb/domain/models.py`, `src/wb/cli/portal.py`, new `docs/portal/` directory, tests
- **Plan file:** [now-plan-what-will-rustling-hare.md](../../../../Users/teocci/.claude/plans/now-plan-what-will-rustling-hare.md)

## Goal

Surface the seller portal's CPC/CPM bid-recommendation endpoints as a new CLI command, and create the first **empiric documentation** for the portal API family (separate from the official `dev-wb-adv.md` / `docs/swagger/` references).

## Why

The official WB Promotion API exposes bid recommendations **only for CPM** (`/api/advert/v0/bids/recommendations` — CPC payment returns HTTP 400). The portal UI at `cmp.wildberries.ru` actually serves a richer dataset:

- **CPC**: `GET /api/v1/advert/bids-cpc?nms=&bid_type=` — per-placement (search + recommendations) reach forecasts.
- **CPM**: `GET /api/v1/advert/bids?nms=&bid_type=&payment_type=cpm` — same reach-forecast shape, no placement split.

Each response includes a `min` floor plus three reach tiers (`reach_max` / `reach_medium` / `reach_min`), each with `{bid, min, budget, shows, clicks}` — information the official API does not expose at all (no reach forecast on the official endpoint).

CPC campaigns currently have **no bid-recommendation surface** in the CLI; agents must guess bids or copy them from the browser. F-21 plugs that gap.

## Scope

### CLI command (single command, both endpoints)

```
wb portal bids [--campaign CAMPAIGN_ID] [--nm NM_ID]...
               [--payment-type cpm|cpc] [--bid-type manual|unified]
```

- **NMs**: `--nm` (repeatable) takes precedence; else `--campaign` auto-discovers NMs from `/api/advert/v2/adverts`.
- **`--payment-type`**: auto-picked from the campaign's `settings.payment_type` when `--campaign` is given; required otherwise.
- **`--bid-type`**: defaults to `manual` (=1); maps `unified` → 2 per the new-typology convention.
- **Endpoint selection**: `cpc` → `EP_PORTAL_BIDS_CPC`; `cpm` → `EP_PORTAL_BIDS`.

### Empiric portal docs

New directory `docs/portal/` — **strictly separate** from `dev-wb-adv.md` / `docs/swagger/` (which document only official endpoints):

- `docs/portal/README.md` — overview, auth model, observation methodology, stability disclaimer, endpoint index.
- `docs/portal/endpoints/bids.md` — empiric reference for `/api/v1/advert/bids` (CPM).
- `docs/portal/endpoints/bids-cpc.md` — empiric reference for `/api/v1/advert/bids-cpc` (CPC, placement-split).
- `docs/portal/endpoints/auth-token.md` — backfill for the JRPC `auth/token` endpoint (already used by `PortalClient.authenticate`).
- `docs/portal/endpoints/tokens-jrpc.md` — backfill for the JRPC `generateToken` endpoint (already used by `PortalClient.generate_token`).
- `docs/portal/endpoints/table-list.md` — backfill for `tableListv6` (already used by `PortalClient.list_products`).

## Out of scope

- Mutation endpoints on the portal (this phase is read-only).
- Generalizing `PortalClient` into a service-layer module — portal flow already uses the lean CLI → client → domain pattern (see [src/wb/cli/portal.py:60](../../src/wb/cli/portal.py#L60)).
- Client-side rate limiting for `cmp.wildberries.ru` — portal endpoints already bypass the centralized limiter; no change unless 429s appear in production.
- `RATE_LIMITS.md` updates (portal endpoints are not listed there by design).

## Files to touch

### Code
- `src/wb/core/constants.py` — `WB_CMP_BASE_URL`, `EP_PORTAL_BIDS`, `EP_PORTAL_BIDS_CPC`.
- `src/wb/domain/models.py` — `ReachTier`, `PortalBidRecommendation` (with `from_portal()` factory).
- `src/wb/client/portal.py` — new `_get()` helper, new `fetch_bid_recommendations()` method.
- `src/wb/cli/portal.py` — new `bids` command following `products` pattern.
- (no service layer — mirror existing portal pattern.)

### Tests
- `tests/unit/test_portal_client.py` (new or extend) — `test_fetch_bid_recommendations_cpc_shape`, `test_fetch_bid_recommendations_cpm_shape`, `test_auth_error_on_401`.

### Docs
- `docs/portal/README.md` + 5 endpoint files (see Scope).
- `docs/PROGRESS.md`, `docs/IMPROVEMENTS.md`, this file.
- `CLAUDE.md` — add Known-Quirks row + Auth-Methods note.
- `CHANGELOG.md` (via `phase-complete`).

## Acceptance checks

1. `pytest tests/unit/ -v` — all pass.
2. Live end-to-end smoke against NM 183813043 (campaign 36384182, CPC). Response shape depends on `--bid-type`:
   - `wb portal bids -c 36384182` (manual, the campaign's mode) → 1 row with `placement='combined'`, `min_bid=181`.
   - `wb portal bids --nm 183813043 --payment-type cpc --bid-type unified` → 2 rows: `placement='search'` (`min_bid=181`, `reach_min.bid=1500`, `reach_min.clicks=30`) and `placement='recommendations'` (`min_bid=100`).
   - `wb portal bids --nm 183813043 --payment-type cpm --bid-type unified` → 2 rows with non-zero `reach_medium`/`reach_min` tiers (CPM has broader inventory signal).
3. `--json` output validates as a list of `PortalBidRecommendation` dicts.
4. Validation: missing inputs / invalid `--bid-type` / invalid `--payment-type` all exit 2 (`VALIDATION_ERROR`).
5. 401/403 from the portal raises `AuthenticationError` → exit code 3.
6. `dev-wb-adv.md` and `docs/swagger/` are unchanged in the F-21 diff (`git diff --name-only main HEAD` lists only `docs/portal/**`, `docs/PROGRESS.md`, `docs/IMPROVEMENTS.md`, `docs/phases/F-21-portal-bids.md`, plus the code files in Step 3).

## What shipped

- New CLI command **`wb portal bids`** ([src/wb/cli/portal.py](../../src/wb/cli/portal.py)) — single command surfaces both `cmp.wildberries.ru/api/v1/advert/bids` (CPM) and `/bids-cpc` (CPC). Inputs: `--campaign` (auto-discovers NMs + payment_type + bid_type from `/api/advert/v2/adverts`) and/or `--nm` (repeatable), with `--payment-type cpm|cpc` and `--bid-type manual|unified` overrides.
- New domain types ([src/wb/domain/models.py](../../src/wb/domain/models.py)) — `ReachTier`, `PortalBidRecommendation` (with `from_portal()`), and a shape-flexible `parse_portal_bids_response()` that surfaces whatever placement keys WB returns (so a future `cart` placement just flows through).
- First **GET** method on `PortalClient` ([src/wb/client/portal.py](../../src/wb/client/portal.py)) — `fetch_bid_recommendations(nm_ids, payment_type, bid_type)` + a `_get()` helper that mirrors `_post()`'s 401/403/4xx handling. `_build_headers()` now accepts an `origin=` override so cmp endpoints use a same-origin referer.
- New constants ([src/wb/core/constants.py](../../src/wb/core/constants.py)) — `WB_CMP_BASE_URL`, `EP_PORTAL_BIDS`, `EP_PORTAL_BIDS_CPC`.
- New empiric documentation tree ([docs/portal/](../portal/)) — README + 5 endpoint files (`bids.md`, `bids-cpc.md`, `auth-token.md`, `tokens-jrpc.md`, `table-list.md`). Strictly separate from `dev-wb-adv.md` / `docs/swagger/` per the rule that official and unofficial WB surfaces must not be intermingled.
- 18 new unit tests in [tests/unit/test_portal_client.py](../../tests/unit/test_portal_client.py) — covers both endpoint variants, all three response shapes (`combined`, `search`+`recommendations`, flat array), 401/auth handling, multi-NM batching, and the shape-flexible parser. All passing — full suite 1442/1443 (1 pre-existing env-test failure unchanged).
- CLAUDE.md ([Known WB API Quirks](../../CLAUDE.md) + [Auth Methods](../../CLAUDE.md)) — new quirks row for the cmp endpoints (`bid_type=1` → `{combined}`, `bid_type=2` → `{search,recommendations}`) and `wb portal bids` added to the portal-only command list.

## Key observation captured during implementation

The empiric docs were written ahead of the code (per the phase-registration-before-code rule) using a single live probe. The first probe used `bid_type=2` and returned `{recommendations, search}`; the user's pasted CPM sample was a flat array. Both initial assumptions turned out to be incomplete — running the CLI with the default `bid_type` (mapped from `manual` = 1) returned a `{combined: [...]}` shape on both CPC and CPM endpoints. The parser was rewritten to be shape-agnostic, and the empiric docs ([bids.md](../portal/endpoints/bids.md), [bids-cpc.md](../portal/endpoints/bids-cpc.md)) now document both the `combined` and the placement-split shapes with the observed `bid_type` → shape mapping.
