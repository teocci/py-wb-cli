# WB CLI — Authorization System Plan
> v0.1 — Authorization Design Document

---

## 0. Current State

The WB CLI currently supports **API key auth only**:
- User runs `wb auth login --token <JWT> --category promotion`
- Token stored as raw string in profile JSON file
- HTTP client sends `Authorization: <token>` header (no `Bearer` prefix)
- Token validated via `GET /adv/v1/promotion/count` endpoint

This is correct per the [official WB API docs](https://dev.wildberries.ru/en/docs/openapi/api-information#tag/Authorization), which specify `HeaderApiKey` scheme — raw JWT in `Authorization` header.

---

## 1. Problem

The CLI's auth system has two gaps:

1. **No environment variable fallback** — users must always use profile-based auth. There's no support for `WB_API_TOKEN` env var, which is standard for CLI tools and CI/CD pipelines.

2. **No seller portal session support** — the only way to get an API token is manually through the WB seller portal web UI. The CLI cannot:
   - Authenticate against the seller portal programmatically
   - Generate or manage API tokens from the command line
   - Access portal-only data not available through the official API

---

## 2. WB Authorization Architecture

### 2.1 Official WB API (current support)

```
Header: Authorization: <JWT_TOKEN>
Scheme: HeaderApiKey (no Bearer prefix)
Token: JWT per RFC 7519, 180-day validity
Types: Personal, Service, Base, Test
Categories: Content, Analytics, Promotion, Statistics, etc.
Ping: GET https://advert-api.wildberries.ru/ping
```

**Token JWT structure:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUIDv4 | Unique token ID |
| `s` | uint | Token properties bitmask (bit 6 = Promotion access) |
| `sid` | UUIDv4 | Wildberries seller ID |
| `exp` | uint | Token lifetime (RFC 7519) |
| `acc` | uint | Token type: 1=Base, 2=Test, 3=Personal, 4=Service |
| `for` | string | `self` for personal, `asid:{ID}` for service |
| `t` | bool | `true` for test tokens |

### 2.2 Seller Portal Session Auth (new support)

The seller portal at `seller.wildberries.ru` uses a separate authentication chain based on JSON-RPC:

```
Step 1: Portal session authentication
  POST https://seller.wildberries.ru/ns/suppliers-auth/suppliers-portal-core/auth/token
  Headers:
    authorizev3: <AUTHORIZEV3_KEY>  (727 chars, JWT: 36.347.342)
    cookie: <BROWSER_COOKIES>
  Payload:
    {"params":{},"jsonrpc":"2.0","id":"json-rpc_136"}
  Response:
    {
      "id": "json-rpc_10",
      "jsonrpc": "2.0",
      "result": {
        "data": {
          "token": "<SESSION_TOKEN>",   ← 356 chars, JWT: 36.232.86
          "userID": 155579335,
          "exp": 1773884106
        }
      }
    }

Step 2: Portal API calls (e.g., generate API token)
  POST https://seller-content.wildberries.ru/ns/suppliers-auth-tokens/suppliers-portal-core/api/v1/tokensjrpc
  Headers:
    authorizev3: <AUTHORIZEV3_KEY>
    wb-seller-lk: <SESSION_TOKEN>     ← from Step 1
    cookie: <BROWSER_COOKIES>
  Payload:
    {"method":"generateToken","params":{"team":"render"},"jsonrpc":"2.0","id":"json-rpc_119"}
  Response:
    {
      "id": "json-rpc_119",
      "jsonrpc": "2.0",
      "result": {
        "token": "<RENDER_TOKEN>"     ← 412 chars, alphanumeric only
      }
    }
```

**Token formats observed:**

| Token | Length | Format | Source |
|-------|--------|--------|--------|
| `authorizev3` | 727 | JWT (36.347.342), base64url | Browser session |
| Session token | 356 | JWT (36.232.86), shares first 36 chars with authorizev3 | Auth endpoint |
| Render token | 412 | Pure alphanumeric (no dots/hyphens) | generateToken JRPC |

**Auth pair:** `cookie + authorizev3` (both required, neither works alone)

**Note:** The `wb-seller-lk` session token is NOT required for any portal endpoint. See `wb_portal_authentication_notes.md` for comprehensive test results.

**User provides:** `authorizev3` key + browser cookie (both from browser DevTools)

---

## 3. Design Goals

| Goal | Description |
|------|-------------|
| Dual auth | Support both API key (official) and portal session (reverse-engineered) |
| Unified priority | CLI flags > env vars > .env > profiles.json for all credentials |
| Env var support | `WB_API_TOKEN`, `WB_AUTHORIZEV3`, `WB_PORTAL_COOKIE`, `WB_USER_ID`, `WB_TOKEN_EXPIRATION` |
| Token generation | Generate API tokens from CLI using portal session |
| Portal data access | Access seller portal endpoints for data not in official API |
| Backward compatibility | Existing profiles.json files continue to work |
| Iterative refinement | Portal auth is reverse-engineered; build, test, and refine |

---

## 4. Implementation Plan

### 4.1 Constants (`src/wb/core/constants.py`)

Add:
```python
# ── Ping endpoint ────────────────────────────────────────────────────
PING_PATH = '/ping'
COMMON_API_BASE_URL = 'https://common-api.wildberries.ru'

# ── Seller Portal ────────────────────────────────────────────────────
SELLER_PORTAL_BASE_URL = 'https://seller.wildberries.ru'
SELLER_CONTENT_BASE_URL = 'https://seller-content.wildberries.ru'
PORTAL_AUTH_HEADER = 'authorizev3'
PORTAL_SESSION_HEADER = 'wb-seller-lk'
EP_PORTAL_AUTH_TOKEN = '/ns/suppliers-auth/suppliers-portal-core/auth/token'
EP_PORTAL_TOKENS_JRPC = '/ns/suppliers-auth-tokens/suppliers-portal-core/api/v1/tokensjrpc'
```

### 4.2 Config — env var support (`src/wb/core/config.py`)

Add fields to existing `Settings` class:
```python
# Auth env var fallbacks
api_token: str | None = None           # WB_API_TOKEN
user_id: int | None = None             # WB_USER_ID
token_expiration: int | None = None    # WB_TOKEN_EXPIRATION

# Portal session env var fallbacks
authorizev3: str | None = None         # WB_AUTHORIZEV3
portal_cookie: str | None = None       # WB_PORTAL_COOKIE
```

### 4.2.1 Credential Resolution Priority

All credentials follow the same chain (highest to lowest):
```
CLI flags > Environment variables > .env file > ~/.wb-cli/profiles.json
```

Pydantic-settings handles env vars > .env automatically. CLI flags override both via factory function parameters.

### 4.3 Profile model — portal session (`src/wb/auth/profiles.py`)

Add `portal_session` field to `Profile`:
```python
portal_session: dict[str, str] = field(default_factory=dict)
```

Keys: `authorizev3`, `cookie`, `session_token`, `user_id`, `exp`

Methods: `get_portal_session()`, `set_portal_session()`, `has_portal_session()`

Backward compat: `from_dict()` reads `portal_session` with default `{}`

### 4.4 Token validation fix (`src/wb/auth/token_validation.py`)

Change ping path from `/adv/v1/promotion/count` to `/ping` (official endpoint).

### 4.5 Portal client — new (`src/wb/client/portal.py`)

New `PortalClient` class:
- Constructor: `PortalClient(authorizev3, cookie=None)`
- `authenticate() -> PortalSession` — Step 1, returns session token + user_id + exp
- `generate_token(session_token) -> str` — Step 2, calls generateToken JRPC
- `_jrpc_request(base_url, path, payload)` — JSON-RPC helper
- Browser-like headers for compatibility (user-agent, origin, referer)

### 4.6 Factory — portal client + env var fallback (`src/wb/services/_factory.py`)

- `create_portal_client(profile_name)` — loads portal session from profile
- Update `_get_promotion_token()` — check `Settings().api_token` as fallback

### 4.7 CLI commands (`src/wb/cli/auth.py`)

New commands:
- `wb auth login-portal --authorizev3 <key> [--cookie <str>] [--profile <name>]`
  - Authenticates via portal, stores session in profile
- `wb auth generate-token [--profile <name>]`
  - Uses stored portal session to generate token via JRPC
  - Auto-stores result in profile

### 4.8 Tests

| Test file | Coverage |
|-----------|----------|
| `tests/unit/test_token_validation.py` | Updated ping path |
| `tests/unit/test_portal_client.py` | **New** — portal auth + JRPC mocking |
| `tests/unit/test_profiles.py` | portal_session field, backward compat |
| `tests/unit/test_cli_auth.py` | login-portal, generate-token commands |
| `tests/unit/test_config.py` | WB_API_TOKEN env var fallback |

---

## 5. Execution Order

1. Constants (portal URLs, headers, endpoints, ping path)
2. Config (env var fields)
3. Profile model (portal_session storage)
4. Token validation fix (/ping)
5. Portal client (new JRPC client)
6. Factory (portal client + env var fallback)
7. CLI commands (login-portal, generate-token)
8. Tests
9. Update DESIGN.md, PROGRESS.md, CLAUDE.md

---

## 6. Post-Implementation Updates

After implementation:
- **DESIGN.md** — add portal auth section to architecture, add new commands to taxonomy
- **PROGRESS.md** — document what was built, test results
- **CLAUDE.md** — update auth commands section, add portal auth flow

---

## 7. Open Areas for Exploration

These will be investigated during implementation through testing:

- What other JRPC methods exist on the tokens endpoint besides `generateToken`?
- What does the `team` parameter control? (observed value: `"render"`)
- Can the render token (412 chars) be used as an actual WB API token?
- What is the session token expiration behavior?
- Are there additional portal endpoints useful for the CLI?
