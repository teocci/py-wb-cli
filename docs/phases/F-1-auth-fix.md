# Fix F-1 — Auth Fix (v0.3.1)

**Date:** 2026-03-19 | **Tests:** 355 passed

## Problem

Portal session auth was missing; `WB_API_TOKEN` env var not respected; ping endpoint was wrong path.

## What Was Fixed

- Portal constants: seller portal base URLs, auth headers (`authorizev3`, `wb-seller-lk`), JRPC endpoint paths
- `WB_API_TOKEN`, `WB_USER_ID`, `WB_TOKEN_EXPIRATION` env var support via `.env`
- `portal_session` field on `Profile` dataclass with `get/set/has_portal_session()` methods
- Token validation fix: ping path changed from `/adv/v1/promotion/count` to `/ping`
- `PortalClient` (`client/portal.py`): two-step JRPC auth chain
- Unified auth priority chain: CLI flags > env vars > .env > profiles.json
- CLI commands: `wb auth login-portal`, `wb auth generate-token`, `wb portal products`

## Discovery Note

Testing revealed that **cookie + authorizev3** is the real auth pair — `wb-seller-lk` session token is NOT required. PortalClient simplified accordingly.
