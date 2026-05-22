# POST https://seller.wildberries.ru/ns/suppliers-auth/suppliers-portal-core/auth/token

- **Host:** `seller.wildberries.ru`
- **Auth:** `authorizev3` header + browser `cookie` (see [../README.md](../README.md#auth-model))
- **Status:** undocumented
- **Date verified:** 2026-05-23 (backfilled — endpoint has been in use since F-1)
- **Used by:** [`PortalClient.authenticate()`](../../../src/wb/client/portal.py#L84) — invoked by `wb auth login-portal` to validate stored credentials.

Validates a portal session and returns a short-lived session JWT plus the supplier's user ID and the JWT's expiration timestamp. Used as a liveness probe — if it returns 200, the stored `authorizev3 + cookie` pair is still valid.

## Request body

JSON-RPC 2.0 envelope with an empty `params` object:

```json
{
  "jsonrpc": "2.0",
  "id": "json-rpc_1",
  "params": {}
}
```

No `method` key is sent — the path itself selects the action.

## Headers

Same as the shared portal pattern (see [../README.md → Auth model](../README.md#auth-model)). `content-type: application/json` is required because the body is JRPC JSON.

## Request example (curl)

```bash
curl -X POST 'https://seller.wildberries.ru/ns/suppliers-auth/suppliers-portal-core/auth/token' \
  -H 'authorizev3: <portal JWT>' \
  -H 'cookie: <portal cookie>' \
  -H 'content-type: application/json' \
  -H 'origin: https://seller.wildberries.ru' \
  -H 'referer: https://seller.wildberries.ru/' \
  --data '{"jsonrpc":"2.0","id":"json-rpc_1","params":{}}'
```

## Response shape

```jsonc
{
  "result": {
    "data": {
      "token": "<short-lived session JWT, ~5 min lifetime>",
      "userID": 155579335,                  // supplier's user ID (int)
      "exp":    1773884106                  // Unix epoch expiration (seconds)
    }
  },
  "jsonrpc": "2.0",
  "id": "json-rpc_1"
}
```

Parsed in [`PortalClient._parse_auth_response()`](../../../src/wb/client/portal.py#L238) into a `PortalSession(token, user_id, exp)` dataclass.

## Field semantics (observed)

| Field | Meaning |
|---|---|
| `result.data.token` | Short-lived JWT (≈5-minute lifetime). Distinct from the longer-lived `authorizev3` JWT — used for any subsequent JRPC call that requires session validation. The CLI does not currently store this; it just calls the endpoint to check the credentials are alive. |
| `result.data.userID` | Supplier's portal user ID. Saved as `user_id` in the profile's portal session record. |
| `result.data.exp` | Unix epoch (seconds) when the session token expires. The CLI exposes this as `WB_TOKEN_EXPIRATION` when bootstrapping from env. |

## Observed status codes

- **200 OK** — credentials valid.
- **401 / 403** — `authorizev3` expired or cookie invalid. The CLI maps this to `AuthenticationError` (exit 3).
- **JSON-RPC error envelope** — if the body parses but `result.data` is missing, the CLI raises `ApiError` with the raw response as context.

## Open questions

None — this is the simplest portal endpoint and has been stable since first use.

## See also

- [src/wb/client/portal.py:84](../../../src/wb/client/portal.py#L84) — `authenticate()` implementation.
- [src/wb/cli/auth.py](../../../src/wb/cli/auth.py) — `wb auth login-portal` command.
