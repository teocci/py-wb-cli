# Phase I-25 — `wb portal sales-report` (WB seller-goods xlsx download)

**Version:** 0.46.0 · **Status:** ✅ DONE · **Date:** 2026-06-02 · **Tests:** 1628 passing (38 new); same single pre-existing `test_auth_list_empty` env-leak as I-22..I-24

## Goal

Add a `wb portal sales-report` sub-command group that downloads the **WB seller-goods sales report** ("Отчёт по товарам / Sales report") from `seller-weekly-report.wildberries.ru`. The first (and currently only) report type wired up is `supplier-goods`, exposed as `wb portal sales-report supplier-goods`.

The report is an xlsx workbook with one row per SKU per reporting day, containing fields the documented analytics API does not expose. The user-facing CLI is a single transparent command — dates in, file out — that hides the underlying 3-step async workflow (generate → poll → download).

Reverse trace: [reverse/download-sales-reports-process.md](../../reverse/download-sales-reports-process.md).

| Step | Endpoint | Method | Host |
|------|----------|--------|------|
| Generate | `/ns/reportsviewer/analytics-back/api/report/supplier-goods/order?dateFrom=DD.MM.YY&dateTo=DD.MM.YY` | POST (no body) | `seller-weekly-report.wildberries.ru` |
| List | `/ns/reportsviewer/analytics-back/api/report/supplier-goods/orders` | GET | `seller-weekly-report.wildberries.ru` |
| Download | `/ns/reportsviewer/analytics-back/api/report/supplier-goods/xlsx/{id}` | GET | `seller-weekly-report.wildberries.ru` |

## Why now

Sellers and agents need the per-day per-SKU sales/orders breakdown that the official Statistics API does not cover at this granularity. The browser-only seller portal exposes it as an xlsx download; this phase reverse-engineers that workflow.

Originating plan: [in-a-similar-way-nested-hummingbird.md](../../../../Users/teocci/.claude/plans/in-a-similar-way-nested-hummingbird.md).

## Distinctions vs. Jam (I-23)

| Aspect | Jam | Sales-report |
|--------|-----|--------------|
| Host | 2 hosts (`seller-content` + `downloads-content-analytics`) | Single host (`seller-weekly-report`) for all 3 steps |
| Generate body | JSON `params` | Empty body — params in URL query string |
| Date format | `YYYY-MM-DD` | **`DD.MM.YY`** (day-first, 2-digit year) |
| ID | Client-generated UUID | Server-assigned; trailing nonce, NOT idempotent on re-POST |
| Download token | Separate `x-download-token` via JRPC `team='content-analytics'` | None — regular portal auth |
| Download payload | Raw `.zip` | JSON envelope `{data: "<base64 xlsx>", error: false}` — decode `data` |
| Poll signal | `status` field on list endpoint | None on list endpoint; treat **successful download** as readiness |

## Steps

1. **constants** — add `SELLER_WEEKLY_REPORT_BASE_URL`, `EP_PORTAL_SALES_REPORT_GENERATE`, `EP_PORTAL_SALES_REPORT_LIST`, `EP_PORTAL_SALES_REPORT_XLSX`, `SALES_REPORT_TYPE_SUPPLIER_GOODS` in [src/wb/core/constants.py](../../src/wb/core/constants.py). Reuse `REPORT_POLL_INTERVAL` / `REPORT_POLL_TIMEOUT`.
2. **domain** — `SalesReport` dataclass in [src/wb/domain/models.py](../../src/wb/domain/models.py) (`id, supplier_id, locale, report_name, date_from, date_to, created_at, expired_at, file_url, total_count, is_deleted`) + tolerant `from_api`. No `is_terminal` / `is_success` — readiness is the successful download itself.
3. **client** — extend `PortalClient` in [src/wb/client/portal.py](../../src/wb/client/portal.py). Change `_post(payload)` → `_post(payload=None)` so the POST body becomes optional (omitting `json=` yields `Content-Length: 0`). Add `generate_sales_report(report_type, from_dd_mm_yy, to_dd_mm_yy)`, `list_sales_reports(report_type)`, and `try_download_sales_report_xlsx(report_type, report_id) -> bytes | None`. The xlsx method base64-decodes the `data` field on success and returns `None` when the envelope indicates pending.
4. **service** — new [src/wb/services/portal_sales_report.py](../../src/wb/services/portal_sales_report.py) with `PortalSalesReportService(client)`:
   - `request_supplier_goods(from_date, to_date) -> SalesReport`
   - `fetch_supplier_goods(from_date, to_date, *, interval, timeout) -> tuple[SalesReport, bytes]`
   - `list_reports() -> list[SalesReport]`
   - `_poll_download(report_id, *, interval, timeout) -> bytes`
   - `default_filename(from_date, to_date) -> str`
   - `format_query_date(d) -> str` (DD.MM.YY, guards against year < 2000)
5. **factory** — `create_portal_sales_report_service(profile_name)` in [src/wb/services/_factory.py](../../src/wb/services/_factory.py).
6. **CLI** — in [src/wb/cli/portal.py](../../src/wb/cli/portal.py): `sales_report_app = typer.Typer(...)` + `portal_app.add_typer(...)`. Commands:
   - `@sales_report_app.command('supplier-goods')` — `--from / -f` (required), `--to / -t` (defaults to `--from`), `--output / -o`. Daily / weekly / monthly / custom = any `(from, to)` pair the user passes.
   - `@sales_report_app.command('list')` — show known supplier-goods reports.
7. **tests** — `tests/unit/test_portal_sales_report.py` covering: model parsing, DD.MM.YY formatting (incl. year < 2000 reject), default filename (single + multi-day), POST with empty body, list parsing, base64-decoded xlsx, pending envelope returns `None`, poll loop (pending → success → bytes), pipeline orchestration, CLI validation errors, CLI write-to-disk + JSON output.
8. **docs** — `CLAUDE.md` Financial Data Surface table row + new "WB API Quirks" row noting the base64-in-JSON download envelope.

## CLI shape

```text
wb [GLOBAL_FLAGS] portal sales-report supplier-goods --from YYYY-MM-DD [--to YYYY-MM-DD] [-o PATH]
wb [GLOBAL_FLAGS] portal sales-report list
```

`--to` defaults to `--from`. Any of these patterns works through the same flags:

| Use-case | Invocation |
|----------|-----------|
| Daily (default) | `--from 2026-05-11` |
| Weekly | `--from 2026-05-04 --to 2026-05-10` |
| Monthly | `--from 2026-05-01 --to 2026-05-31` |
| Custom | `--from D1 --to D2` (D2 ≥ D1) |

## Verification

- `pytest tests/unit/ -v` — 1628 passing (38 new in I-25), only the pre-existing `test_auth_list_empty` env-leak fails (carried since I-22).
- Live (executed 2026-06-02 against active profile `25169_personal`):
  - `wb portal sales-report supplier-goods --from 2026-05-11 -o d:/tmp/sales-report-verify` →
    `Generated report supplier-goods-25169-2026-05-11-2026-05-11-tikgfqshb (2026-05-11..2026-05-11)` +
    143226-byte xlsx. `zipfile.ZipFile` opens it cleanly with the expected 9-entry workbook layout
    (`xl/worksheets/sheet1.xml`, `xl/workbook.xml`, …).
  - `wb portal sales-report list` (table + `--json`) surfaces the new id at the top of the list,
    above older same-day runs.

## Notes for AI agents

- **Auth.** Requires `wb auth login-portal` (cookie + authorizev3). Same surface as `wb portal products` / `wb portal bids` / `wb portal jam`.
- **No `wb-seller-lk`.** The captured browser trace includes the `wb-seller-lk` header but it is *never required* (see `wb_portal_authentication_notes.md`). Sending only cookie + authorizev3 is sufficient.
- **Polling.** No status field on the list endpoint and re-POSTing step 1 creates a new id (trailing nonce). The cheapest reliable readiness signal is *the download itself* — service loops `try_download_sales_report_xlsx()` every 5 s.
- **Date format quirk.** URL query uses `DD.MM.YY` (two-digit year), not ISO. The `format_query_date` helper guards against `year < 2000` so the wraparound risk is explicit, not silent.
