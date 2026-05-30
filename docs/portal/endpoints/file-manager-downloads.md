# GET https://seller-content.wildberries.ru/ns/analytics-api/content-analytics/api/v1/file-manager/downloads

- **Host:** `seller-content.wildberries.ru`
- **Auth:** `authorizev3` header + browser `cookie` (see [../README.md](../README.md#auth-model))
- **Status:** undocumented
- **Date verified:** 2026-05-29
- **Used by:** [`PortalClient.list_jam_reports()`](../../../src/wb/client/portal.py) — invoked by `wb portal jam list` and used as the polling step inside `wb portal jam search-queries` (I-23).

Lists WB Джем (Jam) reports of a given type that the account has queued or completed. Together with [file-manager-generate.md](file-manager-generate.md) and [file-manager-file.md](file-manager-file.md), this forms the generate → poll → download triple for async Jam report downloads.

## Query params

| Name | Required | Example | Meaning |
|---|---|---|---|
| `report_types` | yes | `SEARCH_QUERIES_REPORT` | Comma-separated list of WB Джем report-type slugs. With one type, returns only entries of that type. Empty parameter likely 400s; not probed. |

## Headers

Same as the shared portal pattern (see [../README.md → Auth model](../README.md#auth-model)). No request body — GET only.

## Request example (curl)

```bash
curl 'https://seller-content.wildberries.ru/ns/analytics-api/content-analytics/api/v1/file-manager/downloads?report_types=SEARCH_QUERIES_REPORT' \
  -H 'authorizev3: <portal JWT>' \
  -H 'cookie: <portal cookie>' \
  -H 'accept: */*' \
  -H 'origin: https://seller.wildberries.ru' \
  -H 'referer: https://seller.wildberries.ru/'
```

## Response shape

```jsonc
{
  "error": false,
  "errorText": "",
  "additionalErrors": { "errors": null },
  "data": {
    "downloads": [
      {
        "id": "935086cc-5eee-40b8-920a-877e678752de",      // matches the UUID the client passed to file-manager/download
        "createdAt": "2026-05-29T22:01:13Z",                // ISO-8601 UTC — when WB queued the job
        "generatedAt": "2026-05-29T22:01:21Z",              // ISO-8601 UTC — empty string until status hits a terminal value
        "status": "SUCCESS",                                // see Status values below
        "name": "Поисковые запросы — ваши товары",         // human-readable Russian name (per reportType)
        "size": 575369,                                     // bytes; 0 until generated
        "startDate": "2026-05-11",                          // echoed from the generate request
        "endDate":   "2026-05-11",
        "downloadUrl": "https://downloads-content-analytics.wildberries.ru/api/v1/file-manager/download/935086cc-5eee-40b8-920a-877e678752de"
      }
      // …most-recent-first, oldest at the end
    ]
  }
}
```

Order is observed as **most-recent first** (`createdAt` descending). The list returns all the account's reports of `report_types` — there is no opt-in filter for "ready only" or "not yet downloaded". Clients filter by `status` themselves.

## Status values (observed)

| Value | Terminal? | Meaning |
|---|---|---|
| `SUCCESS` | yes | Report generated; `downloadUrl` is valid (with [file-manager-file.md](file-manager-file.md) token rules). |
| `PROCESSING` | no | Job is running. Poll again. |
| `FAILED` / `ERROR` | yes | Job failed. Names inferred from generic API conventions — not yet observed live; treat any non-`SUCCESS` terminal status as a failure. |

The CLI treats `SUCCESS` as success and `FAILED`/`ERROR` as terminal-fail; anything else continues polling until a 120 s timeout. See [`JamReport.is_terminal`](../../../src/wb/domain/models.py) and `PortalJamService.poll_report()` in [src/wb/services/portal_jam.py](../../../src/wb/services/portal_jam.py).

## Field semantics

| Field | Notes |
|---|---|
| `id` | UUID4 chosen by the client in the [generate](file-manager-generate.md) call. WB stores and echoes it verbatim. Use it to identify your own report among others in the list. |
| `createdAt` | When WB accepted the generate request. |
| `generatedAt` | When WB finished writing the file. Empty string for non-`SUCCESS` entries. Typical generate-to-ready latency for `SEARCH_QUERIES_REPORT`: 2–8 seconds (observed `22:01:13Z → 22:01:21Z` = 8 s). |
| `size` | Size of the eventual ZIP in bytes. `0` before generation; ~500–600 KB once ready for a typical single-day search-queries report. |
| `downloadUrl` | Full CDN URL on `downloads-content-analytics.wildberries.ru`. The path is always `{host}/api/v1/file-manager/download/{id}` — the CLI composes this from `id` rather than trusting the response field. |
| `name` | Russian display name keyed off `reportType` ("Поисковые запросы — ваши товары" for `SEARCH_QUERIES_REPORT`). |

The response contains **no** download-token field — the `x-download-token` required by the CDN is minted separately via [tokens-jrpc.md](tokens-jrpc.md) with `team='content-analytics'`. This was the main reverse-engineering puzzle for I-23 (the captured browser trace included the token in the download request but omitted the request that produced it).

## Observed status codes

- **200 OK** — list returned (may be empty `downloads: []`).
- **401 / 403** — `authorizev3` or cookie expired/invalid.
- **400** — likely on missing/malformed `report_types`; not yet probed.

## Open questions

1. **Pagination / retention.** The response is not paginated in any observed call — does WB cap the list, and at what age/count does it prune?
2. **`status` enumeration.** `FAILED`/`ERROR` are guessed-then-treated as terminal; live capture of an actual generate failure would confirm the exact slug.
3. **Multi-type query.** Is the comma-separated `report_types` actually honored, or is a single value the only path WB supports? Captured browser calls only ever send one.

## See also

- [file-manager-generate.md](file-manager-generate.md) — request creation.
- [file-manager-file.md](file-manager-file.md) — CDN download (and the `x-download-token` header).
- [tokens-jrpc.md](tokens-jrpc.md) — where the `x-download-token` comes from (`team='content-analytics'`).
- [docs/phases/I-23-portal-jam-reports.md](../../phases/I-23-portal-jam-reports.md).
