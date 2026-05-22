# GET https://cmp.wildberries.ru/api/v1/advert/bids-cpc

- **Host:** `cmp.wildberries.ru`
- **Auth:** `authorizev3` header + browser `cookie` (see [../README.md](../README.md#auth-model))
- **Status:** undocumented
- **Date verified:** 2026-05-23
- **Used by:** `wb portal bids` (F-21) when `--payment-type cpc`

Returns suggested bids and **per-placement reach forecasts** for CPC campaigns. Each NM is reported twice — once for the **search** placement, once for the **recommendations** placement — with up to three reach tiers each.

## Query params

| Name | Required | Example | Meaning |
|---|---|---|---|
| `nms` | yes | `183813043` | NM ID. Almost certainly accepts a comma-separated list (mirrors what the browser sends for multi-product campaigns); not yet verified with ≥2 NMs in a single call. |
| `bid_type` | yes | `2` | New-typology bid mode: `1` = manual, `2` = unified. **Drives the response shape** — see below. |

`payment_type` is **not** a query param here — CPC is implied by the `-cpc` suffix in the path. (Contrast with the sibling [bids.md](bids.md) endpoint, which requires `payment_type=cpm`.)

## Headers

Minimum set that worked in the live probe ([d:/tmp/probe_bids_cpc.py](d:/tmp/probe_bids_cpc.py)):

```
authorizev3: <portal JWT>
cookie:      <full cookie string, including X-Current-Advertiser-ID=…>
accept:      application/json, text/plain, */*
referer:     https://cmp.wildberries.ru/campaigns/edit/<campaign_id>
origin:      https://cmp.wildberries.ru
user-agent:  Mozilla/5.0 (…) Chrome/148.0.0.0 …
```

`sec-fetch-*` headers and `accept-language` are accepted but not required for a 200.

## Request example (curl)

```bash
curl 'https://cmp.wildberries.ru/api/v1/advert/bids-cpc?nms=183813043&bid_type=2' \
  -H 'authorizev3: <portal JWT>' \
  -H 'cookie: <portal cookie>' \
  -H 'accept: application/json' \
  -H 'referer: https://cmp.wildberries.ru/campaigns/edit/36384182'
```

## Response shape

The top-level shape depends on `bid_type`:

### `bid_type=1` (manual)

```jsonc
{
  "combined": [
    {
      "id": 183813043,                  // NM ID echoed back
      "min": 181,                       // absolute minimum bid (kopecks)
      "reach_max":    { "bid": 0, "min": 0, "budget": 0, "shows": 0, "clicks": 0 },
      "reach_medium": { "bid": 0, "min": 0, "budget": 0, "shows": 0, "clicks": 0 },
      "reach_min":    { "bid": 0, "min": 0, "budget": 0, "shows": 0, "clicks": 0 }
    }
  ]
}
```

Single `combined` bucket — manual bidding applies one bid to whichever placement WB picks, so the forecast is not split.

### `bid_type=2` (unified)

```jsonc
{
  "recommendations": [
    {
      "id": 183813043,
      "min": 100,
      "reach_max":    { "bid": 0, "min": 0, "budget": 0, "shows": 0, "clicks": 0 },
      "reach_medium": { "bid": 0, "min": 0, "budget": 0, "shows": 0, "clicks": 0 },
      "reach_min":    { "bid": 0, "min": 0, "budget": 0, "shows": 0, "clicks": 0 }
    }
  ],
  "search": [
    {
      "id": 183813043,
      "min": 181,
      "reach_max":    { "bid": 0,    "min": 0, "budget": 0,      "shows": 0, "clicks": 0 },
      "reach_medium": { "bid": 0,    "min": 0, "budget": 0,      "shows": 0, "clicks": 0 },
      "reach_min":    { "bid": 1500, "min": 0, "budget": 315000, "shows": 0, "clicks": 30 }
    }
  ]
}
```

Two buckets, one per placement:

- `recommendations` — recommendation-carousel slots.
- `search` — search-results slots.

Each value is an array of per-NM records (one entry per requested NM). The per-entry shape is identical across all placements.

**The CLI parser is shape-flexible**: it surfaces whatever top-level keys WB returns as the `placement` field on `PortalBidRecommendation`. A future `cart` (or similar) placement would flow through without code changes.

## Field semantics (observed)

| Field | Unit | Meaning |
|---|---|---|
| `id` | int | NM ID (echo of the queried `nms` value). |
| `min` | kopecks | Hard floor for any bid on this placement. Bids below this are rejected by the campaign-update API. Observed values: `100` for the recommendations placement, `181` for search on the same NM — floor is placement-specific. |
| `reach_max` / `reach_medium` / `reach_min` | obj | Three reach tiers. `reach_max` = "show to the broadest audience"; `reach_min` = "show to the smallest, cheapest audience". `reach_medium` sits between. |
| `reach_*.bid` | kopecks | The bid WB suggests to hit this tier. `0` means WB has no forecast at this tier (typically when the NM has no historical impressions there). |
| `reach_*.min` | kopecks | A per-tier floor (likely an inferior bid that still yields traffic at that tier). Mostly `0` in observed samples — semantics not fully nailed. |
| `reach_*.budget` | kopecks | Projected daily budget required to sustain that bid/tier. |
| `reach_*.shows` | int | Projected daily impressions at that bid/tier. |
| `reach_*.clicks` | int | Projected daily clicks at that bid/tier. |

A tier object full of zeros (`{bid:0, min:0, budget:0, shows:0, clicks:0}`) means **no forecast available** for that tier — usually because the NM has insufficient historical signal at that placement. Treat as "tier inactive" rather than "tier exists at cost zero".

For the campaign in our smoke test (CPC, NM 183813043), only `search.reach_min` was populated — WB has data for the lowest-reach tier on search but not for the recommendations placement at all.

## Observed status codes

- **200 OK** — happy path.
- **401 / 403** — `authorizev3` or cookie expired/invalid. The portal's `wbx-validation-key` cookie expires faster than the JWT itself; refresh both from a fresh browser session.
- **400** — not observed in probes, but likely on malformed `nms` (non-numeric) or unknown `bid_type`.

## Open questions

1. **Multi-NM in a single call.** The browser likely sends comma-separated `nms` for multi-product campaigns. Probe with `nms=A,B` and verify both records come back.
2. **`reach_*.min`.** Mostly `0` in observed samples — possibly a per-tier floor that only differs from the top-level `min` when WB has a tier-specific override. Worth probing on a high-traffic NM.
3. **`combined.min` reflects which placement?** When `bid_type=1` returns a single `combined` record, its `min` matches the `search.min` from the `bid_type=2` response (both `181` in observed samples). Whether that's coincidence or `combined` always tracks `search` is not yet confirmed.

## See also

- [bids.md](bids.md) — the CPM sibling (flat array, no placement split).
- [src/wb/client/portal.py](../../../src/wb/client/portal.py) — implementation.
- [F-21 phase doc](../../phases/F-21-portal-bids.md).
