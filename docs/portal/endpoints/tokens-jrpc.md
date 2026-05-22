# POST https://seller-content.wildberries.ru/ns/suppliers-auth-tokens/suppliers-portal-core/api/v1/tokensjrpc

- **Host:** `seller-content.wildberries.ru`
- **Auth:** `authorizev3` header + browser `cookie` (see [../README.md](../README.md#auth-model))
- **Status:** undocumented
- **Date verified:** 2026-05-23 (backfilled — endpoint has been in use since F-1)
- **Used by:** [`PortalClient.generate_token()`](../../../src/wb/client/portal.py#L102) — invoked by `wb auth generate-token`.

Generates a long opaque "render token" used by the portal's content/media services. The CLI surfaces this so sellers can mint a render token without leaving the terminal — useful when the seller portal UI is awkward to drive (CI scripts, agent flows).

## Request body

JSON-RPC 2.0 envelope with the `generateToken` method and a `team` parameter:

```json
{
  "method": "generateToken",
  "jsonrpc": "2.0",
  "id": "json-rpc_1",
  "params": { "team": "render" }
}
```

The CLI hardcodes `team: 'render'`. Other team values likely exist (the portal's content services may have several teams), but only `render` is exercised today.

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
{
  "result": {
    "token": "<412-char alphanumeric token>"
  },
  "jsonrpc": "2.0",
  "id": "json-rpc_1"
}
```

Parsed in [`PortalClient._parse_token_response()`](../../../src/wb/client/portal.py#L254) — the CLI returns `data['result']['token']` directly.

## Field semantics (observed)

| Field | Meaning |
|---|---|
| `result.token` | Opaque ~412-character alphanumeric string. Used by downstream content/media services as a per-team credential. Lifetime not yet observed — treat as session-scoped. |

## Observed status codes

- **200 OK** — token generated.
- **401 / 403** — `authorizev3` or cookie expired.
- **JSON-RPC error envelope** — likely on unknown `team` values; not yet observed because the CLI only sends `render`.

## Open questions

1. **Other `team` values.** The parameter is exposed in the JRPC payload — what other teams accept token generation? Try `content`, `media`, etc.
2. **Token lifetime.** Not measured. Probably tied to the parent portal session, but worth confirming for long-lived agent flows.

## See also

- [src/wb/client/portal.py:102](../../../src/wb/client/portal.py#L102) — `generate_token()` implementation.
- [src/wb/cli/auth.py](../../../src/wb/cli/auth.py) — `wb auth generate-token` command.
