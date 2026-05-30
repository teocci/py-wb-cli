"""Tests for the cmp.wildberries.ru campaign-finance ledger surface — I-24.

Covers the new ``PortalClient.list_campaign_finance`` /
``download_campaign_finance_xlsx`` methods, the ``PortalCampaignFinanceService``
orchestrator (page + auto-paginate-all), the ``CampaignFinanceEntry`` /
``CampaignFinancePage`` dataclasses, and the ``wb portal campaign`` CLI.

Also asserts that the ``_get_bytes`` refactor (added in I-24 to support an
``include_auth`` flag and query params) did not break the existing Jam CDN
download path.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import httpx
import pytest
import respx
from typer.testing import CliRunner

from wb.cli.portal import portal_app
from wb.client.portal import PortalClient
from wb.core.constants import (
    DOWNLOADS_CONTENT_ANALYTICS_BASE_URL,
    EP_PORTAL_JAM_FILE,
    EP_PORTAL_TOKENS_JRPC,
    EP_PORTAL_UPD_LIST,
    EP_PORTAL_UPD_XLSX,
    SELLER_CONTENT_BASE_URL,
    WB_CMP_BASE_URL,
)
from wb.core.exceptions import ApiError, AuthenticationError
from wb.domain.models import CampaignFinanceEntry, CampaignFinancePage
from wb.services.portal_campaign_finance import (
    PortalCampaignFinanceService,
    default_filename,
    format_msk_datetime,
)

LIST_URL = f'{WB_CMP_BASE_URL}{EP_PORTAL_UPD_LIST}'
XLSX_URL = f'{WB_CMP_BASE_URL}{EP_PORTAL_UPD_XLSX}'
TOKENS_JRPC_URL = f'{SELLER_CONTENT_BASE_URL}{EP_PORTAL_TOKENS_JRPC}'
JAM_DOWNLOAD_URL_BASE = f'{DOWNLOADS_CONTENT_ANALYTICS_BASE_URL}{EP_PORTAL_JAM_FILE}'


# ── Helpers ──────────────────────────────────────────────────────────


def _make_client() -> PortalClient:
    return PortalClient(authorizev3='auth-v3-key', cookie='c=1')


def _sample_row(**overrides) -> dict:
    base = {
        'upd_num': 0,
        'upd_time': '2026-05-29T23:59:59+03:00',
        'upd_sum': 186,
        'advert_id': 35916291,
        'camp_name': 'WB 265811162 | Ед',
        'bid_type': 1,
        'advert_type': '',
        'payment_type': 'Баланс',
        'payment_type_id': 1,
        'advert_status': '9',
        'category_uid': '66666666-6666-6666-6666-666666666666',
        'time': '2026-04-28T00:07:41.274339Z',
        'payment_model': 'cpm',
        'source_service_id': 3,
        'is_autorefill': True,
    }
    base.update(overrides)
    return base


def _sample_response(rows: list[dict], *, total_count: int | None = None,
                     total_amount: int | None = None) -> dict:
    return {
        'upd_total_amount': total_amount if total_amount is not None else sum(r['upd_sum'] for r in rows),
        'total_count': total_count if total_count is not None else len(rows),
        'upd_info': rows,
    }


# ── CampaignFinanceEntry dataclass ───────────────────────────────────


class TestCampaignFinanceEntryFromApi:
    def test_full_payload(self):
        entry = CampaignFinanceEntry.from_api(_sample_row())
        assert entry.advert_id == 35916291
        assert entry.camp_name == 'WB 265811162 | Ед'
        assert entry.upd_sum == 186
        assert entry.bid_type == 1
        assert entry.payment_type == 'Баланс'
        assert entry.payment_model == 'cpm'
        assert entry.is_autorefill is True
        assert entry.booked_time == '2026-04-28T00:07:41.274339Z'

    def test_missing_keys_default(self):
        entry = CampaignFinanceEntry.from_api({})
        assert entry.advert_id == 0
        assert entry.camp_name == ''
        assert entry.upd_sum == 0
        assert entry.is_autorefill is False

    def test_null_numeric_fields_coerced(self):
        entry = CampaignFinanceEntry.from_api({'advert_id': None, 'upd_sum': None, 'bid_type': None})
        assert entry.advert_id == 0
        assert entry.upd_sum == 0
        assert entry.bid_type == 0


class TestCampaignFinancePageFromApi:
    def test_parses_rows_and_totals(self):
        page = CampaignFinancePage.from_api(
            _sample_response([_sample_row(), _sample_row(upd_sum=10, advert_id=2)]),
            page_number=1, page_size=10,
        )
        assert len(page.entries) == 2
        assert page.upd_total_amount == 196
        assert page.total_count == 2
        assert page.page_number == 1
        assert page.page_size == 10

    def test_handles_missing_upd_info(self):
        page = CampaignFinancePage.from_api(
            {'upd_total_amount': 0, 'total_count': 0},
            page_number=1, page_size=10,
        )
        assert page.entries == []

    def test_skips_non_dict_rows(self):
        page = CampaignFinancePage.from_api(
            {'upd_info': [_sample_row(), 'garbage', None]},
            page_number=1, page_size=10,
        )
        assert len(page.entries) == 1


# ── Helpers (format_msk_datetime, default_filename) ──────────────────


class TestFormatMskDatetime:
    def test_single_day(self):
        assert format_msk_datetime(date(2026, 5, 29)) == '2026-05-29T00:00:00+03:00'

    def test_zero_padding(self):
        assert format_msk_datetime(date(2026, 1, 5)) == '2026-01-05T00:00:00+03:00'


class TestDefaultFilename:
    def test_single_day(self):
        assert default_filename(date(2026, 5, 11), date(2026, 5, 11)) == 'campaign-finance_2026-05-11.xlsx'

    def test_range(self):
        assert default_filename(date(2026, 5, 11), date(2026, 5, 13)) == 'campaign-finance_2026-05-11_2026-05-13.xlsx'


# ── PortalClient.list_campaign_finance ───────────────────────────────


class TestListCampaignFinance:
    def test_sends_correct_params_and_headers(self):
        captured: dict = {}

        def _capture(request: httpx.Request) -> httpx.Response:
            captured['params'] = dict(request.url.params)
            captured['headers'] = dict(request.headers)
            return httpx.Response(200, json=_sample_response([_sample_row()]))

        with respx.mock:
            respx.get(LIST_URL).mock(side_effect=_capture)
            client = _make_client()
            result = client.list_campaign_finance(
                '2026-05-29T00:00:00+03:00',
                '2026-05-29T00:00:00+03:00',
                page_number=1, page_size=10,
            )

        assert result['total_count'] == 1
        assert captured['params'] == {
            'page_number': '1',
            'page_size': '10',
            'bid_type': '[0]',
            'attribute': 'all',
            'from': '2026-05-29T00:00:00+03:00',
            'to': '2026-05-29T00:00:00+03:00',
        }
        assert captured['headers']['authorizev3'] == 'auth-v3-key'
        assert captured['headers']['cookie'] == 'c=1'
        assert captured['headers']['origin'] == WB_CMP_BASE_URL
        assert 'campaigns/finances' in captured['headers']['referer']

    def test_401_raises_authentication_error(self):
        with respx.mock:
            respx.get(LIST_URL).mock(return_value=httpx.Response(401, text='nope'))
            client = _make_client()
            with pytest.raises(AuthenticationError):
                client.list_campaign_finance(
                    '2026-05-29T00:00:00+03:00',
                    '2026-05-29T00:00:00+03:00',
                )

    def test_500_raises_api_error(self):
        with respx.mock:
            respx.get(LIST_URL).mock(return_value=httpx.Response(500, text='boom'))
            client = _make_client()
            with pytest.raises(ApiError):
                client.list_campaign_finance(
                    '2026-05-29T00:00:00+03:00',
                    '2026-05-29T00:00:00+03:00',
                )

    def test_non_dict_payload_raises_api_error(self):
        with respx.mock:
            respx.get(LIST_URL).mock(return_value=httpx.Response(200, json=[]))
            client = _make_client()
            with pytest.raises(ApiError, match='Unexpected'):
                client.list_campaign_finance(
                    '2026-05-29T00:00:00+03:00',
                    '2026-05-29T00:00:00+03:00',
                )


# ── PortalClient.download_campaign_finance_xlsx ──────────────────────


class TestDownloadCampaignFinanceXlsx:
    def test_sends_auth_header_and_params(self):
        captured: dict = {}

        def _capture(request: httpx.Request) -> httpx.Response:
            captured['params'] = dict(request.url.params)
            captured['headers'] = dict(request.headers)
            return httpx.Response(
                200, content=b'PK\x03\x04xlsx-bytes',
            )

        with respx.mock:
            respx.get(XLSX_URL).mock(side_effect=_capture)
            client = _make_client()
            content = client.download_campaign_finance_xlsx(
                '2026-05-29T00:00:00+03:00',
                '2026-05-29T00:00:00+03:00',
            )

        assert content == b'PK\x03\x04xlsx-bytes'
        # cmp host expects authorizev3 — unlike the jam CDN
        assert captured['headers']['authorizev3'] == 'auth-v3-key'
        assert captured['headers']['cookie'] == 'c=1'
        assert captured['headers']['origin'] == WB_CMP_BASE_URL
        assert 'x-download-token' not in captured['headers']
        assert captured['params'] == {
            'bid_type': '[0]',
            'from': '2026-05-29T00:00:00+03:00',
            'to': '2026-05-29T00:00:00+03:00',
            'pageNumber': '1',
            'pageSize': '10',
        }

    def test_401_raises_authentication_error(self):
        with respx.mock:
            respx.get(XLSX_URL).mock(return_value=httpx.Response(401, text='nope'))
            client = _make_client()
            with pytest.raises(AuthenticationError):
                client.download_campaign_finance_xlsx(
                    '2026-05-29T00:00:00+03:00',
                    '2026-05-29T00:00:00+03:00',
                )


# ── _get_bytes refactor regression — Jam CDN path ─────────────────────


class TestJamDownloadStillOmitsAuthorizev3:
    """Regression for the I-24 _get_bytes refactor.

    The Jam downloads CDN (downloads-content-analytics.wildberries.ru) rejects
    the ``authorizev3`` header. After adding ``include_auth=True`` as the
    default, ``download_jam_file`` must explicitly pass ``include_auth=False``.
    """

    def test_jam_download_does_not_send_authorizev3(self):
        captured: dict = {}

        def _capture(request: httpx.Request) -> httpx.Response:
            captured['headers'] = dict(request.headers)
            return httpx.Response(200, content=b'zip')

        with respx.mock:
            respx.post(TOKENS_JRPC_URL).mock(return_value=httpx.Response(
                200, json={'id': 'json-rpc_1', 'jsonrpc': '2.0', 'result': {'token': 'tok'}},
            ))
            respx.get(f'{JAM_DOWNLOAD_URL_BASE}/abc-id').mock(side_effect=_capture)
            client = _make_client()
            client.download_jam_file('abc-id')

        assert 'authorizev3' not in captured['headers']
        assert captured['headers']['x-download-token'] == 'tok'
        assert captured['headers']['cookie'] == 'c=1'


# ── PortalCampaignFinanceService ─────────────────────────────────────


class TestServiceListPage:
    def test_calls_client_with_formatted_dates(self):
        client = MagicMock(spec=PortalClient)
        client.list_campaign_finance.return_value = _sample_response([_sample_row()])
        service = PortalCampaignFinanceService(client)

        page = service.list_page(
            date(2026, 5, 11), date(2026, 5, 11),
            page_number=2, page_size=50,
        )

        client.list_campaign_finance.assert_called_once_with(
            '2026-05-11T00:00:00+03:00',
            '2026-05-11T00:00:00+03:00',
            page_number=2, page_size=50,
        )
        assert page.page_number == 2
        assert page.page_size == 50
        assert page.total_count == 1


class TestServiceListAll:
    def test_walks_until_short_page(self):
        client = MagicMock(spec=PortalClient)
        client.list_campaign_finance.side_effect = [
            _sample_response(
                [_sample_row(advert_id=i) for i in range(100)],
                total_count=140, total_amount=999,
            ),
            _sample_response(
                [_sample_row(advert_id=i) for i in range(100, 140)],
                total_count=140, total_amount=999,
            ),
        ]
        service = PortalCampaignFinanceService(client)

        page = service.list_all(date(2026, 5, 29), date(2026, 5, 29), page_size=100)

        assert client.list_campaign_finance.call_count == 2
        assert len(page.entries) == 140
        assert page.total_count == 140
        assert page.upd_total_amount == 999
        assert page.page_number == 1
        assert page.page_size == 140  # combined entry count

    def test_single_page_exact_total(self):
        client = MagicMock(spec=PortalClient)
        client.list_campaign_finance.return_value = _sample_response(
            [_sample_row(advert_id=i) for i in range(5)], total_count=5, total_amount=100,
        )
        service = PortalCampaignFinanceService(client)

        page = service.list_all(date(2026, 5, 11), date(2026, 5, 11), page_size=100)

        assert client.list_campaign_finance.call_count == 1
        assert len(page.entries) == 5
        assert page.upd_total_amount == 100

    def test_empty_response(self):
        client = MagicMock(spec=PortalClient)
        client.list_campaign_finance.return_value = _sample_response(
            [], total_count=0, total_amount=0,
        )
        service = PortalCampaignFinanceService(client)

        page = service.list_all(date(2026, 5, 11), date(2026, 5, 11), page_size=100)

        assert client.list_campaign_finance.call_count == 1
        assert page.entries == []
        assert page.total_count == 0
        assert page.page_size == 100  # falls back to per-page size

    def test_stops_when_total_reached_even_with_full_page(self):
        # Defensive: WB returns exactly total_count over pages without trailing short page.
        client = MagicMock(spec=PortalClient)
        client.list_campaign_finance.return_value = _sample_response(
            [_sample_row(advert_id=i) for i in range(5)], total_count=5, total_amount=42,
        )
        service = PortalCampaignFinanceService(client)

        page = service.list_all(date(2026, 5, 11), date(2026, 5, 11), page_size=5)

        assert client.list_campaign_finance.call_count == 1
        assert len(page.entries) == 5


class TestServiceDownloadXlsx:
    def test_calls_client(self):
        client = MagicMock(spec=PortalClient)
        client.download_campaign_finance_xlsx.return_value = b'xlsx'
        service = PortalCampaignFinanceService(client)

        content = service.download_xlsx(date(2026, 5, 11), date(2026, 5, 12))

        assert content == b'xlsx'
        client.download_campaign_finance_xlsx.assert_called_once_with(
            '2026-05-11T00:00:00+03:00',
            '2026-05-12T00:00:00+03:00',
        )


# ── CLI integration ──────────────────────────────────────────────────


class TestCliFinance:
    def _fake_page(self, n_rows: int = 2) -> CampaignFinancePage:
        return CampaignFinancePage(
            entries=[CampaignFinanceEntry.from_api(_sample_row(advert_id=i)) for i in range(n_rows)],
            upd_total_amount=999,
            total_count=n_rows,
            page_number=1,
            page_size=max(n_rows, 1),
        )

    def test_table_mode_renders_summary_and_rows(self, monkeypatch):
        fake_service = MagicMock()
        fake_service.list_all.return_value = self._fake_page(2)
        monkeypatch.setattr(
            'wb.cli.portal._get_campaign_finance_service',
            lambda profile: fake_service,
        )

        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['campaign', 'finance', '--from', '2026-05-11'],
            obj={'json_output': False, 'profile': None},
        )

        assert result.exit_code == 0, result.output
        assert 'Total' in result.output
        assert '999' in result.output
        fake_service.list_all.assert_called_once()
        fake_service.list_page.assert_not_called()

    def test_page_flag_uses_list_page(self, monkeypatch):
        fake_service = MagicMock()
        fake_service.list_page.return_value = self._fake_page(1)
        monkeypatch.setattr(
            'wb.cli.portal._get_campaign_finance_service',
            lambda profile: fake_service,
        )

        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['campaign', 'finance', '--from', '2026-05-11', '--page', '2', '--page-size', '5'],
            obj={'json_output': False, 'profile': None},
        )

        assert result.exit_code == 0, result.output
        fake_service.list_page.assert_called_once()
        kwargs = fake_service.list_page.call_args.kwargs
        assert kwargs['page_number'] == 2
        assert kwargs['page_size'] == 5
        fake_service.list_all.assert_not_called()

    def test_json_mode_emits_entries_and_summary(self, monkeypatch):
        import json
        fake_service = MagicMock()
        fake_service.list_all.return_value = self._fake_page(1)
        monkeypatch.setattr(
            'wb.cli.portal._get_campaign_finance_service',
            lambda profile: fake_service,
        )

        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['campaign', 'finance', '--from', '2026-05-11'],
            obj={'json_output': True, 'profile': None},
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload['total_count'] == 1
        assert payload['upd_total_amount'] == 999
        assert len(payload['entries']) == 1
        assert payload['entries'][0]['advert_id'] == 0  # sample_row default with id=0

    def test_rejects_inverted_range(self):
        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['campaign', 'finance', '--from', '2026-05-11', '--to', '2026-05-10'],
            obj={'json_output': False, 'profile': None},
        )
        assert result.exit_code != 0
        assert '--to' in result.output

    def test_rejects_invalid_date(self):
        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['campaign', 'finance', '--from', 'nope'],
            obj={'json_output': False, 'profile': None},
        )
        assert result.exit_code != 0
        assert 'YYYY-MM-DD' in result.output


class TestCliFinanceXlsx:
    def test_writes_xlsx_to_disk(self, tmp_path, monkeypatch):
        fake_service = MagicMock()
        fake_service.download_xlsx.return_value = b'PK\x03\x04workbook'
        monkeypatch.setattr(
            'wb.cli.portal._get_campaign_finance_service',
            lambda profile: fake_service,
        )

        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['campaign', 'finance-xlsx', '--from', '2026-05-11', '-o', str(tmp_path)],
            obj={'json_output': False, 'profile': None},
        )

        assert result.exit_code == 0, result.output
        out_file = tmp_path / 'campaign-finance_2026-05-11.xlsx'
        assert out_file.exists()
        assert out_file.read_bytes() == b'PK\x03\x04workbook'
        assert 'Saved' in result.output

    def test_directory_target_appends_default_name(self, tmp_path, monkeypatch):
        fake_service = MagicMock()
        fake_service.download_xlsx.return_value = b'xlsx-bytes'
        monkeypatch.setattr(
            'wb.cli.portal._get_campaign_finance_service',
            lambda profile: fake_service,
        )

        sub = tmp_path / 'sub'
        sub.mkdir()
        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            [
                'campaign', 'finance-xlsx',
                '--from', '2026-05-11', '--to', '2026-05-13',
                '-o', str(sub),
            ],
            obj={'json_output': False, 'profile': None},
        )

        assert result.exit_code == 0, result.output
        assert (sub / 'campaign-finance_2026-05-11_2026-05-13.xlsx').exists()

    def test_json_mode_emits_metadata(self, tmp_path, monkeypatch):
        import json
        fake_service = MagicMock()
        fake_service.download_xlsx.return_value = b'01234567'
        monkeypatch.setattr(
            'wb.cli.portal._get_campaign_finance_service',
            lambda profile: fake_service,
        )

        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['campaign', 'finance-xlsx', '--from', '2026-05-11', '-o', str(tmp_path)],
            obj={'json_output': True, 'profile': None},
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload['byte_size'] == 8
        assert payload['from'] == '2026-05-11'
        assert payload['to'] == '2026-05-11'
        assert payload['saved_path'].endswith('campaign-finance_2026-05-11.xlsx')

    def test_rejects_invalid_date(self):
        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['campaign', 'finance-xlsx', '--from', 'not-a-date'],
            obj={'json_output': False, 'profile': None},
        )
        assert result.exit_code != 0
        assert 'YYYY-MM-DD' in result.output
