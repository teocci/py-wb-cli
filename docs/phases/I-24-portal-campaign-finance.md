# Phase I-24 — `wb portal campaign finance{,-xlsx}` (campaign finance ledger)

**Version:** 0.45.0 · **Status:** ✅ DONE · **Date:** 2026-05-31 · **Tests:** 1590/1591 passing (32 new); same pre-existing `test_auth_list_empty` env-leak as I-23

## Goal

Add two synchronous portal commands under a new `wb portal campaign` group that surface the
campaign **expense ledger** ("История затрат") visible at
`https://cmp.wildberries.ru/campaigns/finances`:

- `wb portal campaign finance` — JSON rows from `GET /api/v6/upd` (paginated; `--all` is the
  default, `--page N --page-size N` for explicit slices).
- `wb portal campaign finance-xlsx` — binary `xlsx` from `GET /api/v5/updxlsx` (single call,
  returns all rows for the date range; saved to disk via `-o PATH`).

Both endpoints live on `cmp.wildberries.ru` (same host as `wb portal bids` from F-21) and
share the standard portal auth surface (`authorizev3` + `cookie`). Captured in
[reverse/download-campaign-finance-reports-process.md](../../reverse/download-campaign-finance-reports-process.md);
reference xlsx at [reverse/История-затрат-…+03_00.xlsx](../../reverse/История-затрат-Не определено-2026-05-29T00_00_00+03_00-2026-05-29T00_00_00+03_00.xlsx).

| Step | Endpoint | Method | Host | Pagination |
|------|----------|--------|------|------------|
| List rows | `/api/v6/upd?page_number=N&page_size=N&bid_type=[0]&attribute=all&from=…&to=…` | GET | `cmp.wildberries.ru` | paginated |
| Download xlsx | `/api/v5/updxlsx?bid_type=[0]&from=…&to=…&pageNumber=1&pageSize=10` | GET | `cmp.wildberries.ru` | none (returns everything) |

## Why now

The official `/adv/v3/fullstats` returns *aggregate* campaign metrics — there is no documented
endpoint that exposes the per-deduction ledger (campaign × charge date × payment source). Finance
and accounting workflows specifically ask for the xlsx; agents want the JSON. The reverse-engineered
trace already gives us both, and the existing `PortalClient` already speaks to `cmp.wildberries.ru`.

Originating plan: [in-the-same-way-purrfect-cascade.md](../../../../Users/teocci/.claude/plans/in-the-same-way-purrfect-cascade.md).

## Distinctions

| CLI | Source | What it returns |
|-----|--------|-----------------|
| `wb finance sales-reports …` | OFFICIAL `/api/finance/v1/sales-reports/*` | Settlement statements (what WB owes the seller) |
| `wb finance acquiring …` | OFFICIAL `/api/finance/v1/acquiring/*` | Card-processing fees |
| `wb portal campaign finance` | portal `/api/v6/upd` | Per-deduction ad-spend ledger (JSON) |
| `wb portal campaign finance-xlsx` | portal `/api/v5/updxlsx` | Same ledger as a downloadable xlsx |
| `wb budget balance` | promotion `/adv/v1/balance` | Ad-deposit balance |

## Steps

1. **constants** — add `EP_PORTAL_UPD_LIST`, `EP_PORTAL_UPD_XLSX`, `MSK_TZ_OFFSET`,
   `CAMPAIGN_FINANCE_DEFAULT_PAGE_SIZE` to [src/wb/core/constants.py](../../src/wb/core/constants.py)
   and export in `__all__`.
2. **domain** — `CampaignFinanceEntry` + `CampaignFinancePage` dataclasses in
   [src/wb/domain/models.py](../../src/wb/domain/models.py) with `from_api` classmethods.
3. **client** — extend `PortalClient` in [src/wb/client/portal.py](../../src/wb/client/portal.py):
   - `list_campaign_finance(from_dt, to_dt, *, page_number, page_size) -> dict` — wraps GET
     `/api/v6/upd`.
   - `download_campaign_finance_xlsx(from_dt, to_dt, *, page_size) -> bytes` — wraps GET
     `/api/v5/updxlsx`.
   - Refactor `_get_bytes()` to accept `params: dict | None`, `include_auth: bool = True`, and an
     overridable `origin/referer`. The jam caller passes `include_auth=False` to preserve current
     behavior (downloads CDN rejects `authorizev3`). The new finance-xlsx caller uses the default
     `include_auth=True` against `cmp.wildberries.ru` and overrides the origin/referer to the cmp
     host.
4. **service** — new [src/wb/services/portal_campaign_finance.py](../../src/wb/services/portal_campaign_finance.py)
   with `PortalCampaignFinanceService(client)`:
   - `list_page(from_date, to_date, *, page_number, page_size) -> CampaignFinancePage`.
   - `list_all(from_date, to_date) -> CampaignFinancePage` (auto-paginate; concatenates entries).
   - `download_xlsx(from_date, to_date) -> bytes`.
   - `default_filename(from_date, to_date) -> str` and `format_msk_datetime(d) -> str` helpers.
5. **factory** — `create_portal_campaign_finance_service(profile_name)` in
   [src/wb/services/_factory.py](../../src/wb/services/_factory.py).
6. **CLI** — in [src/wb/cli/portal.py](../../src/wb/cli/portal.py):
   - `campaign_app = typer.Typer(...)` + `portal_app.add_typer(campaign_app, name='campaign', ...)`.
   - `@campaign_app.command('finance')` — `--from / --to / --page / --page-size`. Table by default;
     `--json` emits `{entries, upd_total_amount, total_count, page_number, page_size}`.
   - `@campaign_app.command('finance-xlsx')` — `--from / --to / -o PATH`. Writes xlsx; `--json`
     emits `{saved_path, byte_size, from, to}` metadata only.
   - Promote `_parse_iso_date` and rename `_resolve_jam_output` → `_resolve_download_output` for
     reuse across both download commands.
7. **tests** — `tests/unit/test_portal_campaign_finance.py` covering: dataclass parsing,
   MSK datetime helper, default filename, client list+download (respx mocks for auth headers
   + query params), service auto-paginate, CLI table + JSON modes + write-to-disk + 401/403
   handling. Plus a regression test for `download_jam_file` (asserts the `_get_bytes` refactor
   still omits `authorizev3` for the jam CDN path).
8. **docs** — extend the "Financial Data Surface" table in CLAUDE.md with the two new rows.

## Out of scope (deferred follow-ups)

- CLI filtering by campaign id / bid_type / payment source. Captured requests use
  `bid_type=[0]` + `attribute=all` exclusively; if a seller needs filtering they JSON-pipe through
  `jq` for now.
- Reconciling the `_BID_TYPE_INT` enum mismatch between F-21 (`/api/v1/advert/bids[-cpc]` → "1 =
  manual, 2 = unified") and `/api/v6/upd` (returns `bid_type=1` for campaigns the xlsx shows as
  "Единая Ставка" / Unified). Kept as a known issue — the new `CampaignFinanceEntry` stores
  `bid_type` as a raw int so callers can map themselves until F-21 is revisited.
- Decoding the mojibake `Content-Disposition` filename returned by the xlsx endpoint. We mint our
  own clean kebab-case name instead.
- Consolidating `wb finance` (documented settlement) and `wb portal campaign finance{,-xlsx}`
  (unofficial ad-spend ledger). Different APIs, different surfaces.

## CLI shape (final)

```text
wb [GLOBAL_FLAGS] portal campaign finance       --from YYYY-MM-DD [--to YYYY-MM-DD] [--page N] [--page-size N]
wb [GLOBAL_FLAGS] portal campaign finance-xlsx  --from YYYY-MM-DD [--to YYYY-MM-DD] [-o PATH]
```

Global flags (`--json`, `--compact`, `--profile`, `--fields`, `--no-cache`, `--verbose`,
`--quiet`) live on the app callback — they MUST precede the subcommand chain.

## Verification

Live against `25169_personal` for 2026-05-11 (executed 2026-05-30 / 2026-05-31):

- `wb --profile 25169_personal portal campaign finance --from 2026-05-11 --page 1 --page-size 5`
  → `Total: 193,925 ₽ across 159 rows (page 1, size 5, returned 5)` + 5-row table. Both payment
  sources visible ("Баланс" + "Промо бонусы"), both bid_type values present (1 = Ед / 2 = Руч).
- `wb --profile 25169_personal --json portal campaign finance --from 2026-05-11 --page 1 --page-size 2`
  → JSON envelope: `{entries[2], upd_total_amount: 193925, total_count: 159, page_number: 1, page_size: 2}`.
- `wb --profile 25169_personal --json portal campaign finance --from 2026-05-11` (no `--page`, auto-paginate)
  → walked 2 API calls at `page_size=100` (100 + 59); returned `len(entries)=159`, `page_number=1`,
  `page_size=159` (synthetic merged-page size = combined entry count), `total_count=159`. Sum of
  every row's `upd_sum` field = `193,925 ₽`, matching the reported `upd_total_amount` exactly.
  122 unique `advert_id` values across 159 rows confirms WB charges the same campaign multiple
  times per day (different payment sources / bid types).
- `wb --profile 25169_personal portal campaign finance-xlsx --from 2026-05-11 -o d:/tmp/i24/`
  → wrote `d:\tmp\i24\campaign-finance_2026-05-11.xlsx` (13,375 bytes); inspection shows
  160 rows (1 header + 159 data rows) — exactly matches the JSON `total_count`. First data row
  matches first JSON entry (advert_id 30853961, sum 43, "WB 183813948 | Руч").
- `wb --profile 25169_personal portal jam list` → 5 prior search-queries reports listed
  unchanged (regression check for the `_get_bytes` / `_get` overload refactor).

`pytest tests/unit/` → 1590 passing + 1 pre-existing failure (`test_auth_list_empty` env-leak,
unchanged since I-22). 32 new tests in `test_portal_campaign_finance.py`, all green; existing
`test_portal_jam.py` and `test_portal_client.py` continue to pass (74/74) confirming the
`_get_bytes` refactor preserved the jam CDN behavior.

**Empirical bid_type mapping (confirmed via 2026-05-11 xlsx column C "Раздел"):**
- `bid_type=1` → "Единая Ставка" (Unified Rate)
- `bid_type=2` → "Ручная Ставка" (Manual Rate)
This is the **opposite** of F-21's `_BID_TYPE_INT` in [src/wb/cli/portal.py](../../src/wb/cli/portal.py),
which says `1=manual, 2=unified`. Either F-21 is wrong or the two endpoints disagree on the
enum. Deferred — see "Out of scope".

## Notes for AI agents

- **Auth.** Requires `wb auth login-portal` (cookie + authorizev3). Same surface as the rest of
  `wb portal`.
- **Dates.** Both endpoints expect ISO-8601 with MSK offset, e.g. `2026-05-29T00:00:00+03:00`.
  Use start-of-day for both `from` and `to` — the WB UI does the same and the response date math
  treats `to` as inclusive end-of-day.
- **`bid_type=[0]` is the literal string `[0]`** (URL-encoded `%5B0%5D`). The pinned value =
  "all bid types".
- **Page size in the xlsx endpoint is a red herring** — the response is always the full ledger
  for the date range regardless of `pageSize`. The captured value (`pageSize=10`) is just what the
  UI happens to send.
- **Bid-type semantics differ** from F-21 (see "Out of scope"). Treat `bid_type` as opaque int
  unless you've cross-checked against an xlsx export.
