# F-19 — Real implementation of `wb bid recommend / minimum / get-items`

- **Version:** 0.37.0
- **Status:** ✅ DONE
- **Scope:** `services/bids.py`, `client/promotion.py`, `domain/models.py`, `cli/bid.py`
- **Reported in:** `bugs/2026-05-22-bid-endpoint-http400-bug.md`

## Bug

All three read-only bid commands return HTTP 400 on any campaign:

```powershell
wb --json --compact bid recommend --campaign 36384182
wb --json --compact bid minimum   --campaign 36384182
wb --json --compact bid get-items --campaign 36384182
```

The original bug-report hypothesis (paused campaigns) is incorrect — the failure is not state-dependent.

## Root cause

The CLI's bid read path was never implemented against the actual WB endpoints. Verified against `docs/swagger/08-promotion.yaml` and `dev-wb-adv.md`:

| Command | Real endpoint shape | What CLI did | Result |
|---|---|---|---|
| `bid recommend` | `GET /api/advert/v0/bids/recommendations?nmId=N&advertId=X` (per-item; returns single `{advertId, nmId, base, normQueries}`; **CPM-only**) | `GET …?id=X` (single param, no per-item loop) | 400 every call |
| `bid minimum` | `POST /api/advert/v1/bids/min` body `{advert_id, nm_ids, payment_type, placement_types}` returns `{bids:[{nm_id, bids:[{type,value}]}]}` | Aliased to broken `get_recommended_bids` | 400 every call |
| `bid get-items` | (no dedicated endpoint — bids are inside `/api/advert/v2/adverts` at `nm_settings[].bids_kopecks.{search,recommendations}`) | Aliased to broken `get_recommended_bids` | 400 every call |

Even if the request had succeeded, `RecommendedBid.from_api` (models.py:748-761) reads `cpm`/`minCpm` fields that don't appear in the swagger response.

`EP_BID_MIN = '/api/advert/v1/bids/min'` (constants.py:267) was imported in promotion.py but never called — the minimum-bids endpoint was placeholdered and never wired up.

## Fix

### Endpoint mapping (final)

| CLI command | New behavior | Endpoint | Rate limit |
|---|---|---|---|
| `bid recommend --campaign X [--nm N]` | Default: loop over the campaign's NMs and call recommendations per item. With `--nm`: single call. Validates `payment_type == cpm`. | `GET /api/advert/v0/bids/recommendations?nmId=&advertId=` | Personal: 5/min; Base: 20/h |
| `bid minimum --campaign X` | Reads nm_ids + payment_type from campaign info, batches up to 100 NMs per call to /bids/min. | `POST /api/advert/v1/bids/min` | Personal: 20/min; Base: 5/h |
| `bid get-items --campaign X` | Zero extra API calls — reads `nm_settings[].bids_kopecks` from campaign info. | (reuses `/api/advert/v2/adverts`) | n/a |

### Domain models

Replace flat misnamed `RecommendedBid` with three precise dataclasses (all `slots=True`):

- `RecommendedBid(campaign_id, nm_id, competitive, leaders, top2, error)` — from /v0/bids/recommendations.
- `MinimumBid(campaign_id, nm_id, combined, search, recommendation)` — from /v1/bids/min.
- `CurrentBid(campaign_id, nm_id, search, recommendations)` — from campaign info nm_settings.

### Loop-over-NMs design for `bid recommend`

- Read campaign info once via `PromotionClient.get_campaign`.
- Reject terminal-state campaigns (`DELETED/ARCHIVED/DECLINED`) with `ValidationError`.
- Reject non-CPM campaigns with `ValidationError` (the endpoint is CPM-only per swagger:1807).
- Iterate `nm_settings[].nm_id`, calling recommendations per item.
- On per-NM 400/4xx, log a warning and append a `RecommendedBid` with zeros + `error` field. Loop does not abort.
- Existing `EndpointBudget` throttles transparently — no manual sleeps needed.

## Files touched

### Code

- `src/wb/client/promotion.py` — drop old broken `get_recommended_bids`; add `get_recommended_bid` (singular, with `nmId`/`advertId`) + `get_minimum_bids` (POST).
- `src/wb/services/bids.py` — rewrite all three read methods. Drop the alias chain.
- `src/wb/domain/models.py` — rewrite `RecommendedBid`; add `MinimumBid`, `CurrentBid`.
- `src/wb/cli/bid.py` — add `--nm` to `bid_recommend`; update headers/rows for new fields.
- `src/wb/sdk.py` — sweep for any bid exports; update surface to match.

### Tests

- `tests/unit/test_promotion_client.py` — update `test_get_recommended_bids` → `test_get_recommended_bid_*`; add `test_get_minimum_bids_post_body_shape`.
- `tests/unit/test_bid_service.py` — rewrite with swagger-shaped fixtures; add CPM-validation, `--nm`, partial-failure-loop, and batching tests.
- `tests/unit/test_cli_bid.py` — update JSON assertions to new field names; add `--nm` test; add non-CPM `VALIDATION_ERROR` test.
- `tests/unit/test_bid_models.py` *(new)* — from_api / from_nm_setting parsers.

### Docs

- `docs/FIXES.md`, `docs/PROGRESS.md`, this file, `CLAUDE.md` Known-Quirks table, `CHANGELOG.md`.
- `bugs/2026-05-22-bid-endpoint-http400-bug.md` — flip Status to `fixed in 0.37.0`, link to this fix.

## Verification

1. `pytest tests/unit/ -v` — all pass.
2. End-to-end against a real CPM campaign (once rate-limit cooldown clears):
   - `wb --json bid get-items --campaign <id>` → search/recommendations per NM
   - `wb --json bid minimum   --campaign <id>` → combined/search/recommendation per NM
   - `wb --json bid recommend --campaign <id>` → competitive/leaders/top2 per NM (loops)
   - `wb --json bid recommend --campaign <id> --nm <nm>` → single row
3. Non-CPM campaign: `wb --json bid recommend --campaign <cpc-id>` → `VALIDATION_ERROR` JSON.
4. Original repro: `wb --json --compact bid recommend --campaign 36384182` no longer surfaces `API_ERROR HTTP 400`.
