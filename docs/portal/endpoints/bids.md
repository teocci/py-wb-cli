# GET https://cmp.wildberries.ru/api/v1/advert/bids

- **Host:** `cmp.wildberries.ru`
- **Auth:** `authorizev3` header + browser `cookie` (see [../README.md](../README.md#auth-model))
- **Status:** undocumented
- **Date verified:** 2026-05-23
- **Used by:** `wb portal bids` (F-21) when `--payment-type cpm`

Returns suggested bids and reach forecasts for CPM campaigns. The response is a dict-of-lists keyed by placement, with the same shape rules as the [CPC sibling](bids-cpc.md) — `bid_type` drives whether you get a single `combined` bucket or a `search` + `recommendations` split.

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

The top-level shape depends on `bid_type` — same rules as [bids-cpc.md → Response shape](bids-cpc.md#response-shape):

### `bid_type=1` (manual)

```jsonc
{
  "combined": [
    {
      "id": 183813043,                  // NM ID echoed back
      "min": 12000,                     // absolute minimum bid in kopecks
      "reach_max":    { "bid": 0,     "min": 39000, "budget": 0,      "shows": 0,    "clicks": 0   },
      "reach_medium": { "bid": 21600, "min": 0,     "budget": 106600, "shows": 4944, "clicks": 115 },
      "reach_min":    { "bid": 20300, "min": 0,     "budget": 59000,  "shows": 2915, "clicks": 51  }
    }
  ]
}
```

### `bid_type=2` (unified)

```jsonc
{
  "recommendations": [
    { "id": 183813043, "min": 11800, "reach_max": {"...": "..."}, "reach_medium": {"...": "..."}, "reach_min": {"...": "..."} }
  ],
  "search": [
    { "id": 183813043, "min": 51000, "reach_max": {"...": "..."}, "reach_medium": {"...": "..."}, "reach_min": {"...": "..."} }
  ]
}
```

**Note on a flat-array variant.** An earlier observation (2026-05-23, same NM) reported a flat array `[{id, min, reach_…}]` at the top level rather than the dict shown above. Subsequent probes (same day, same credentials) consistently returned the dict form for both `bid_type` values. The CLI parser still accepts a flat list as a defensive fallback — see `parse_portal_bids_response()` in [src/wb/domain/models.py](../../../src/wb/domain/models.py). If a future probe confirms the flat shape under specific conditions, document those conditions here.

## Field semantics (observed)

Same per-record shape and units as [bids-cpc.md → Field semantics](bids-cpc.md#field-semantics-observed). Differences specific to the CPM endpoint:

- **`reach_max.min` non-zero in `combined`.** Observed `39000` — likely an absolute floor that says "you need a bid of at least 39000 kopecks (390 ₽) before WB will forecast the maximum-reach tier".
- **More populated tiers.** CPM responses for NM 183813043 have non-zero `reach_medium` and `reach_min` forecasts in both `combined` and unified-split shapes; the CPC variants for the same NM had data only on `search.reach_min`. CPM appears to draw on broader inventory signal.
- **Larger absolute values.** CPM bids are quoted in kopecks per thousand impressions; CPC bids are per click. Expect CPM `min` floors (~12000) to be roughly 50–100× CPC floors (~181) for the same product.

## Observed status codes

- **200 OK** — happy path.
- **401 / 403** — `authorizev3` or cookie expired/invalid.
- **400** — likely on malformed `nms`, unknown `bid_type`, or missing `payment_type`. Not yet probed.

## Open questions

1. **Behavior when `payment_type=cpc` is sent to this path.** Does it 400, redirect to `/bids-cpc`, or return CPC data in this shape? Worth a quick probe.
2. **`reach_*.min` semantics across both endpoints.** Why is it sometimes a floor (CPM `reach_max.min=39000`) and sometimes zero? Likely tier-eligibility threshold — confirm by varying input.
3. **Multi-NM batching.** Same open question as [bids-cpc.md](bids-cpc.md).
4. **Flat-array variant** (see [Response shape](#response-shape)) — under what conditions does the endpoint return a flat list instead of a dict-keyed-by-placement?

## See also

- [bids-cpc.md](bids-cpc.md) — the CPC sibling (placement-split response).
- [src/wb/client/portal.py](../../../src/wb/client/portal.py) — implementation.
- [F-21 phase doc](../../phases/F-21-portal-bids.md).
