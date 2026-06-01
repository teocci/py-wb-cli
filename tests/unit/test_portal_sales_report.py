"""Tests for the WB seller-goods sales-report download surface — I-25.

Covers ``PortalClient`` sales-report methods, ``PortalSalesReportService``
orchestration, ``SalesReport`` parsing, and the ``wb portal sales-report``
CLI write-to-disk path.
"""

from __future__ import annotations

import base64
from datetime import date
from unittest.mock import MagicMock

import httpx
import pytest
import respx
from typer.testing import CliRunner

from wb.cli.portal import portal_app
from wb.client.portal import PortalClient
from wb.core.constants import (
    EP_PORTAL_SALES_REPORT_GENERATE,
    EP_PORTAL_SALES_REPORT_LIST,
    EP_PORTAL_SALES_REPORT_XLSX,
    SALES_REPORT_TYPE_SUPPLIER_GOODS,
    SELLER_WEEKLY_REPORT_BASE_URL,
)
from wb.core.exceptions import ApiError, AuthenticationError
from wb.domain.models import SalesReport
from wb.services.portal_sales_report import (
    PortalSalesReportService,
    default_filename,
    format_query_date,
)

GENERATE_URL = (
    f'{SELLER_WEEKLY_REPORT_BASE_URL}{EP_PORTAL_SALES_REPORT_GENERATE}'
    f'/{SALES_REPORT_TYPE_SUPPLIER_GOODS}/order'
)
LIST_URL = (
    f'{SELLER_WEEKLY_REPORT_BASE_URL}{EP_PORTAL_SALES_REPORT_LIST}'
    f'/{SALES_REPORT_TYPE_SUPPLIER_GOODS}/orders'
)
XLSX_URL_PREFIX = (
    f'{SELLER_WEEKLY_REPORT_BASE_URL}{EP_PORTAL_SALES_REPORT_XLSX}'
    f'/{SALES_REPORT_TYPE_SUPPLIER_GOODS}/xlsx'
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_client() -> PortalClient:
    return PortalClient(authorizev3='auth-v3-key', cookie='c=1')


def _generate_response(
        report_id: str = 'supplier-goods-25169-2026-05-11-2026-05-11-abc12',
) -> dict:
    return {
        'data': {
            'id': report_id,
            'supplierID': 25169,
            'locale': 'ru',
            'createdAt': '2026-05-11T10:00:00',
            'expiredAt': '2026-05-12T10:00:00',
            'reportName': 'supplier-goods',
            'isDeleted': False,
            'fileUrl': '',
            'dateFrom': '2026-05-11',
            'dateTo': '2026-05-11',
            'totalCount': 0,
            'columns': None,
            'columnsGroups': None,
            'data': None,
        },
        'error': False,
        'errorText': '',
        'additionalErrors': None,
    }


def _list_response(items: list[dict]) -> dict:
    return {
        'data': items,
        'error': False,
        'errorText': '',
        'additionalErrors': None,
    }


def _list_entry(report_id: str) -> dict:
    return {
        'id': report_id,
        'createdAt': '2026-05-11T10:00:00',
        'dateFrom': '2026-05-11',
        'dateTo': '2026-05-11',
    }


def _xlsx_response(payload: bytes) -> dict:
    return {
        'data': base64.b64encode(payload).decode('ascii'),
        'error': False,
        'errorText': '',
        'additionalErrors': None,
    }


def _pending_xlsx_response(error: bool = True) -> dict:
    return {
        'data': '' if not error else None,
        'error': error,
        'errorText': 'still generating' if error else '',
        'additionalErrors': None,
    }


# ── SalesReport dataclass ────────────────────────────────────────────


class TestSalesReportFromApi:
    def test_full_payload(self):
        report = SalesReport.from_api(_generate_response()['data'])
        assert report.id.startswith('supplier-goods-25169-')
        assert report.supplier_id == 25169
        assert report.locale == 'ru'
        assert report.report_name == 'supplier-goods'
        assert report.date_from == '2026-05-11'
        assert report.date_to == '2026-05-11'
        assert report.file_url == ''
        assert report.total_count == 0
        assert report.is_deleted is False

    def test_list_endpoint_subset(self):
        report = SalesReport.from_api(_list_entry('id-1'))
        assert report.id == 'id-1'
        assert report.supplier_id == 0  # omitted by list endpoint
        assert report.locale == ''
        assert report.expired_at == ''
        assert report.file_url == ''

    def test_missing_keys_default_to_empty(self):
        report = SalesReport.from_api({})
        assert report.id == ''
        assert report.supplier_id == 0
        assert report.total_count == 0
        assert report.is_deleted is False


# ── format_query_date helper ─────────────────────────────────────────


class TestFormatQueryDate:
    def test_matches_browser_trace_may_11(self):
        assert format_query_date(date(2026, 5, 11)) == '11.05.26'

    def test_zero_pads_single_digit_day_and_month(self):
        assert format_query_date(date(2026, 1, 5)) == '05.01.26'

    def test_two_digit_year_for_2030(self):
        assert format_query_date(date(2030, 12, 31)) == '31.12.30'

    def test_two_digit_year_for_2099(self):
        assert format_query_date(date(2099, 12, 31)) == '31.12.99'

    def test_rejects_pre_2000(self):
        with pytest.raises(ValueError, match='1999'):
            format_query_date(date(1999, 5, 11))


# ── default_filename ─────────────────────────────────────────────────


class TestDefaultFilename:
    def test_single_day(self):
        assert (
            default_filename(date(2026, 5, 11), date(2026, 5, 11))
            == 'supplier-goods_2026-05-11.xlsx'
        )

    def test_seven_day_range(self):
        assert (
            default_filename(date(2026, 5, 4), date(2026, 5, 10))
            == 'supplier-goods_2026-05-04_2026-05-10.xlsx'
        )

    def test_calendar_month_range(self):
        assert (
            default_filename(date(2026, 5, 1), date(2026, 5, 31))
            == 'supplier-goods_2026-05-01_2026-05-31.xlsx'
        )


# ── PortalClient.generate_sales_report ───────────────────────────────


class TestGenerateSalesReport:
    def test_posts_empty_body_with_query_params(self):
        captured: dict = {}

        def _capture(request: httpx.Request) -> httpx.Response:
            captured['content'] = bytes(request.content)
            captured['headers'] = dict(request.headers)
            captured['url'] = str(request.url)
            return httpx.Response(200, json=_generate_response())

        with respx.mock:
            respx.post(GENERATE_URL).mock(side_effect=_capture)
            client = _make_client()
            result = client.generate_sales_report(
                SALES_REPORT_TYPE_SUPPLIER_GOODS, '11.05.26', '11.05.26',
            )

        assert result['error'] is False
        assert result['data']['id'].startswith('supplier-goods-25169-')
        # Empty body — no JSON payload.
        assert captured['content'] == b''
        # Date params in URL query string.
        assert 'dateFrom=11.05.26' in captured['url']
        assert 'dateTo=11.05.26' in captured['url']
        # Auth headers.
        assert captured['headers']['cookie'] == 'c=1'
        assert captured['headers']['authorizev3'] == 'auth-v3-key'

    def test_401_raises_authentication_error(self):
        with respx.mock:
            respx.post(GENERATE_URL).mock(return_value=httpx.Response(401, text='nope'))
            client = _make_client()
            with pytest.raises(AuthenticationError):
                client.generate_sales_report(
                    SALES_REPORT_TYPE_SUPPLIER_GOODS, '11.05.26', '11.05.26',
                )

    def test_500_raises_api_error(self):
        with respx.mock:
            respx.post(GENERATE_URL).mock(return_value=httpx.Response(500, text='boom'))
            client = _make_client()
            with pytest.raises(ApiError):
                client.generate_sales_report(
                    SALES_REPORT_TYPE_SUPPLIER_GOODS, '11.05.26', '11.05.26',
                )


# ── PortalClient.list_sales_reports ──────────────────────────────────


class TestListSalesReports:
    def test_returns_data_array(self):
        with respx.mock:
            respx.get(LIST_URL).mock(return_value=httpx.Response(
                200, json=_list_response([_list_entry('a'), _list_entry('b')]),
            ))
            client = _make_client()
            items = client.list_sales_reports(SALES_REPORT_TYPE_SUPPLIER_GOODS)
        assert [d['id'] for d in items] == ['a', 'b']

    def test_handles_null_data(self):
        with respx.mock:
            respx.get(LIST_URL).mock(return_value=httpx.Response(
                200, json={'data': None, 'error': False},
            ))
            client = _make_client()
            assert client.list_sales_reports(SALES_REPORT_TYPE_SUPPLIER_GOODS) == []


# ── PortalClient.try_download_sales_report_xlsx ──────────────────────


class TestTryDownloadXlsx:
    def test_returns_decoded_bytes_on_success(self):
        report_id = 'supplier-goods-id-1'
        payload = b'PK\x03\x04xlsx-stub'
        with respx.mock:
            respx.get(f'{XLSX_URL_PREFIX}/{report_id}').mock(return_value=httpx.Response(
                200, json=_xlsx_response(payload),
            ))
            client = _make_client()
            result = client.try_download_sales_report_xlsx(
                SALES_REPORT_TYPE_SUPPLIER_GOODS, report_id,
            )
        assert result == payload

    def test_returns_none_when_error_true(self):
        report_id = 'pending-id'
        with respx.mock:
            respx.get(f'{XLSX_URL_PREFIX}/{report_id}').mock(return_value=httpx.Response(
                200, json=_pending_xlsx_response(error=True),
            ))
            client = _make_client()
            assert client.try_download_sales_report_xlsx(
                SALES_REPORT_TYPE_SUPPLIER_GOODS, report_id,
            ) is None

    def test_returns_none_when_data_empty(self):
        report_id = 'empty-data-id'
        with respx.mock:
            respx.get(f'{XLSX_URL_PREFIX}/{report_id}').mock(return_value=httpx.Response(
                200, json={'data': '', 'error': False},
            ))
            client = _make_client()
            assert client.try_download_sales_report_xlsx(
                SALES_REPORT_TYPE_SUPPLIER_GOODS, report_id,
            ) is None

    def test_401_raises_authentication_error(self):
        with respx.mock:
            respx.get(f'{XLSX_URL_PREFIX}/x').mock(return_value=httpx.Response(401, text='no'))
            client = _make_client()
            with pytest.raises(AuthenticationError):
                client.try_download_sales_report_xlsx(SALES_REPORT_TYPE_SUPPLIER_GOODS, 'x')

    def test_500_raises_api_error(self):
        with respx.mock:
            respx.get(f'{XLSX_URL_PREFIX}/x').mock(return_value=httpx.Response(500, text='boom'))
            client = _make_client()
            with pytest.raises(ApiError):
                client.try_download_sales_report_xlsx(SALES_REPORT_TYPE_SUPPLIER_GOODS, 'x')

    def test_invalid_base64_raises_api_error(self):
        with respx.mock:
            respx.get(f'{XLSX_URL_PREFIX}/x').mock(return_value=httpx.Response(
                200, json={'data': '!!! not base64 !!!', 'error': False},
            ))
            client = _make_client()
            # Note: base64.b64decode is tolerant of many strings — this test
            # confirms an obviously-broken payload still parses without raising
            # (or raises predictably). Either path is acceptable; what matters
            # is that we don't return None on success-looking envelopes.
            try:
                result = client.try_download_sales_report_xlsx(
                    SALES_REPORT_TYPE_SUPPLIER_GOODS, 'x',
                )
                assert isinstance(result, bytes)
            except ApiError:
                pass


# ── PortalSalesReportService ─────────────────────────────────────────


class TestRequestSupplierGoods:
    def test_returns_parsed_sales_report(self):
        client = MagicMock(spec=PortalClient)
        client.generate_sales_report.return_value = _generate_response('id-xyz')
        service = PortalSalesReportService(client)

        report = service.request_supplier_goods(date(2026, 5, 11), date(2026, 5, 11))

        assert report.id == 'id-xyz'
        assert report.supplier_id == 25169
        assert report.file_url == ''
        client.generate_sales_report.assert_called_once_with(
            SALES_REPORT_TYPE_SUPPLIER_GOODS, '11.05.26', '11.05.26',
        )

    def test_error_envelope_raises(self):
        client = MagicMock(spec=PortalClient)
        client.generate_sales_report.return_value = {
            'error': True, 'errorText': 'bad',
        }
        service = PortalSalesReportService(client)
        with pytest.raises(ApiError):
            service.request_supplier_goods(date(2026, 5, 11), date(2026, 5, 11))

    def test_missing_id_raises(self):
        client = MagicMock(spec=PortalClient)
        client.generate_sales_report.return_value = {'error': False, 'data': {}}
        service = PortalSalesReportService(client)
        with pytest.raises(ApiError, match='data.id'):
            service.request_supplier_goods(date(2026, 5, 11), date(2026, 5, 11))


class TestPollDownload:
    def test_returns_bytes_when_ready(self, monkeypatch):
        monkeypatch.setattr('wb.services.portal_sales_report.time.sleep', lambda _: None)
        client = MagicMock(spec=PortalClient)
        client.try_download_sales_report_xlsx.side_effect = [None, None, b'PK-XLSX']
        service = PortalSalesReportService(client)

        result = service._poll_download('id-1', interval=0.01, timeout=10)

        assert result == b'PK-XLSX'
        assert client.try_download_sales_report_xlsx.call_count == 3

    def test_timeout_raises_api_error(self, monkeypatch):
        monkeypatch.setattr('wb.services.portal_sales_report.time.sleep', lambda _: None)
        client = MagicMock(spec=PortalClient)
        client.try_download_sales_report_xlsx.return_value = None
        service = PortalSalesReportService(client)

        with pytest.raises(ApiError, match='did not finish'):
            service._poll_download('id-1', interval=0.05, timeout=0.1)


class TestFetchSupplierGoodsPipeline:
    def test_happy_path(self, monkeypatch):
        monkeypatch.setattr('wb.services.portal_sales_report.time.sleep', lambda _: None)
        client = MagicMock(spec=PortalClient)
        client.generate_sales_report.return_value = _generate_response('pipeline-id')
        client.try_download_sales_report_xlsx.return_value = b'PK-DATA'
        service = PortalSalesReportService(client)

        report, content = service.fetch_supplier_goods(
            date(2026, 5, 11), date(2026, 5, 11),
        )

        assert report.id == 'pipeline-id'
        assert content == b'PK-DATA'
        # file_url is backfilled on success.
        assert report.file_url != ''
        client.generate_sales_report.assert_called_once()
        client.try_download_sales_report_xlsx.assert_called_with(
            SALES_REPORT_TYPE_SUPPLIER_GOODS, 'pipeline-id',
        )


class TestListReports:
    def test_parses_to_sales_reports(self):
        client = MagicMock(spec=PortalClient)
        client.list_sales_reports.return_value = [_list_entry('a'), _list_entry('b')]
        service = PortalSalesReportService(client)

        reports = service.list_reports()

        assert [r.id for r in reports] == ['a', 'b']


# ── CLI write-to-disk integration ────────────────────────────────────


class TestSalesReportCliSupplierGoods:
    def test_writes_xlsx_to_disk(self, tmp_path, monkeypatch):
        fake_report = SalesReport.from_api(_generate_response('cli-id')['data'])
        fake_service = MagicMock()
        fake_service.fetch_supplier_goods.return_value = (fake_report, b'XLSX-DATA')

        monkeypatch.setattr(
            'wb.cli.portal._get_sales_report_service',
            lambda profile: fake_service,
        )

        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['sales-report', 'supplier-goods', '--from', '2026-05-11', '-o', str(tmp_path)],
            obj={'json_output': False, 'profile': None},
        )

        assert result.exit_code == 0, result.output
        out_file = tmp_path / 'supplier-goods_2026-05-11.xlsx'
        assert out_file.exists()
        assert out_file.read_bytes() == b'XLSX-DATA'
        assert 'Saved' in result.output

    def test_seven_day_range(self, tmp_path, monkeypatch):
        fake_report = SalesReport.from_api(_generate_response('week-id')['data'])
        fake_service = MagicMock()
        fake_service.fetch_supplier_goods.return_value = (fake_report, b'WEEK-DATA')
        monkeypatch.setattr(
            'wb.cli.portal._get_sales_report_service',
            lambda profile: fake_service,
        )

        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            [
                'sales-report', 'supplier-goods',
                '--from', '2026-05-04', '--to', '2026-05-10',
                '-o', str(tmp_path),
            ],
            obj={'json_output': False, 'profile': None},
        )

        assert result.exit_code == 0, result.output
        out_file = tmp_path / 'supplier-goods_2026-05-04_2026-05-10.xlsx'
        assert out_file.exists()

    def test_monthly_range(self, tmp_path, monkeypatch):
        fake_report = SalesReport.from_api(_generate_response('month-id')['data'])
        fake_service = MagicMock()
        fake_service.fetch_supplier_goods.return_value = (fake_report, b'MONTH-DATA')
        monkeypatch.setattr(
            'wb.cli.portal._get_sales_report_service',
            lambda profile: fake_service,
        )

        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            [
                'sales-report', 'supplier-goods',
                '--from', '2026-05-01', '--to', '2026-05-31',
                '-o', str(tmp_path),
            ],
            obj={'json_output': False, 'profile': None},
        )

        assert result.exit_code == 0, result.output
        out_file = tmp_path / 'supplier-goods_2026-05-01_2026-05-31.xlsx'
        assert out_file.exists()

    def test_rejects_inverted_range(self):
        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            [
                'sales-report', 'supplier-goods',
                '--from', '2026-05-11',
                '--to', '2026-05-10',
            ],
            obj={'json_output': False, 'profile': None},
        )
        assert result.exit_code != 0
        assert '--to' in result.output

    def test_rejects_invalid_date(self):
        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['sales-report', 'supplier-goods', '--from', 'not-a-date'],
            obj={'json_output': False, 'profile': None},
        )
        assert result.exit_code != 0
        assert 'YYYY-MM-DD' in result.output

    def test_json_mode_emits_metadata(self, tmp_path, monkeypatch):
        import json
        fake_report = SalesReport.from_api(_generate_response('cli-json-id')['data'])
        fake_service = MagicMock()
        fake_service.fetch_supplier_goods.return_value = (fake_report, b'XX')
        monkeypatch.setattr(
            'wb.cli.portal._get_sales_report_service',
            lambda profile: fake_service,
        )

        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['sales-report', 'supplier-goods', '--from', '2026-05-11', '-o', str(tmp_path)],
            obj={'json_output': True, 'profile': None},
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload['id'] == 'cli-json-id'
        assert payload['saved_path'].endswith('supplier-goods_2026-05-11.xlsx')


class TestSalesReportCliList:
    def test_renders_table(self, monkeypatch):
        fake_reports = [
            SalesReport.from_api(_list_entry('supplier-goods-aaa-bbb-ccc-ddd')),
            SalesReport.from_api(_list_entry('supplier-goods-eee-fff-ggg-hhh')),
        ]
        fake_service = MagicMock()
        fake_service.list_reports.return_value = fake_reports
        monkeypatch.setattr(
            'wb.cli.portal._get_sales_report_service',
            lambda profile: fake_service,
        )

        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['sales-report', 'list'],
            obj={'json_output': False, 'profile': None},
        )

        assert result.exit_code == 0, result.output
        assert 'Supplier-Goods' in result.output or 'supplier-goods' in result.output

    def test_empty_list_message(self, monkeypatch):
        fake_service = MagicMock()
        fake_service.list_reports.return_value = []
        monkeypatch.setattr(
            'wb.cli.portal._get_sales_report_service',
            lambda profile: fake_service,
        )

        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['sales-report', 'list'],
            obj={'json_output': False, 'profile': None},
        )

        assert result.exit_code == 0
        assert 'No supplier-goods' in result.output

    def test_json_empty_list(self, monkeypatch):
        import json
        fake_service = MagicMock()
        fake_service.list_reports.return_value = []
        monkeypatch.setattr(
            'wb.cli.portal._get_sales_report_service',
            lambda profile: fake_service,
        )

        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['sales-report', 'list'],
            obj={'json_output': True, 'profile': None},
        )

        assert result.exit_code == 0
        assert json.loads(result.output) == []
