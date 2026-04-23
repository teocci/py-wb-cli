# Fix F-2 — API Migration (v0.3.2)

**Date:** 2026-04-02 | **Tests:** 366 passed

## Problem

Live testing revealed **10 of 12 endpoint paths** return HTTP 404. WB migrated their Promotion API without deprecation notice. Only `/ping` and `/adv/v1/budget` survived.

## What Was Fixed

- All 14 dead `EP_*` constants replaced with current paths from `dev-wb-adv.md`
- 8 new normquery constants added: `EP_NQ_LIST`, `EP_NQ_GET_BIDS`, `EP_NQ_SET_BIDS`, `EP_NQ_DEL_BIDS`, `EP_NQ_GET_MINUS`, `EP_NQ_SET_MINUS`, `EP_NQ_STATS`, `EP_NQ_STATS_DAILY`
- `Campaign`, `AccountBalance`, `BudgetSnapshot`, `CampaignStats`, `SearchCluster`, `ClusterStats` — all `from_api()` rewritten
- `CampaignCreate`, `BidMutation`, `PlacementConfig` — `to_api()` rewritten
- `MinusPhraseSet` — added `from_api()` and `to_api()`
- HTTP client: added `put()` and `patch()` methods
- `PromotionClient`: all methods rewritten for new endpoints/methods/payloads
- `ClusterService`: complete rewrite for normquery API (requires `--nm` parameter)
- `CampaignStatus`: added `DELETED(-1)`, `DECLINED(8)`; `CampaignType`: added `STANDARD(9)`

## Endpoint Migration Summary

| Old Path | New Path |
|----------|----------|
| `GET /adv/v1/promotion/adverts` | split: `/adv/v1/promotion/count` + `/api/advert/v2/adverts` |
| `GET /adv/v2/fullstats` | `GET /adv/v3/fullstats` |
| `GET /adv/v1/promotion/subjects` | `GET /adv/v1/supplier/subjects` |
| `POST /adv/v1/promotion/nms` | `POST /adv/v2/supplier/nms` |
| `GET /adv/v2/promotion/recommended_cpm` | `GET /api/advert/v0/bids/recommendations` |
| `GET /adv/v1/account/balance` | `GET /adv/v1/balance` |
| `POST /adv/v1/promotion/adverts` (create) | `POST /adv/v2/seacat/save-ad` |
| `POST /adv/v1/rename` | `POST /adv/v0/rename` |
| `GET /adv/v1/cpm` | `PATCH /api/advert/v1/bids` |
| `GET /adv/v1/auto/active-words` | removed → normquery |
| `GET /adv/v1/auto/words` | removed → normquery |
| `GET /adv/v2/auto/stat-words` | removed → normquery |

## Write Endpoint Verification (campaign 35495276)

| Endpoint | Method | Result |
|----------|--------|--------|
| `/adv/v2/seacat/save-ad` | POST | 200 — created |
| `/adv/v0/start` | GET | 400 — expected (no budget) |
| `/adv/v0/pause` | GET | 400 — expected (not active) |
| `/adv/v0/rename` | POST | 200 — renamed |
| `/adv/v0/stop` | GET | 400 — expected (not active) |
| `/adv/v0/delete` | GET | 200 — deleted |
