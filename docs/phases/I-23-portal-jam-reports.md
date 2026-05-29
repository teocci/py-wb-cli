# Phase I-23 — `wb portal jam` (WB Джем / Jam report downloads)

**Version:** 0.44.0 · **Status:** ✅ DONE · **Date:** 2026-05-30 · **Tests:** 1558 passing (38 new); same single pre-existing `test_auth_list_empty` env-leak as I-22

## Goal

Add a `wb portal jam` sub-command group that downloads reports from **WB Джем** (WB Jam) — the
seller-analytics suite of the WB seller portal. The first (and currently only) report wired up is
`SEARCH_QUERIES_REPORT` ("Поисковые запросы — ваши товары"), exposed as
`wb portal jam search-queries`.

WB Jam uses an undocumented async 3-step "file-manager" workflow against the seller portal — same
auth surface (`authorizev3` + `cookie`) already used by `wb portal products` / `wb portal bids`
(F-21). This phase reverse-engineers that workflow from a browser trace captured in
[reverse/download-jam-reports-process.md](../../reverse/download-jam-reports-process.md).

| Step | Endpoint | Method | Host |
|------|----------|--------|------|
| Generate | `/ns/analytics-api/content-analytics/api/v1/file-manager/download` | POST | `seller-content.wildberries.ru` |
| Poll (list) | `/ns/analytics-api/content-analytics/api/v1/file-manager/downloads?report_types=<TYPE>` | GET | `seller-content.wildberries.ru` |
| Download | `/api/v1/file-manager/download/{id}` | GET | `downloads-content-analytics.wildberries.ru` |

## Why now

Seller-portal "Jam" reports surface fields the official analytics API does not expose (per-product
search-query position cluster + substituted SKUs in particular). Agents currently have to scrape
this manually; the CLI should automate the generate → poll → download chain and hand back a `.zip`.

Originating plan: [reverse-download-jam-reports-process-md-synchronous-whistle.md](../../../../Users/teocci/.claude/plans/reverse-download-jam-reports-process-md-synchronous-whistle.md).

## Distinctions

| CLI | Source | What it returns |
|-----|--------|-----------------|
| `wb portal products` | portal `tableListv6` | Live product cards (vendor codes, stocks, ratings) |
| `wb portal bids` | portal `bids` / `bids-cpc` | CPC/CPM bid recommendations |
| `wb portal jam search-queries` | portal `file-manager/download` (async) | XLSX-in-ZIP of search-query metrics over a date range |

## Steps

1. **constants** — add `DOWNLOADS_CONTENT_ANALYTICS_BASE_URL`, `EP_PORTAL_JAM_GENERATE`,
   `EP_PORTAL_JAM_DOWNLOADS`, `EP_PORTAL_JAM_FILE`, `JAM_REPORT_SEARCH_QUERIES` in
   [src/wb/core/constants.py](../../src/wb/core/constants.py). Re-use existing
   `REPORT_POLL_INTERVAL` / `REPORT_POLL_TIMEOUT` (no new poll constants).
2. **domain** — `JamReport` dataclass in [src/wb/domain/models.py](../../src/wb/domain/models.py)
   (`id, status, name, size, start_date, end_date, download_url, created_at, generated_at`) +
   `from_api` classmethod.
3. **client** — extend `PortalClient` in [src/wb/client/portal.py](../../src/wb/client/portal.py)
   with `generate_jam_report(report_id, report_type, params)`, `list_jam_reports(report_type)`,
   `download_jam_file(report_id)`, `generate_download_token()` (and a small `team` parameter on
   the existing `generate_token`), plus a new `_get_bytes(base_url, path, *, download_token)` helper
   that returns `response.content` (same 401/403/4xx handling as `_get`). The downloads CDN
   (`downloads-content-analytics.wildberries.ru`) **requires** an `x-download-token` header —
   verified empirically on 2026-05-29 — minted via the same `tokensjrpc` endpoint that already
   powers `wb auth generate-token`, but with `params={'team': 'content-analytics'}` instead of
   `'render'`. The token is short-lived (≈5 min) so `download_jam_file` mints it just-in-time.
4. **service** — new [src/wb/services/portal_jam.py](../../src/wb/services/portal_jam.py) with
   `PortalJamService(client)`:
   - `build_search_queries_params(from_date, to_date) -> dict` (computes same-length `previous*` window).
   - `poll_report(report_id, report_type, interval, timeout) -> JamReport` (mirrors
     `reports.poll_warehouse_report`).
   - `fetch_search_queries(from_date, to_date) -> tuple[JamReport, bytes]` (orchestrator).
   - `list_reports(report_type) -> list[JamReport]`.
   - `default_filename(report_type, from_date, to_date) -> str`.
5. **factory** — `create_portal_jam_service(profile_name)` in
   [src/wb/services/_factory.py](../../src/wb/services/_factory.py), built on top of the existing
   `create_portal_client`.
6. **CLI** — in [src/wb/cli/portal.py](../../src/wb/cli/portal.py): `jam_app = typer.Typer(...)` +
   `portal_app.add_typer(jam_app, name='jam', ...)`. Commands:
   - `@jam_app.command('search-queries')` — `--from/-f --to/-t --output/-o` (file or dir).
     Generate → poll → download → write `.zip` → render metadata. `--json` for machine output.
   - `@jam_app.command('list')` — show ready Jam search-queries reports (the step-2 list view).
7. **tests** — `tests/unit/test_portal_jam.py` covering: params window math (single day +
   multi-day `previous*`), poll loop (PROCESSING → SUCCESS with id match), FAILED/timeout raises,
   `download_jam_file` returns bytes, `list_reports` parsing, default filename, CLI write-to-disk
   (`tmp_path`).
8. **docs** — add a "Jam reports" row to the financial / data-surface table in CLAUDE.md and a row
   in the WB API Quirks table about the download host's headers.

## Out of scope (deferred follow-ups)

- Additional Jam report types (the file-manager endpoint accepts other `reportType` values but we
  only have a payload trace for `SEARCH_QUERIES_REPORT`). Adding a new report = add `build_<type>_params`
  + a new `@jam_app.command(...)` — small change, no restructuring needed.
- Auto-extracting the `.xlsx` inside the `.zip` — sellers already have the zip on disk; agents that
  want the rows can pipe `unzip -p … | xlsx2csv -`.

## CLI shape (final)

```text
wb [GLOBAL_FLAGS] portal jam search-queries --from YYYY-MM-DD [--to YYYY-MM-DD] [-o PATH]
wb [GLOBAL_FLAGS] portal jam list
```

Global flags (`--json`, `--compact`, `--profile`, `--fields`, `--no-cache`, `--verbose`, `--quiet`)
are on the app callback — they MUST precede the subcommand chain.

## Verification

- `pytest tests/unit/ -v` → 38 new tests green; only the pre-existing `test_auth_list_empty`
  env-leak failure (carried from I-22) remains. 1558 total passing.
- Live (executed 2026-05-29 against active profile `25169_personal`):
  - `wb portal jam search-queries --from 2026-05-11 -o d:/tmp/jam-verify` →
    `Generated report 650ef595-… (2026-05-11..2026-05-11, 574951 bytes)` +
    `Saved: d:\tmp\jam-verify\search-queries_2026-05-11.zip`. ZIP unzipped to a valid 660-KB XLSX
    named "29-5-2026 Поисковые запросы — ваши товары с 11-05-2026 по 11-05-2026.xlsx".
  - `wb --json portal jam list` → lists the May 11 report id (`SUCCESS`) plus prior runs.

## Notes for AI agents

- **Auth.** Requires `wb auth login-portal` (cookie + authorizev3). Same surface as
  `wb portal products` / `wb portal bids` — no extra setup.
- **Polling.** The poll interval (5 s default) IS the throttle — `PortalClient` doesn't go through
  `SharedRateLimiter` because it uses raw `httpx`. Don't loop the command in tight wrappers.
- **Download host (`downloads-content-analytics.wildberries.ru`).** Cookie alone is **not**
  sufficient — the host returns HTTP 403 without the `x-download-token` header. The token is minted
  by calling the seller-portal JRPC endpoint
  `POST seller-content.wildberries.ru/ns/suppliers-auth-tokens/.../tokensjrpc` with
  `{method: 'generateToken', params: {team: 'content-analytics'}}`. Response is a base64-encoded
  `{expiresAt, encryptedPart}` token (TTL ≈ 5 minutes). `PortalClient.generate_download_token()`
  wraps this. The download request itself sends `cookie + x-download-token + accept: */*` and **no**
  `authorizev3` (the CDN host rejects it).
