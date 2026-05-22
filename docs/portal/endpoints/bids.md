# GET https://cmp.wildberries.ru/api/v1/advert/bids

- **Host:** `cmp.wildberries.ru`
- **Auth:** `authorizev3` header + browser `cookie` (see [../README.md](../README.md#auth-model))
- **Status:** undocumented
- **Date verified:** 2026-05-23
- **Used by:** `wb portal bids` (F-21) when `--payment-type cpm`

Returns suggested bids and reach forecasts for CPM campaigns. **No placement split** — CPM bids are not placement-scoped, so the response is a flat array of per-NM records.

## Query params

| Name | Required | Example | Meaning |
|---|---|---|---|
| `nms` | yes | `183813043` | NM ID. Almost certainly accepts a comma-separated list (matches the browser pattern); not yet verified with ≥2 NMs in a single call. |
| `bid_type` | yes | `1` | New-typology bid mode: `1` = manual, `2` = unified. |
| `payment_type` | yes | `cpm` | Must be `cpm`. Without this param the endpoint likely 400s — and at any rate the CPC variant lives at the [`/bids-cpc`](bids-cpc.md) sibling. |

## Headers

Same as [bids-cpc.md → Headers](bids-cpc.md#headers).

## Request example (curl)

```bash
curl 'https://cmp.wildberries.ru/api/v1/advert/bids?nms=183813043&bid_type=1&payment_type=cpm' \
  -H 'authorizev3: <portal JWT>' \
  -H 'cookie: <portal cookie>' \
  -H 'accept: application/json' \
  -H 'referer: https://cmp.wildberries.ru/campaigns/edit/<campaign_id>'
```

## Response shape

```jsonc
[
  {
    "id": 183813043,                  // NM ID echoed back
    "min": 12000,                     // absolute minimum bid in kopecks
    "reach_max":    { "bid": 0,     "min": 39000, "budget": 0,      "shows": 0,    "clicks": 0   },
    "reach_medium": { "bid": 21600, "min": 0,     "budget": 106600, "shows": 4944, "clicks": 115 },
    "reach_min":    { "bid": 20300, "min": 0,     "budget": 59000,  "shows": 2915, "clicks": 51  }
  }
]
```

The top-level value is a flat array — one element per requested NM. There is no per-placement key (contrast [bids-cpc.md](bids-cpc.md), which splits `search` vs `recommendations`).

## Field semantics (observed)

Same per-record shape and units as [bids-cpc.md → Field semantics](bids-cpc.md#field-semantics-observed). Differences specific to the CPM endpoint:

- **No placement scope.** A single record per NM, not two. CPM bids on this campaign type apply across all placements that WB selects automatically.
- **`reach_max.min` may be non-zero.** Observed `39000` in the live sample — likely a floor that says "you need a bid of at least 39000 kopecks (390 ₽) before WB will even forecast the maximum-reach tier". (In the CPC response this field has been all zeros so far.)
- **More populated tiers in real data.** The observed CPM call had `reach_medium` and `reach_min` both populated with non-zero forecasts; CPC for the same NM only populated `reach_min`. Suggests CPM has broader inventory signal than CPC for this NM/account.

## Observed status codes

- **200 OK** — happy path.
- **401 / 403** — `authorizev3` or cookie expired/invalid.
- **400** — likely on malformed `nms`, unknown `bid_type`, or missing `payment_type`. Not yet probed.

## Open questions

1. **Behavior when `payment_type=cpc` is sent to this path.** Does it 400, redirect to `/bids-cpc`, or return CPC data in CPM-flat shape? Worth a quick probe.
2. **`reach_*.min` semantics across both endpoints.** Why is it sometimes a floor (CPM `reach_max.min=39000`) and sometimes zero? Likely tier-eligibility threshold — confirm by varying input.
3. **Multi-NM batching.** Same open question as [bids-cpc.md](bids-cpc.md).

## See also

- [bids-cpc.md](bids-cpc.md) — the CPC sibling (placement-split response).
- [src/wb/client/portal.py](../../../src/wb/client/portal.py) — implementation.
- [F-21 phase doc](../../phases/F-21-portal-bids.md).
