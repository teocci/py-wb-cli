# GET https://cmp.wildberries.ru/api/v5/updxlsx

- **Host:** `cmp.wildberries.ru`
- **Auth:** `authorizev3` header + browser `cookie` (see [../README.md](../README.md#auth-model))
- **Status:** undocumented
- **Date verified:** 2026-05-31
- **Used by:** `wb portal campaign finance-xlsx` (I-24)

Synchronous binary download of the campaign **expense ledger** ("История затрат") as an Excel workbook. Same data as the [JSON sibling](upd-list.md), one row per ad-spend deduction; **always returns every row for the requested date range in one call** regardless of the `pageSize` parameter (it's a vestigial leftover from the UI's paginated state).

## Query params

| Name | Required | Example | Meaning |
|---|---|---|---|
| `from` | yes | `2026-05-11T00:00:00+03:00` | Range start as ISO-8601 with **MSK offset (+03:00)**. |
| `to` | yes | `2026-05-11T00:00:00+03:00` | Range end. Pass start-of-day; WB treats it as inclusive end-of-day. |
| `bid_type` | yes | `[0]` | Literal `[0]` (URL-encoded `%5B0%5D`) = all bid types. |
| `pageNumber` | yes (vestigial) | `1` | **Note: camelCase**, unlike the snake_case `page_number` on the JSON sibling. Has no effect on the returned workbook (always full range). |
| `pageSize` | yes (vestigial) | `10` | Also has no effect on the returned workbook. Match the UI value (`10`) to stay close to the captured trace. |

The `pageNumber` / `pageSize` params look paginated but are inert — the response is always the complete ledger for `[from, to]`. WB likely accepts them only because the UI shares form state with the [paginated JSON endpoint](upd-list.md).

## Headers

Same auth pair as [upd-list.md → Headers](upd-list.md#headers): `authorizev3` + `cookie`. The cmp host accepts `authorizev3` for the binary download too (unlike the [Jam downloads CDN](file-manager-file.md), which rejects it). No `x-download-token` is needed.

## Request example (curl)

```bash
curl -OJ 'https://cmp.wildberries.ru/api/v5/updxlsx?bid_type=%5B0%5D&from=2026-05-11T00:00:00%2B03:00&to=2026-05-11T00:00:00%2B03:00&pageNumber=1&pageSize=10' \
  -H 'authorizev3: <portal JWT>' \
  -H 'cookie: <portal cookie>' \
  -H 'accept: application/json, text/plain, */*' \
  -H 'origin: https://cmp.wildberries.ru' \
  -H 'referer: https://cmp.wildberries.ru/campaigns/finances?from=2026-05-11&to=2026-05-11'
```

## Response

- **`Content-Type: application/octet-stream`**
- **`Content-Transfer-Encoding: binary`**
- **`Content-Disposition: attachment; filename=wildberries_<mojibake>_ID-<seller>_<from>-<to>.xlsx`** — the filename portion is UTF-8 bytes re-interpreted as Latin-1 (mojibake), original meaning "wildberries_история_затрат_ID-…". The CLI ignores this header and mints its own clean kebab-case name (`campaign-finance_<from>[_<to>].xlsx`).
- **Body** — standard `.xlsx` zip archive.

## Workbook shape

Single sheet, 7 columns. Row 1 = headers (Russian), rows 2..N = data. Row count = `total_count + 1` where `total_count` is the value returned by the [JSON sibling](upd-list.md#response-shape) for the same date range.

| Col | Header (Russian) | Maps to JSON field | Example |
|---|---|---|---|
| A | `ID кампании` | `advert_id` | `35916291` |
| B | `Кампания` | `camp_name` | `WB 265811162 \| Ед` |
| C | `Раздел` | derived from `bid_type` | `Единая Ставка` (= `bid_type=1`) / `Ручная Ставка` (= `bid_type=2`) |
| D | `Дата списания` | `upd_time` truncated to minutes | `2026-05-29 23:59` |
| E | `Источник списания` | `payment_type` | `Баланс` |
| F | `Сумма` | `upd_sum` | `186` (rubles) |
| G | `Номер документа` | `upd_num` | `0` (no document) / `297930536` |

The xlsx flattens the JSON's richer fields (`payment_type_id`, `payment_model`, `advert_status`, `category_uid`, `time`, `source_service_id`, `is_autorefill`) — agents that need those should use the [JSON endpoint](upd-list.md) instead.

## Observed status codes

- **200 OK** — happy path; body is the xlsx.
- **401 / 403** — `authorizev3` or cookie expired/invalid.

## Open questions

1. **Behaviour with `bid_type` other than `[0]`.** Not yet probed — the UI exposes per-bid-type toggles but the captured trace uses `[0]` exclusively.
2. **Maximum date range.** Single day works (159 rows / 13 KB). Multi-month ranges not stress-tested.
3. **Whether `Content-Disposition` ever returns a properly-encoded filename** (RFC 5987 `filename*=UTF-8''…`). Current observation only shows the mojibake form.

## See also

- [upd-list.md](upd-list.md) — sibling JSON endpoint (paginated; richer per-row fields).
- [src/wb/client/portal.py](../../../src/wb/client/portal.py) — `PortalClient.download_campaign_finance_xlsx()`.
- [src/wb/services/portal_campaign_finance.py](../../../src/wb/services/portal_campaign_finance.py) — `PortalCampaignFinanceService.download_xlsx()`.
- [I-24 phase doc](../../phases/I-24-portal-campaign-finance.md).
- [reverse/download-campaign-finance-reports-process.md](../../../reverse/download-campaign-finance-reports-process.md) — original captured trace.
- [reverse/История-затрат-…+03_00.xlsx](../../../reverse/История-затрат-Не определено-2026-05-29T00_00_00+03_00-2026-05-29T00_00_00+03_00.xlsx) — reference workbook from the seller (2026-05-29, 140 rows).
