# GET https://downloads-content-analytics.wildberries.ru/api/v1/file-manager/download/{id}

- **Host:** `downloads-content-analytics.wildberries.ru` (separate CDN from the rest of the seller portal)
- **Auth:** `cookie` **plus** `x-download-token` header. **`authorizev3` is rejected here** — do not send it.
- **Status:** undocumented
- **Date verified:** 2026-05-29 (cookie-only path returns HTTP 403; `x-download-token` minted via [tokens-jrpc.md](tokens-jrpc.md) is required)
- **Used by:** [`PortalClient.download_jam_file()`](../../../src/wb/client/portal.py) — invoked by `wb portal jam search-queries` (I-23) after the [downloads list](file-manager-downloads.md) reports `status: "SUCCESS"`.

Fetches the binary file for a generated WB Джем (Jam) report. The response is a ZIP archive containing a single `.xlsx`. The path `id` is the same UUID4 the client passed to the [generate endpoint](file-manager-generate.md) (also echoed by the [list endpoint](file-manager-downloads.md) and surfaced as `downloadUrl` there).

## Why a separate host

This host is a download-only CDN. It does not accept `authorizev3` (any of the other three portal hosts do) — sending it does not improve auth and the captured browser trace omits it. Authorization is by **`x-download-token` header** plus the session `cookie`.

## The `x-download-token` header (the puzzle)

The token is a base64-encoded JSON envelope:

```json
{
  "expiresAt": "2026-05-29T22:09:18.709457737Z",
  "encryptedPart": "4bNkLsNP/wpFYI2/dueHpViGvQXzAuY18/kVJtUABMeTqCFNJFcYFg5lGCKqKDAT…"
}
```

- **Lifetime ≈ 5 minutes** (measured from `expiresAt` minus the response time of the JRPC mint call).
- **`encryptedPart` is opaque** — WB validates it on the CDN edge; clients cannot regenerate it.
- **Where it comes from:** the **same `tokensjrpc` endpoint** that already powers `wb auth generate-token`, but with `params: { "team": "content-analytics" }` (vs the existing CLI's `team: "render"`). See [tokens-jrpc.md](tokens-jrpc.md#team-values).
- **CLI behavior:** [`PortalClient.download_jam_file()`](../../../src/wb/client/portal.py) mints just-in-time per download; there is no token caching today (the 5 min lifetime makes pre-minting risky for any non-trivial poll wait).

The original captured browser trace included the `x-download-token` on the download request but did **not** capture the request that produced it — between the `downloads` list call (`17:45:59`) and the download (`17:46:14`) the browser fired a third request the user didn't include in the markdown. Probing live (2026-05-29) revealed cookie-only download returns HTTP 403, and probing JRPC `team` values against the existing tokens endpoint produced the exact `{expiresAt, encryptedPart}` shape on `team='content-analytics'`.

## Headers

Send:

- `cookie: <browser cookie>` — required.
- `x-download-token: <base64 token from tokens-jrpc>` — required. Without it: 403.
- `accept: */*` — the response is binary, not JSON.
- `origin: https://seller.wildberries.ru`, `referer: https://seller.wildberries.ru/`, `user-agent: <browser-shaped UA>` — match the browser request.

**Do not** send `authorizev3` (the CDN rejects it). **Do not** send `content-type` (no request body).

## Request example (curl)

```bash
# Step 1 — mint the token (see tokens-jrpc.md)
TOKEN=$(curl -s 'https://seller-content.wildberries.ru/ns/suppliers-auth-tokens/suppliers-portal-core/api/v1/tokensjrpc' \
  -H 'authorizev3: <portal JWT>' \
  -H 'cookie: <portal cookie>' \
  -H 'content-type: application/json' \
  --data '{"method":"generateToken","jsonrpc":"2.0","id":"mint_1","params":{"team":"content-analytics"}}' \
  | jq -r .result.token)

# Step 2 — download
curl -sS -o report.zip \
  "https://downloads-content-analytics.wildberries.ru/api/v1/file-manager/download/935086cc-5eee-40b8-920a-877e678752de" \
  -H "cookie: <portal cookie>" \
  -H "x-download-token: $TOKEN" \
  -H 'accept: */*'
```

## Response

- **Body:** raw bytes of a ZIP archive (magic header `PK\x03\x04`). The archive contains a single `.xlsx` file whose name is set by WB (e.g. `29-5-2026 Поисковые запросы — ваши товары с 11-05-2026 по 11-05-2026.xlsx`).
- **Notable headers** (observed):
  - `content-type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` — note that this advertises **XLSX**, not ZIP, even though the body is a ZIP-of-XLSX. The CLI writes the bytes as `.zip` regardless because the magic header is `PK`.
  - `content-disposition: attachment; filename=<UTF-8-mis-encoded mojibake>.zip` — the browser-supplied filename is Latin-1-encoded UTF-8; not usable as-is. The CLI derives its own filename from the report type and date range.

## Observed status codes

- **200 OK** — file delivered.
- **403** — missing/expired `x-download-token` **or** cookie. Re-mint the token; if still 403, the cookie likely expired (run `wb auth login-portal`).
- **401** — not observed (the host appears to convert all auth failures to 403).
- **404** — would be expected for an unknown `id`, but not probed.

## Open questions

1. **Token reuse across IDs.** A token minted for one report `id` is probably valid for downloading any of the account's ready reports within its TTL (the mint doesn't take an id). Confirm by probing.
2. **Range / streaming support.** The CLI reads the whole body via `response.content`. Whether the CDN honors `Range` headers for large reports (>>1 MB) is unknown — every observed report has been ≤700 KB.
3. **Why mojibake in `content-disposition`.** WB writes UTF-8 bytes into the `filename=` parameter without RFC 5987 encoding, which most HTTP libraries decode as Latin-1. Server-side bug or intentional? Browsers render it correctly because they happen to attempt UTF-8 decoding.

## See also

- [file-manager-generate.md](file-manager-generate.md) — queue the report (step 1 of 3).
- [file-manager-downloads.md](file-manager-downloads.md) — poll for `SUCCESS` (step 2 of 3).
- [tokens-jrpc.md](tokens-jrpc.md) — mint `x-download-token` (`team='content-analytics'`).
- [docs/phases/I-23-portal-jam-reports.md](../../phases/I-23-portal-jam-reports.md).
