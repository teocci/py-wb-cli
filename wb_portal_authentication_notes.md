# WB Seller Portal — Authentication Notes
> Tested 2026-03-19

## Summary

The WB seller portal uses **cookie + authorizev3** as its authentication pair. Both are required together — neither works alone. The `wb-seller-lk` session token (from the auth/token JRPC endpoint) is **not required** for any portal endpoint.

## Token Systems

WB has two completely separate authentication systems:

| System | Auth Header | Endpoints | Token Lifetime |
|--------|------------|-----------|---------------|
| **Official WB API** | `Authorization: <JWT>` | `*-api.wildberries.ru` | 180 days |
| **Seller Portal** | `authorizev3` + `cookie` | `seller.wildberries.ru`, `seller-content.wildberries.ru` | Session-based |

These are NOT interchangeable. A portal session token fails on API endpoints with: `"access token signature is unverifiable: kid missing or empty"`.

## Portal Authentication — Test Results

### Tested Endpoints

1. **Auth endpoint**: `POST seller.wildberries.ru/ns/suppliers-auth/suppliers-portal-core/auth/token`
2. **Product list**: `POST seller-content.wildberries.ru/ns/viewer/content-card/viewer/tableListv6`
3. **Generate token**: `POST seller-content.wildberries.ru/ns/suppliers-auth-tokens/suppliers-portal-core/api/v1/tokensjrpc`

### Combination Results

#### Auth endpoint (auth/token)
| Combo | Status | Result |
|-------|--------|--------|
| cookie only | 401 | Unauthorized |
| authorizev3 only | 401 | Unauthorized |
| **cookie + authorizev3** | **200** | **Session JWT (356 chars)** |

#### Product list (tableListv6)
| Combo | Status | Result |
|-------|--------|--------|
| cookie only | 401 | Unauthorized |
| authorizev3 only | 401 | Unauthorized |
| wb-seller-lk only | 401 | Unauthorized |
| **cookie + authorizev3** | **200** | **Product cards** |
| cookie + wb-seller-lk | 401 | Unauthorized |
| authorizev3 + wb-seller-lk | 401 | Unauthorized |
| **cookie + authorizev3 + wb-seller-lk** | **200** | **Product cards (redundant wb-seller-lk)** |

#### Generate token (tokensjrpc)
| Combo | Status | Result |
|-------|--------|--------|
| **cookie + authorizev3** | **200** | **Render token (412 chars)** |
| **cookie + authorizev3 + wb-seller-lk** | **200** | **Render token (same)** |
| authorizev3 + wb-seller-lk | 401 | Unauthorized |

### Key Findings

1. **`cookie + authorizev3` is the universal auth pair** — works on all portal endpoints
2. **`wb-seller-lk` (session token) is never required** — it's optional/redundant
3. **Cookie is mandatory** — even with both authorizev3 and wb-seller-lk, requests fail without cookie
4. **authorizev3 is mandatory** — cookie alone is not enough

## Token Formats

| Token | Length | Format | Source |
|-------|--------|--------|--------|
| `authorizev3` | 727 chars | JWT (36.347.342), RS256 | Browser session |
| Session token | 356 chars | JWT (36.232.86), EdDSA | Auth JRPC endpoint |
| Render token | 412 chars | Alphanumeric (no dots) | generateToken JRPC |
| WB API token | varies | JWT with `kid` field | Seller portal UI |

## Credential Sources

Users obtain `authorizev3` and `cookie` by:
1. Logging into `seller.wildberries.ru` in a browser
2. Opening DevTools > Network tab
3. Copying the `authorizev3` header value and `cookie` header from any request

## Session Lifetime

- `authorizev3`: Tied to browser session, likely persists for hours/days
- `cookie`: Browser session cookies, may include various tracking/auth cookies
- Session token (from auth JRPC): Very short-lived (~5 minutes based on `exp` field)
- The session token's short lifetime doesn't matter since it's not required

## Implications for CLI

1. **Both `WB_AUTHORIZEV3` and `WB_PORTAL_COOKIE` are required** for portal operations
2. The `PortalClient` only needs to send these two headers — no session token management
3. The `authenticate()` method is still useful for **validation** (confirms creds work, returns user ID)
4. When creds expire, user must refresh from browser DevTools

## Portal Endpoints Discovered

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ns/suppliers-auth/suppliers-portal-core/auth/token` | POST | Validate creds, get user ID |
| `/ns/suppliers-auth-tokens/suppliers-portal-core/api/v1/tokensjrpc` | POST | Generate render tokens |
| `/ns/viewer/content-card/viewer/tableListv6` | POST | List product cards with rich data |
