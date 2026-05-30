# POST https://seller-content.wildberries.ru/ns/analytics-api/content-analytics/api/v1/file-manager/download

- **Host:** `seller-content.wildberries.ru`
- **Auth:** `authorizev3` header + browser `cookie` (see [../README.md](../README.md#auth-model))
- **Status:** undocumented
- **Date verified:** 2026-05-29
- **Used by:** [`PortalClient.generate_jam_report()`](../../../src/wb/client/portal.py) — invoked by `wb portal jam search-queries` (I-23).

Triggers generation of a WB Джем (Jam) analytics report. Despite the path being `…/download`, this is the **request-creation** endpoint — it queues a report job; the actual file lives on a separate CDN host ([file-manager-file.md](file-manager-file.md)). The `id` field is **chosen by the client** (UUID4) and echoed verbatim in the [downloads list](file-manager-downloads.md), so the same id is used to poll for completion and to compose the download URL.

Despite path-name similarity, this is NOT the same as the official "Поставка" upload `/file-manager/download` — both belong to seller-content but live under different `/ns/<service>/` prefixes.

## Request body

```jsonc
{
  "id": "3e3d13aa-5f4b-4055-b991-b0d5edf35765",   // client-generated UUID4 — keep it to match the list response
  "userReportName": "",                            // optional display name; empty is accepted
  "reportType": "SEARCH_QUERIES_REPORT",           // one of the WB Джем report-type slugs
  "params": {
    "startDate": "2026-05-11",                     // YYYY-MM-DD
    "endDate":   "2026-05-11",                     // YYYY-MM-DD; equal to startDate for single-day
    "previousStartDate": "2026-05-10",             // same-length window immediately before [start, end]
    "previousEndDate":   "2026-05-10",
    "brands": [], "subjects": [], "tags": [],
    "nms": [], "vendorCodes": [],
    "orderBy": { "field": "openCard", "mode": "desc" },
    "positionCluster": "all",
    "topOrderBy": "openCard",
    "textLimit": 30,
    "includeSearchTexts": true,
    "includeSubstitutedSKUs": true
  }
}
```

The `params` block shape is **report-type specific**. The one above is verbatim for `SEARCH_QUERIES_REPORT`. Other Jam report types accept different fields here — only `SEARCH_QUERIES_REPORT` has been reverse-engineered to date.

### `previousStartDate` / `previousEndDate`

The report embeds a same-length comparison window for delta metrics. The CLI computes it as the period immediately preceding `[startDate, endDate]`:

| Input range | Length | `previousStartDate` | `previousEndDate` |
|---|---|---|---|
| `2026-05-11..2026-05-11` | 1 day | `2026-05-10` | `2026-05-10` |
| `2026-05-26..2026-05-26` | 1 day | `2026-05-25` | `2026-05-25` |
| `2026-05-20..2026-05-27` | 8 days | `2026-05-12` | `2026-05-19` |

WB does **not** appear to validate this against the foreground window — sending a non-adjacent or different-length range likely changes only the "previous period" columns in the resulting XLSX.

## Headers

Same as the shared portal pattern (see [../README.md → Auth model](../README.md#auth-model)). `content-type: application/json` is required.

## Request example (curl)

```bash
curl -X POST 'https://seller-content.wildberries.ru/ns/analytics-api/content-analytics/api/v1/file-manager/download' \
  -H 'authorizev3: <portal JWT>' \
  -H 'cookie: <portal cookie>' \
  -H 'content-type: application/json' \
  -H 'origin: https://seller.wildberries.ru' \
  -H 'referer: https://seller.wildberries.ru/' \
  --data @body.json
```

## Response shape

```jsonc
{
  "data": "Created",
  "error": false,
  "errorText": "",
  "additionalErrors": { "errors": null }
}
```

`data: "Created"` is the only observed success value. WB does not echo the client-supplied `id` in the response — keep it client-side and match against the [downloads list](file-manager-downloads.md).

## Observed status codes

- **200 OK** — job queued. (Generation is async; poll the list endpoint until `status: "SUCCESS"`.)
- **401 / 403** — `authorizev3` or cookie expired/invalid.
- **400** — likely on malformed `params` or an unsupported `reportType`. Not yet probed exhaustively.

## Open questions

1. **Full list of `reportType` slugs.** WB Джем surfaces several report types in its UI — only `SEARCH_QUERIES_REPORT` is reverse-engineered here. Capture the others (each will have its own `params` shape).
2. **Validity of `previous*` constraints.** Does WB enforce length equality / adjacency, or is the field a pass-through to the XLSX?
3. **Per-account rate limit.** Not observed. The async list/poll loop is the natural throttle today.

## See also

- [file-manager-downloads.md](file-manager-downloads.md) — the polling endpoint (find your `id` here).
- [file-manager-file.md](file-manager-file.md) — the CDN download host.
- [tokens-jrpc.md](tokens-jrpc.md) — `team='content-analytics'` mints the `x-download-token` needed by the CDN.
- [docs/phases/I-23-portal-jam-reports.md](../../phases/I-23-portal-jam-reports.md).
