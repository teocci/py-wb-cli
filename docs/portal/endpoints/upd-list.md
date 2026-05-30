# GET https://cmp.wildberries.ru/api/v6/upd

- **Host:** `cmp.wildberries.ru`
- **Auth:** `authorizev3` header + browser `cookie` (see [../README.md](../README.md#auth-model))
- **Status:** undocumented
- **Date verified:** 2026-05-31
- **Used by:** `wb portal campaign finance` (I-24)

Returns one page of the campaign **expense ledger** ("История затрат") visible at
`https://cmp.wildberries.ru/campaigns/finances`. One row = one ad-spend deduction
(campaign × charge date × payment source). The same data is also exposed in xlsx
form via the [sibling endpoint](upd-xlsx.md); the JSON variant here is paginated
while the xlsx returns the full range in one call.

## Query params

| Name | Required | Example | Meaning |
|---|---|---|---|
| `from` | yes | `2026-05-11T00:00:00+03:00` | Range start as ISO-8601 with **MSK offset (+03:00)**. WB seller portal works in Europe/Moscow year-round. |
| `to` | yes | `2026-05-11T00:00:00+03:00` | Range end. Pass start-of-day; WB treats it as **inclusive end-of-day** (a single-day query uses identical `from` and `to`). |
| `page_number` | yes | `1` | 1-indexed page number. |
| `page_size` | yes | `100` | Rows per page. Browser default is `10`; the CLI uses `100` to keep the auto-paginate loop short. No hard ceiling observed. |
| `bid_type` | yes | `[0]` | Literal `[0]` (URL-encoded `%5B0%5D`) returns all bid types. **Semantics inside response rows are opposite to F-21's `_BID_TYPE_INT`** — see [Field semantics](#field-semantics-observed). |
| `attribute` | yes | `all` | UI's catch-all filter; "all campaigns". Other values not yet probed. |

## Headers

Same auth pair as the [bids endpoint](bids.md#headers): `authorizev3` + `cookie`. The cmp host **does** accept `authorizev3` (unlike the Jam downloads CDN — see [file-manager-file.md](file-manager-file.md)). The browser sends `referer: https://cmp.wildberries.ru/campaigns/finances?from=YYYY-MM-DD&to=YYYY-MM-DD` and `origin: https://cmp.wildberries.ru`; the CLI replays the same pattern.

## Request example (curl)

```bash
curl 'https://cmp.wildberries.ru/api/v6/upd?page_number=1&page_size=100&bid_type=%5B0%5D&attribute=all&from=2026-05-11T00:00:00%2B03:00&to=2026-05-11T00:00:00%2B03:00' \
  -H 'authorizev3: <portal JWT>' \
  -H 'cookie: <portal cookie>' \
  -H 'accept: application/json' \
  -H 'origin: https://cmp.wildberries.ru' \
  -H 'referer: https://cmp.wildberries.ru/campaigns/finances?from=2026-05-11&to=2026-05-11'
```

## Response shape

```jsonc
{
  "upd_total_amount": 193925,          // sum of ALL rows in the date range (not just this page), in rubles
  "total_count": 159,                  // total rows in the date range (not just this page)
  "upd_info": [
    {
      "upd_num": 297930536,            // document number; 0 = not yet assigned
      "upd_time": "2026-05-11T23:59:59+03:00",   // charge timestamp (ISO+MSK)
      "upd_sum": 43,                   // rubles
      "advert_id": 30853961,           // campaign ID
      "camp_name": "WB 183813948 | Руч",
      "bid_type": 2,                   // 1 = unified / 2 = manual — see Field semantics
      "advert_type": "",
      "payment_type": "Баланс",        // 'Баланс' (balance) or 'Промо бонусы' (promo)
      "payment_type_id": 1,
      "advert_status": "11",
      "category_uid": "66666666-6666-6666-6666-666666666666",
      "time": "2026-03-15T00:06:24.697539Z",     // when the charge was booked
      "payment_model": "cpm",          // 'cpm' or 'cpc'
      "source_service_id": 2,
      "is_autorefill": false
    }
  ]
}
```

Both `upd_total_amount` and `total_count` are **range-wide**, not page-scoped — they stay constant as you walk pages.

## Field semantics (observed)

- **`upd_sum`** — rubles (not kopecks). Confirmed by summing all 159 rows for 2026-05-11 (`193,925 ₽`) against the top-level `upd_total_amount` (`193,925`). Exact match.
- **`bid_type`** — **inverted vs. F-21.** Empirical mapping (cross-checked against the xlsx column "Раздел" for the same rows):
  - `bid_type=1` → "Единая Ставка" (Unified Rate)
  - `bid_type=2` → "Ручная Ставка" (Manual Rate)

  This is the **opposite** of the `_BID_TYPE_INT` map in [src/wb/cli/portal.py](../../../src/wb/cli/portal.py) (set by F-21 for the bid-recommendations endpoint, which says `1=manual, 2=unified`). The two endpoints disagree; the CLI's `CampaignFinanceEntry` therefore stores `bid_type` as a raw `int` so callers can map themselves until F-21 is reconciled.
- **`payment_type` / `payment_type_id`** — Russian payment-source label and its numeric code. Two values observed for 2026-05-11: `Баланс` / `1` (ad-deposit balance) and `Промо бонусы` (promo bonuses; numeric ID not yet captured).
- **`payment_model`** — `cpm` or `cpc`; matches the campaign's billing model.
- **`advert_status`** — string-encoded WB status code at charge time (`"9"`, `"11"`). Not a stable enum; treat as opaque.
- **`time` vs `upd_time`** — `upd_time` is the calendar charge timestamp (always 23:59:59 of the charge day in MSK); `time` is when WB **booked** the charge (microsecond UTC). Multi-day campaigns show `time` weeks earlier than `upd_time`.
- **`category_uid`** — the all-sixes sentinel (`66666666-…`) appears for every row observed; meaning unclear, likely "uncategorized".

## Pagination behavior

- `page_number` is 1-indexed.
- The response always carries the full-range `total_count` regardless of page, so you can compute the stopping condition without walking blind.
- An empty `upd_info` list signals end-of-stream; walking past the last populated page does not error.
- Observed for 2026-05-11 / `page_size=100`: page 1 returned 100 rows, page 2 returned 59 (= `total_count`); page 3 would have returned an empty list.

## Observed status codes

- **200 OK** — happy path.
- **401 / 403** — `authorizev3` or cookie expired/invalid.

## Open questions

1. **Single-row campaigns appearing multiple times.** 122 unique `advert_id` across 159 rows for 2026-05-11 — WB charges the same campaign from multiple sources/bid types on the same day. Whether `upd_num` uniquely identifies the deduction (i.e. can be used as a primary key) is not yet confirmed.
2. **`attribute` other than `all`.** UI exposes filters; specific values not probed.
3. **`source_service_id` enum.** Values 1, 2, 3 observed; mapping not yet decoded.
4. **Maximum `page_size`.** Not probed; 100 works, 10 is the UI default.

## See also

- [upd-xlsx.md](upd-xlsx.md) — sibling xlsx download (same data, full range in one call).
- [src/wb/client/portal.py](../../../src/wb/client/portal.py) — `PortalClient.list_campaign_finance()`.
- [src/wb/services/portal_campaign_finance.py](../../../src/wb/services/portal_campaign_finance.py) — service-layer auto-pagination.
- [I-24 phase doc](../../phases/I-24-portal-campaign-finance.md).
- [reverse/download-campaign-finance-reports-process.md](../../../reverse/download-campaign-finance-reports-process.md) — original captured trace.
