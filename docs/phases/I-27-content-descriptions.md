# Phase I-27 — `wb content` (product card description management)

**Version:** 0.48.0 · **Status:** ✅ DONE · **Date:** 2026-06-21 · **Tests:** 32 new; 1691/1693 in one full run (2 pre-existing failures unrelated to I-27 — `test_auth_list_empty` env-leak + flaky `test_acquire_after_window_clears_no_sleep`)

## Goal

Add a `wb content` command group that lets a manager (or an AI agent) **read and edit product
card descriptions** — the official Content API surface the CLI never wired before. Descriptions
are living text: they must be revised to follow trends, hit objectives, and improve search
clusters. One manager hand-editing ~200 cards in the portal UI does not scale.

Commands:

```
wb content list [--text S] [--brand B] [--nms 111,222] [--limit N]   # nmID, vendorCode, title, desc length
wb content get --nm 12345                                              # full description text of one card
wb content export --out descriptions.json                             # dump all cards' {nmID,vendorCode,title,description}
wb content apply --file descriptions.json [--dry-run]                  # bulk round-trip update
wb content set-description --nm 12345 (--text "..." | --file one.txt) [--dry-run]   # single round-trip update
```

## Why now

The CLI can read basic card metadata only via the read-only portal scrape
(`wb portal products` → `tableListv6`). It has no official Content API client, so descriptions
cannot be read in bulk nor written at all. The `'content'` token category already exists in the
profile system; only the endpoint plumbing is missing.

## Authoritative API source

[docs/swagger/02-products.yaml](../../docs/swagger/02-products.yaml). Host:
**`https://content-api.wildberries.ru`** (new base URL — NOT the existing `seller-content` portal host).

| Op | Endpoint | Method | Key facts |
|----|----------|--------|-----------|
| Read | `/content/v2/get/cards/list` | POST | Cursor pagination (`limit ≤100`; carry `cursor.updatedAt` + `cursor.nmID`; stop when `cursor.total < limit`). Card carries `description`, `characteristics[]{id,name,value}`, `sizes[]{chrtID,techSize,wbSize,skus}`, `dimensions`, `brand`, `title`, `vendorCode`. No nmID filter — filter client-side or use `filter.textSearch`. RL 100/min, burst 5. |
| Write | `/content/v2/cards/update` | POST | **Destructive full-overwrite.** Array of cards. Required: `nmID`, `vendorCode`, `sizes`. Must also resend `brand`/`title`/`characteristics`/`dimensions` or they are wiped. `characteristics` send `{id, value}` only (drop `name`). ≤3000 cards/request, ≤10 MB. RL 10/min, 6 s interval, burst 5. Description max is category-dependent (1000–5000, standard 2000). |
| Confirm | `/content/v2/cards/error/list` | POST | A 200 on update does NOT guarantee success; failed cards + reasons land here. RL 10/min. |

## Core safety design — read-modify-write round-trip

`apply` / `set-description` never trust a hand-edited file to carry the full card. They re-fetch
the **live** full card from WB, swap only `description`, and send the whole object back. This
guarantees characteristics/sizes/dimensions stay current and are never corrupted by the editor.
The export file therefore carries only `{nmID, vendorCode, title, description}` — `vendorCode`
/`title` are context; only `description` is read on apply.

`apply` flow: read file → `{nmID: new_description}` map → fetch all live cards (paginate) →
`{nmID: ProductCard}` map → for each file nmID build the update payload from the live card with
the new description, skipping no-ops (unchanged) and flagging over-length → `--dry-run` prints the
diff and stops → otherwise one `cards/update` request (≤3000) → `error/list` confirms.

## Files

**New:** `domain/content.py` (`ProductCard`, `CardUpdateResult`), `client/content.py`
(`ContentClient`), `services/content.py` (`ContentService`), `cli/content.py` (`content_app`),
`tests/unit/test_content_service.py`, `tests/unit/test_content_cli.py`.

**Modified:** `core/constants.py` (`CONTENT_BASE_URL` + 3 `EP_CONTENT_*`), `core/rate_limits.py`
(3 endpoint entries), `services/_factory.py` (`_get_content_token` + `create_content_client`
/`create_content_service`), `cli/app.py` (register `content_app`).

## Steps

1. ✅ Register I-27 (IMPROVEMENTS.md, PROGRESS.md, this stub).
2. ✅ Constants — `CONTENT_BASE_URL` + `EP_CONTENT_CARDS_LIST/UPDATE/ERROR_LIST` + page/batch/length limits.
3. ✅ Rate limits — 3 `ENDPOINT_LIMITS` entries; all 3 added to `NEVER_CACHE` (cache policy).
4. ✅ `domain/content.py` — `ProductCard.from_api` / `.to_update_payload(description)`, `CardUpdateResult`.
5. ✅ `client/content.py` — `get_cards_list` (cursor loop), `update_cards`, `list_errors`.
6. ✅ `services/content.py` — list/get/export/apply_updates/set_description + classification + vendorCode→nmID error mapping.
7. ✅ `_factory.py` — `_get_content_token` + `create_content_client`/`create_content_service`.
8. ✅ `cli/content.py` + register in `app.py`.
9. ✅ Unit tests (18 service + 14 cli).
10. ✅ Finalize — CHANGELOG, RATE_LIMITS.md, CLAUDE.md quirks + Product Content surface, version bump → 0.48.0.

## Live verification

Read-only against seller `25169_personal` (2026-06-21): `wb --json content list --nms 143265407,972104944,59140395,29054173,972108323` returned real descriptions for all 5 SKUs (1339–1945 chars); `wb content get --nm 59140395` resolved the single card via `textSearch`; `wb content set-description --nm 59140395 --text … --dry-run` diffed `old 1444 → new 20` (status `changed`) with **zero writes**. The destructive write path itself is covered by unit tests (round-trip field preservation, batching, error mapping) and validated up to the WB boundary via dry-run — no live overwrite was performed.

## Out of scope

AI-assisted description generation/rewriting (keywords/clusters → text). Plumbing only; new text
comes from the manager or an external tool/file.
