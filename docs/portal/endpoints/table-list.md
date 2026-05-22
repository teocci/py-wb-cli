# POST https://seller-content.wildberries.ru/ns/viewer/content-card/viewer/tableListv6

- **Host:** `seller-content.wildberries.ru`
- **Auth:** `authorizev3` header + browser `cookie` (see [../README.md](../README.md#auth-model))
- **Status:** undocumented
- **Date verified:** 2026-05-23 (backfilled — endpoint has been in use since F-1)
- **Used by:** [`PortalClient.list_products()`](../../../src/wb/client/portal.py#L123) — surfaces as `wb portal products`.

Returns paginated product cards from the seller's catalog. The portal UI uses this same endpoint to render the "Products" table — hence the `tableListv6` path suffix. Provides fields the official API does not expose (notably feedback counts, card-rating, and tag metadata).

## Request body

```jsonc
{
  "sort":   [{ "columnID": 11, "order": "desc" }],   // 11 = "last updated", desc = newest first
  "filter": { "search": "<query>", "paidOptions": {} },
  "cursor": { "n": 20 }                               // page size; portal default in CLI is 20
}
```

- `sort` — single-element array selecting the sort column and direction. `columnID: 11` is the "updateAt" column the CLI defaults to. Other column IDs exist but are not yet mapped here.
- `filter.search` — free-text search. Empty string returns all cards (up to `cursor.n`).
- `filter.paidOptions` — observed empty in CLI traffic; the portal UI uses it to filter by paid services on a card.
- `cursor.n` — page size. The endpoint also supports cursor-based pagination via an `updated` / `nmID` cursor object, but the CLI does not yet use it.

## Headers

Same as the shared portal pattern. `content-type: application/json` is required.

## Request example (curl)

```bash
curl -X POST 'https://seller-content.wildberries.ru/ns/viewer/content-card/viewer/tableListv6' \
  -H 'authorizev3: <portal JWT>' \
  -H 'cookie: <portal cookie>' \
  -H 'content-type: application/json' \
  -H 'origin: https://seller.wildberries.ru' \
  -H 'referer: https://seller.wildberries.ru/' \
  --data '{"sort":[{"columnID":11,"order":"desc"}],"filter":{"search":"","paidOptions":{}},"cursor":{"n":20}}'
```

## Response shape

The CLI reads only `data.cards`; other top-level keys (cursor, paging totals) exist but are not consumed today.

```jsonc
{
  "data": {
    "cards": [
      {
        "nmID":       123456789,
        "imtID":      987654321,
        "vendorCode": "SELLER-SKU-001",
        "title":      "Product title",
        "brand":      "Brand",
        "subject":    "Category name",
        "stocks":     42,
        "sizes": [
          { "currentPrice": 199900, "...": "..." }     // currentPrice in kopecks; CLI reads sizes[0]
        ],
        "feedbacks":  { "rating": 4.8, "count": 1234 },
        "meta":       { "ratingData": { "rating": 9.2 } },  // card quality rating (0-10)
        "tags":       [{ "id": 1, "name": "Hit", "color": "#ff0000" }],
        "updateAt":   "2026-05-22T12:34:56Z"
      }
    ]
  }
}
```

## Field semantics (observed)

These are the subset the CLI consumes via [`PortalProductCard.from_portal()`](../../../src/wb/domain/models.py#L894):

| Field path | Mapped to | Notes |
|---|---|---|
| `nmID` | `nm_id` | WB article number. |
| `imtID` | `imt_id` | Internal model type ID — groups variants under a single "model". |
| `vendorCode` | `vendor_code` | Seller-defined SKU string. |
| `title` | `title` | Product title. |
| `brand` | `brand` | Brand name. |
| `subject` | `subject` | Product category/subject. |
| `stocks` | `stocks` | Total stock across all warehouses. |
| `sizes[0].currentPrice` | `price` | First size's current price. **In kopecks** despite the field name suggesting RUB — verify before displaying. |
| `feedbacks.rating` | `feedback_rating` | Star rating average (0–5). |
| `feedbacks.count` | `feedback_count` | Number of customer reviews. |
| `meta.ratingData.rating` | `card_rating` | Card quality rating (0–10) — WB's internal listing-quality score. |
| `tags` | `tags` | Raw tag dicts. |
| `updateAt` | `updated_at` | ISO timestamp, last edit to the card. |

## Observed status codes

- **200 OK** — happy path. `data.cards` may be empty when search yields no matches.
- **401 / 403** — `authorizev3` or cookie expired.
- **5xx** — observed under heavy seller-portal load; not retried by the CLI today (portal calls bypass the centralized retry/limiter).

## Open questions

1. **Other `columnID` values.** Beyond `11` (updateAt). What does the UI use for sort-by-price, sort-by-stock?
2. **Cursor pagination.** The CLI only requests page 1 (`cursor.n: 20`). The portal UI clearly paginates further — the response includes cursor metadata that's not yet consumed.
3. **`sizes[0].currentPrice` units.** Field naming suggests RUB but observed values look like kopecks. Confirm with a high-priced item.

## See also

- [src/wb/client/portal.py:123](../../../src/wb/client/portal.py#L123) — `list_products()` implementation.
- [src/wb/domain/models.py:860](../../../src/wb/domain/models.py#L860) — `PortalProductCard` model.
- [src/wb/cli/portal.py:31](../../../src/wb/cli/portal.py#L31) — `wb portal products` command.
