# POST https://seller-content.wildberries.ru/ns/suppliers-auth-tokens/suppliers-portal-core/api/v1/tokensjrpc

- **Host:** `seller-content.wildberries.ru`
- **Auth:** `authorizev3` header + browser `cookie` (see [../README.md](../README.md#auth-model))
- **Status:** undocumented
- **Date verified:** 2026-05-29 (initial entry 2026-05-23; `team='content-analytics'` added per I-23)
- **Used by:**
  - [`PortalClient.generate_token(team='render')`](../../../src/wb/client/portal.py) — invoked by `wb auth generate-token` (render token).
  - [`PortalClient.generate_download_token()`](../../../src/wb/client/portal.py) — wraps `generate_token(team='content-analytics')`; called inside `download_jam_file()` to mint the `x-download-token` required by the Jam downloads CDN (I-23).

A multi-purpose JRPC token-mint endpoint. The same `generateToken` method serves **multiple downstream "teams"**, each returning a token shaped for that team's consumers. The CLI uses two:

- `team='render'` — long opaque "render token" used by the portal's content/media services. Useful for CI/agent flows that need to drive content-rendering endpoints.
- `team='content-analytics'` — short-lived `x-download-token` for the WB Джем (Jam) downloads CDN (`downloads-content-analytics.wildberries.ru`). Required to fetch generated report files — see [file-manager-file.md](file-manager-file.md).

## Request body

JSON-RPC 2.0 envelope with the `generateToken` method and a `team` parameter:

```json
{
  "method": "generateToken",
  "jsonrpc": "2.0",
  "id": "json-rpc_1",
  "params": { "team": "<team-slug>" }
}
```

### `team` values

| `team` | Response token shape | Used for | Observed |
|---|---|---|---|
| `render` | 412-char opaque alphanumeric | Content/media render services | Yes (since F-1) |
| `content-analytics` | base64 JSON `{expiresAt, encryptedPart}`, TTL ≈ 5 min | `x-download-token` for the WB Джем downloads CDN — see [file-manager-file.md](file-manager-file.md) | Yes (I-23, 2026-05-29) |
| anything else | JRPC error `team not found` (code `-32603`) | — | Probed; `download`, `analytics`, `media` all rejected |

A single endpoint serving multiple token shapes by team is unusual but consistent across the two values WB does accept. Other valid teams may exist; probing with arbitrary strings returns `team not found` quickly enough that brute enumeration is cheap.

## Headers

Same as the shared portal pattern (see [../README.md → Auth model](../README.md#auth-model)). `content-type: application/json` is required because the body is JRPC JSON.

## Request example (curl)

```bash
curl -X POST 'https://seller-content.wildberries.ru/ns/suppliers-auth-tokens/suppliers-portal-core/api/v1/tokensjrpc' \
  -H 'authorizev3: <portal JWT>' \
  -H 'cookie: <portal cookie>' \
  -H 'content-type: application/json' \
  -H 'origin: https://seller.wildberries.ru' \
  -H 'referer: https://seller.wildberries.ru/' \
  --data '{"method":"generateToken","jsonrpc":"2.0","id":"json-rpc_1","params":{"team":"render"}}'
```

## Response shape

```jsonc
// team='render'
{
  "result": { "token": "<412-char alphanumeric token>" },
  "jsonrpc": "2.0",
  "id": "json-rpc_1"
}

// team='content-analytics'
{
  "result": {
    "token": "eyJleHBpcmVzQXQiOiIyMDI2LTA1LTI5VDIyOjA5OjE4LjcwOTQ1NzczN1oiLCJlbmNyeXB0ZWRQYXJ0IjoiNGJOa0xzTlAvd3BG…"
    // base64 of: { "expiresAt": "2026-05-29T22:09:18.709457737Z", "encryptedPart": "4bNkLsNP/wpF…" }
  },
  "jsonrpc": "2.0",
  "id": "json-rpc_1"
}

// unknown team
{
  "id": "json-rpc_1",
  "jsonrpc": "2.0",
  "error": { "code": -32603, "message": "team not found", "data": {} }
}
```

Parsed in [`PortalClient._parse_token_response()`](../../../src/wb/client/portal.py) — the CLI returns `data['result']['token']` directly (raising `ApiError` if the envelope shape is wrong; the JRPC `error` path bubbles up as the same error because there is no `result.token`).

## Field semantics (observed)

| Field | `team='render'` | `team='content-analytics'` |
|---|---|---|
| `result.token` | Opaque ~412-character alphanumeric string. Lifetime not yet measured — treat as session-scoped. | Base64-encoded JSON `{expiresAt, encryptedPart}`. **TTL ≈ 5 min** (from `expiresAt`). `encryptedPart` is opaque (WB-side encrypted blob); not regeneratable client-side. |

## Observed status codes

- **200 OK with `result.token`** — token generated.
- **200 OK with `error` envelope** — known JRPC-level failure (e.g. `team not found`).
- **401 / 403** — `authorizev3` or cookie expired.

## Open questions

1. **Other `team` values.** Three confirmed rejected (`download`, `analytics`, `media`). Probably more valid teams exist (the seller portal's JS bundle would list them). Bulk-enumerate from a dictionary if needed.
2. **`render` token lifetime.** Not measured — render-token responses are accepted by downstream services for hours, but the exact bound is unknown.
3. **Token rotation.** Calling `generateToken` again immediately with the same `team` returns a *different* token. Is the previous one revoked, or do they coexist until natural expiry? Affects whether agents should cache tokens.

## See also

- [src/wb/client/portal.py](../../../src/wb/client/portal.py) — `generate_token()` and `generate_download_token()` implementations.
- [src/wb/cli/auth.py](../../../src/wb/cli/auth.py) — `wb auth generate-token` command (render team).
- [file-manager-file.md](file-manager-file.md) — where the `content-analytics` token is consumed (`x-download-token` header).
- [docs/phases/I-23-portal-jam-reports.md](../../phases/I-23-portal-jam-reports.md) — phase notes covering the team-discovery work.
