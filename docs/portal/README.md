# WB Seller Portal — Empiric API Reference

> **Unofficial endpoints. Not documented by WB. Subject to change without notice.**

This directory documents endpoints that the WB seller-portal web UI calls from a logged-in browser. They are **not** part of WB's documented [API surface](../../dev-wb-adv.md) and **not** described by the [swagger files](../swagger/). They are recorded here for the same reason the CLI uses them: to access fields the official API does not expose (richer product cards, render-token generation, CPC bid recommendations with reach forecasts).

## Scope

Three hosts are documented here:

| Host | Role |
|---|---|
| `cmp.wildberries.ru` | Campaign-management portal — bid recommendations, reach forecasts, campaign editor data. |
| `seller.wildberries.ru` | Main seller portal — auth, profile, account-level data. |
| `seller-content.wildberries.ru` | Content portal — product cards, render-token JRPC. |

All three are reached with the **same auth pair**: `authorizev3` header + browser `cookie` string (see [Auth model](#auth-model)).

## Auth model

Every portal endpoint requires **both**:

1. **`authorizev3` header** — a JWT issued to the portal session. Captured from any portal request in DevTools → Network → Headers → `authorizev3`. Lifetime ≈ session.
2. **`cookie` header** — the full `Cookie:` string for the relevant `*.wildberries.ru` domain. Includes `_wbauid`, `wbx-validation-key`, `x-supplier-id-external`, anti-bot tokens (`__zzatw-wb`, `cfidsw-wb`), and on `cmp.wildberries.ru` also `X-Current-Advertiser-ID`.

Neither token works alone. **No `Authorization: Bearer …` header is used** — that header pattern belongs to the official API only. **Do not mix** an official JWT (issued via the seller portal's "API tokens" page) with portal calls; they are different credential systems.

The CLI stores both values in the active profile under `portal_session` and provides them via the `--authorizev3` / `--cookie` flags on `wb auth login-portal`. See [src/wb/client/portal.py](../../src/wb/client/portal.py) for the implementation.

## Observation methodology

Each endpoint file in [endpoints/](endpoints/) follows the same shape:

1. **Captured live** — request copied from Chrome DevTools (`Copy → Copy as cURL`) against a real seller account.
2. **Replayed** with a one-off Python probe (`httpx.get/post` with the captured headers) to confirm the response is reproducible from outside the browser.
3. **Field semantics inferred** by varying inputs and comparing the response. Where a field's meaning is not obvious from observation, it is listed under **Open questions** rather than guessed.
4. **Date stamped** — `Date verified` records when the endpoint last produced the documented behavior. If WB silently rerouted or renamed it, the stamp tells future readers how stale the doc is.

If a documented endpoint stops working, the action is: (1) re-capture from DevTools, (2) diff request shape against this file, (3) update both the doc and any client code that depends on it.

## Endpoint index

| Endpoint | Method | Host | Used by CLI | Doc |
|---|---|---|---|---|
| `/api/v1/advert/bids` | GET | `cmp.wildberries.ru` | `wb portal bids` (F-21) | [bids.md](endpoints/bids.md) |
| `/api/v1/advert/bids-cpc` | GET | `cmp.wildberries.ru` | `wb portal bids` (F-21) | [bids-cpc.md](endpoints/bids-cpc.md) |
| `/ns/suppliers-auth/suppliers-portal-core/auth/token` | POST | `seller.wildberries.ru` | `PortalClient.authenticate()` | [auth-token.md](endpoints/auth-token.md) |
| `/ns/suppliers-auth-tokens/suppliers-portal-core/api/v1/tokensjrpc` | POST | `seller-content.wildberries.ru` | `wb auth generate-token` | [tokens-jrpc.md](endpoints/tokens-jrpc.md) |
| `/ns/viewer/content-card/viewer/tableListv6` | POST | `seller-content.wildberries.ru` | `wb portal products` | [table-list.md](endpoints/table-list.md) |

## Stability disclaimer

These endpoints have no public contract. WB may rename paths, change query-parameter semantics, alter response shapes, or remove fields between any two deployments. The CLI treats portal calls as best-effort and falls back to documented official endpoints whenever feasible — see the [auth-methods rule in CLAUDE.md](../../CLAUDE.md) ("if a documented endpoint can answer your question, use `wb auth login`…").

Update this README's date stamp whenever an endpoint file is touched.
