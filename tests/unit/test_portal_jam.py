"""Tests for the WB Джем (Jam) report download surface — I-23.

Covers ``PortalClient`` jam methods, ``PortalJamService`` orchestration,
``JamReport`` parsing, and the ``wb portal jam`` CLI write-to-disk path.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import respx
import typer
from typer.testing import CliRunner

from wb.cli.portal import portal_app
from wb.client.portal import PortalClient
from wb.core.constants import (
    DOWNLOADS_CONTENT_ANALYTICS_BASE_URL,
    EP_PORTAL_JAM_DOWNLOADS,
    EP_PORTAL_JAM_FILE,
    EP_PORTAL_JAM_GENERATE,
    EP_PORTAL_TOKENS_JRPC,
    JAM_REPORT_SEARCH_QUERIES,
    SELLER_CONTENT_BASE_URL,
)
from wb.core.exceptions import ApiError, AuthenticationError
from wb.domain.models import JamReport
from wb.services.portal_jam import (
    JAM_REPORT_SLUGS,
    PortalJamService,
    _previous_window,
    default_filename,
)

GENERATE_URL = f'{SELLER_CONTENT_BASE_URL}{EP_PORTAL_JAM_GENERATE}'
LIST_URL = f'{SELLER_CONTENT_BASE_URL}{EP_PORTAL_JAM_DOWNLOADS}'
DOWNLOAD_URL = f'{DOWNLOADS_CONTENT_ANALYTICS_BASE_URL}{EP_PORTAL_JAM_FILE}'
TOKENS_JRPC_URL = f'{SELLER_CONTENT_BASE_URL}{EP_PORTAL_TOKENS_JRPC}'


def _token_response(token: str = 'mock-x-download-token') -> dict:
    return {'id': 'json-rpc_1', 'jsonrpc': '2.0', 'result': {'token': token}}


# ── Helpers ──────────────────────────────────────────────────────────


def _make_client() -> PortalClient:
    return PortalClient(authorizev3='auth-v3-key', cookie='c=1')


def _list_response(downloads: list[dict]) -> dict:
    return {
        'error': False, 'errorText': '',
        'additionalErrors': {'errors': None},
        'data': {'downloads': downloads},
    }


def _entry(report_id: str, status: str, **overrides) -> dict:
    base = {
        'id': report_id,
        'createdAt': '2026-05-30T10:00:00Z',
        'generatedAt': '2026-05-30T10:00:05Z' if status == 'SUCCESS' else '',
        'status': status,
        'name': 'Поисковые запросы — ваши товары',
        'size': 503335 if status == 'SUCCESS' else 0,
        'startDate': '2026-05-11',
        'endDate': '2026-05-11',
        'downloadUrl': f'{DOWNLOADS_CONTENT_ANALYTICS_BASE_URL}/api/v1/file-manager/download/{report_id}',
    }
    base.update(overrides)
    return base


# ── JamReport dataclass ──────────────────────────────────────────────


class TestJamReportFromApi:
    def test_full_payload(self):
        report = JamReport.from_api(_entry('abc-123', 'SUCCESS'))
        assert report.id == 'abc-123'
        assert report.status == 'SUCCESS'
        assert report.is_terminal and report.is_success
        assert report.size == 503335
        assert report.start_date == '2026-05-11'

    def test_missing_keys_default_to_empty(self):
        report = JamReport.from_api({})
        assert report.id == ''
        assert report.size == 0
        assert not report.is_terminal
        assert not report.is_success

    def test_failed_status_is_terminal_not_success(self):
        report = JamReport.from_api(_entry('x', 'FAILED'))
        assert report.is_terminal
        assert not report.is_success

    def test_processing_is_neither(self):
        report = JamReport.from_api(_entry('x', 'PROCESSING'))
        assert not report.is_terminal
        assert not report.is_success


# ── Previous-window math ─────────────────────────────────────────────


class TestPreviousWindow:
    def test_single_day(self):
        prev_start, prev_end = _previous_window(date(2026, 5, 11), date(2026, 5, 11))
        assert prev_start == date(2026, 5, 10)
        assert prev_end == date(2026, 5, 10)

    def test_matches_browser_trace_2026_05_26(self):
        prev_start, prev_end = _previous_window(date(2026, 5, 26), date(2026, 5, 26))
        assert prev_start == date(2026, 5, 25)
        assert prev_end == date(2026, 5, 25)

    def test_week_window(self):
        prev_start, prev_end = _previous_window(date(2026, 5, 20), date(2026, 5, 27))
        assert prev_end == date(2026, 5, 19)
        assert prev_start == date(2026, 5, 12)


# ── default_filename ─────────────────────────────────────────────────


class TestDefaultFilename:
    def test_search_queries_single_day(self):
        name = default_filename(JAM_REPORT_SEARCH_QUERIES, date(2026, 5, 11), date(2026, 5, 11))
        assert name == 'search-queries_2026-05-11.zip'

    def test_search_queries_range(self):
        name = default_filename(JAM_REPORT_SEARCH_QUERIES, date(2026, 5, 11), date(2026, 5, 13))
        assert name == 'search-queries_2026-05-11_2026-05-13.zip'

    def test_unknown_type_falls_back_to_lowercased_slug(self):
        name = default_filename('SOME_NEW_REPORT', date(2026, 1, 1), date(2026, 1, 1))
        assert name == 'some-new-report_2026-01-01.zip'

    def test_slug_table_includes_search_queries(self):
        assert JAM_REPORT_SLUGS[JAM_REPORT_SEARCH_QUERIES] == 'search-queries'


# ── PortalClient.generate_jam_report ─────────────────────────────────


class TestGenerateJamReport:
    def test_posts_envelope(self):
        captured: dict = {}

        def _capture(request: httpx.Request) -> httpx.Response:
            import json
            captured['json'] = json.loads(request.content)
            captured['headers'] = dict(request.headers)
            return httpx.Response(200, json={'data': 'Created', 'error': False})

        with respx.mock:
            respx.post(GENERATE_URL).mock(side_effect=_capture)
            client = _make_client()
            result = client.generate_jam_report(
                'id-1', JAM_REPORT_SEARCH_QUERIES,
                {'startDate': '2026-05-11', 'endDate': '2026-05-11'},
            )

        assert result == {'data': 'Created', 'error': False}
        assert captured['json'] == {
            'id': 'id-1',
            'userReportName': '',
            'reportType': JAM_REPORT_SEARCH_QUERIES,
            'params': {'startDate': '2026-05-11', 'endDate': '2026-05-11'},
        }
        assert captured['headers']['cookie'] == 'c=1'
        assert captured['headers']['authorizev3'] == 'auth-v3-key'

    def test_4xx_raises_api_error(self):
        with respx.mock:
            respx.post(GENERATE_URL).mock(return_value=httpx.Response(400, text='bad'))
            client = _make_client()
            with pytest.raises(ApiError):
                client.generate_jam_report('id-1', JAM_REPORT_SEARCH_QUERIES, {})


# ── PortalClient.list_jam_reports ────────────────────────────────────


class TestListJamReports:
    def test_returns_downloads(self):
        with respx.mock:
            respx.get(LIST_URL).mock(return_value=httpx.Response(
                200, json=_list_response([_entry('a', 'SUCCESS'), _entry('b', 'PROCESSING')]),
            ))
            client = _make_client()
            items = client.list_jam_reports(JAM_REPORT_SEARCH_QUERIES)
        assert [d['id'] for d in items] == ['a', 'b']

    def test_handles_null_downloads(self):
        with respx.mock:
            respx.get(LIST_URL).mock(return_value=httpx.Response(
                200, json={'error': False, 'data': {'downloads': None}},
            ))
            client = _make_client()
            assert client.list_jam_reports(JAM_REPORT_SEARCH_QUERIES) == []

    def test_handles_missing_data(self):
        with respx.mock:
            respx.get(LIST_URL).mock(return_value=httpx.Response(200, json={'error': False}))
            client = _make_client()
            assert client.list_jam_reports(JAM_REPORT_SEARCH_QUERIES) == []


# ── PortalClient.download_jam_file / _get_bytes ──────────────────────


class TestGenerateDownloadToken:
    def test_calls_tokensjrpc_with_content_analytics_team(self):
        captured: dict = {}

        def _capture(request: httpx.Request) -> httpx.Response:
            import json
            captured['json'] = json.loads(request.content)
            return httpx.Response(200, json=_token_response('tok-1'))

        with respx.mock:
            respx.post(TOKENS_JRPC_URL).mock(side_effect=_capture)
            client = _make_client()
            token = client.generate_download_token()

        assert token == 'tok-1'
        assert captured['json']['method'] == 'generateToken'
        assert captured['json']['params'] == {'team': 'content-analytics'}

    def test_generate_token_default_team_unchanged(self):
        captured: dict = {}

        def _capture(request: httpx.Request) -> httpx.Response:
            import json
            captured['json'] = json.loads(request.content)
            return httpx.Response(200, json=_token_response('render-tok'))

        with respx.mock:
            respx.post(TOKENS_JRPC_URL).mock(side_effect=_capture)
            client = _make_client()
            token = client.generate_token()

        assert token == 'render-tok'
        assert captured['json']['params'] == {'team': 'render'}


class TestDownloadJamFile:
    def test_mints_token_and_sends_x_download_token(self):
        captured_download: dict = {}

        def _capture_download(request: httpx.Request) -> httpx.Response:
            captured_download['headers'] = dict(request.headers)
            return httpx.Response(200, content=b'PK\x03\x04...zip-bytes')

        with respx.mock:
            respx.post(TOKENS_JRPC_URL).mock(return_value=httpx.Response(
                200, json=_token_response('minted-tok'),
            ))
            respx.get(f'{DOWNLOAD_URL}/report-xyz').mock(side_effect=_capture_download)
            client = _make_client()
            content = client.download_jam_file('report-xyz')

        assert content == b'PK\x03\x04...zip-bytes'
        assert captured_download['headers']['x-download-token'] == 'minted-tok'
        assert captured_download['headers']['cookie'] == 'c=1'
        assert 'authorizev3' not in captured_download['headers']
        assert captured_download['headers']['accept'] == '*/*'

    def test_401_on_download_raises_authentication_error(self):
        with respx.mock:
            respx.post(TOKENS_JRPC_URL).mock(return_value=httpx.Response(
                200, json=_token_response(),
            ))
            respx.get(f'{DOWNLOAD_URL}/x').mock(return_value=httpx.Response(401, text='nope'))
            client = _make_client()
            with pytest.raises(AuthenticationError):
                client.download_jam_file('x')

    def test_500_on_download_raises_api_error(self):
        with respx.mock:
            respx.post(TOKENS_JRPC_URL).mock(return_value=httpx.Response(
                200, json=_token_response(),
            ))
            respx.get(f'{DOWNLOAD_URL}/x').mock(return_value=httpx.Response(500, text='boom'))
            client = _make_client()
            with pytest.raises(ApiError):
                client.download_jam_file('x')

    def test_token_mint_failure_propagates(self):
        with respx.mock:
            respx.post(TOKENS_JRPC_URL).mock(return_value=httpx.Response(401, text='nope'))
            client = _make_client()
            with pytest.raises(AuthenticationError):
                client.download_jam_file('x')


# ── PortalJamService ─────────────────────────────────────────────────


class TestBuildSearchQueriesParams:
    def test_matches_browser_trace(self):
        params = PortalJamService.build_search_queries_params(
            date(2026, 5, 26), date(2026, 5, 26),
        )
        assert params['startDate'] == '2026-05-26'
        assert params['endDate'] == '2026-05-26'
        assert params['previousStartDate'] == '2026-05-25'
        assert params['previousEndDate'] == '2026-05-25'
        assert params['orderBy'] == {'field': 'openCard', 'mode': 'desc'}
        assert params['positionCluster'] == 'all'
        assert params['topOrderBy'] == 'openCard'
        assert params['textLimit'] == 30
        assert params['includeSearchTexts'] is True
        assert params['includeSubstitutedSKUs'] is True
        assert params['brands'] == []
        assert params['nms'] == []


class TestRequestSearchQueries:
    def test_generates_uuid_and_calls_client(self):
        client = MagicMock(spec=PortalClient)
        client.generate_jam_report.return_value = {'data': 'Created'}
        service = PortalJamService(client)

        report_id = service.request_search_queries(date(2026, 5, 11), date(2026, 5, 11))

        client.generate_jam_report.assert_called_once()
        passed_id, passed_type, passed_params = client.generate_jam_report.call_args.args
        assert passed_id == report_id
        assert passed_type == JAM_REPORT_SEARCH_QUERIES
        assert passed_params['startDate'] == '2026-05-11'
        assert passed_params['previousStartDate'] == '2026-05-10'


class TestPollReport:
    def test_returns_on_success_after_processing(self, monkeypatch):
        monkeypatch.setattr('wb.services.portal_jam.time.sleep', lambda _: None)
        client = MagicMock(spec=PortalClient)
        client.list_jam_reports.side_effect = [
            [_entry('id-1', 'PROCESSING')],
            [_entry('id-1', 'PROCESSING')],
            [_entry('id-1', 'SUCCESS')],
        ]
        service = PortalJamService(client)

        report = service.poll_report(
            'id-1', JAM_REPORT_SEARCH_QUERIES, interval=0.01, timeout=10,
        )
        assert report.is_success
        assert client.list_jam_reports.call_count == 3

    def test_failed_status_is_returned_terminal(self, monkeypatch):
        monkeypatch.setattr('wb.services.portal_jam.time.sleep', lambda _: None)
        client = MagicMock(spec=PortalClient)
        client.list_jam_reports.return_value = [_entry('id-1', 'FAILED')]
        service = PortalJamService(client)

        report = service.poll_report(
            'id-1', JAM_REPORT_SEARCH_QUERIES, interval=0.01, timeout=10,
        )
        assert report.is_terminal
        assert not report.is_success

    def test_timeout_raises_api_error(self, monkeypatch):
        monkeypatch.setattr('wb.services.portal_jam.time.sleep', lambda _: None)
        client = MagicMock(spec=PortalClient)
        client.list_jam_reports.return_value = [_entry('id-1', 'PROCESSING')]
        service = PortalJamService(client)

        with pytest.raises(ApiError, match='did not finish'):
            service.poll_report(
                'id-1', JAM_REPORT_SEARCH_QUERIES, interval=0.05, timeout=0.1,
            )

    def test_ignores_other_report_ids(self, monkeypatch):
        monkeypatch.setattr('wb.services.portal_jam.time.sleep', lambda _: None)
        client = MagicMock(spec=PortalClient)
        client.list_jam_reports.side_effect = [
            [_entry('other-1', 'SUCCESS')],
            [_entry('other-1', 'SUCCESS'), _entry('id-1', 'SUCCESS')],
        ]
        service = PortalJamService(client)

        report = service.poll_report(
            'id-1', JAM_REPORT_SEARCH_QUERIES, interval=0.01, timeout=10,
        )
        assert report.id == 'id-1'


class TestFetchSearchQueries:
    def test_happy_path(self, monkeypatch):
        monkeypatch.setattr('wb.services.portal_jam.time.sleep', lambda _: None)
        fixed_uuid = 'fixed-uuid-1234'
        monkeypatch.setattr('wb.services.portal_jam.uuid.uuid4', lambda: fixed_uuid)
        client = MagicMock(spec=PortalClient)
        client.generate_jam_report.return_value = {'data': 'Created'}
        client.list_jam_reports.return_value = [_entry(fixed_uuid, 'SUCCESS')]
        client.download_jam_file.return_value = b'zipbytes'
        service = PortalJamService(client)

        report, content = service.fetch_search_queries(date(2026, 5, 11), date(2026, 5, 11))

        assert report.id == fixed_uuid
        assert content == b'zipbytes'
        client.download_jam_file.assert_called_once_with(fixed_uuid)

    def test_failed_status_raises(self, monkeypatch):
        monkeypatch.setattr('wb.services.portal_jam.time.sleep', lambda _: None)
        fixed_uuid = 'uuid-fail'
        monkeypatch.setattr('wb.services.portal_jam.uuid.uuid4', lambda: fixed_uuid)
        client = MagicMock(spec=PortalClient)
        client.generate_jam_report.return_value = {'data': 'Created'}
        client.list_jam_reports.return_value = [_entry(fixed_uuid, 'FAILED')]
        service = PortalJamService(client)

        with pytest.raises(ApiError, match='FAILED'):
            service.fetch_search_queries(date(2026, 5, 11), date(2026, 5, 11))
        client.download_jam_file.assert_not_called()


class TestListReports:
    def test_parses_to_jam_reports(self):
        client = MagicMock(spec=PortalClient)
        client.list_jam_reports.return_value = [
            _entry('a', 'SUCCESS'), _entry('b', 'PROCESSING'),
        ]
        service = PortalJamService(client)

        reports = service.list_reports(JAM_REPORT_SEARCH_QUERIES)

        assert [r.id for r in reports] == ['a', 'b']
        assert reports[0].is_success
        assert not reports[1].is_terminal


# ── CLI write-to-disk integration ────────────────────────────────────


class TestJamCliSearchQueries:
    def test_writes_zip_to_disk(self, tmp_path, monkeypatch):
        fake_report = JamReport.from_api(_entry('cli-id', 'SUCCESS'))
        fake_service = MagicMock()
        fake_service.fetch_search_queries.return_value = (fake_report, b'PK-ZIP-DATA')

        monkeypatch.setattr(
            'wb.cli.portal._get_jam_service',
            lambda profile: fake_service,
        )

        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['jam', 'search-queries', '--from', '2026-05-11', '-o', str(tmp_path)],
            obj={'json_output': False, 'profile': None},
        )

        assert result.exit_code == 0, result.output
        out_file = tmp_path / 'search-queries_2026-05-11.zip'
        assert out_file.exists()
        assert out_file.read_bytes() == b'PK-ZIP-DATA'
        assert 'Saved' in result.output

    def test_rejects_invalid_date(self, monkeypatch):
        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['jam', 'search-queries', '--from', 'not-a-date'],
            obj={'json_output': False, 'profile': None},
        )
        assert result.exit_code != 0
        assert 'YYYY-MM-DD' in result.output

    def test_rejects_inverted_range(self, monkeypatch):
        # No service stub needed — validation must fail before service lookup.
        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            [
                'jam', 'search-queries',
                '--from', '2026-05-11',
                '--to', '2026-05-10',
            ],
            obj={'json_output': False, 'profile': None},
        )
        assert result.exit_code != 0
        assert '--to' in result.output

    def test_json_mode_emits_metadata(self, tmp_path, monkeypatch):
        import json
        fake_report = JamReport.from_api(_entry('cli-json', 'SUCCESS'))
        fake_service = MagicMock()
        fake_service.fetch_search_queries.return_value = (fake_report, b'zz')
        monkeypatch.setattr(
            'wb.cli.portal._get_jam_service',
            lambda profile: fake_service,
        )

        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['jam', 'search-queries', '--from', '2026-05-11', '-o', str(tmp_path)],
            obj={'json_output': True, 'profile': None},
        )

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload['id'] == 'cli-json'
        assert payload['saved_path'].endswith('search-queries_2026-05-11.zip')


class TestJamCliList:
    def test_renders_table(self, monkeypatch):
        fake_reports = [
            JamReport.from_api(_entry('aaaa1111', 'SUCCESS')),
            JamReport.from_api(_entry('bbbb2222', 'PROCESSING')),
        ]
        fake_service = MagicMock()
        fake_service.list_reports.return_value = fake_reports
        monkeypatch.setattr(
            'wb.cli.portal._get_jam_service',
            lambda profile: fake_service,
        )

        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['jam', 'list'],
            obj={'json_output': False, 'profile': None},
        )

        assert result.exit_code == 0, result.output
        assert 'aaaa1111'[:8] in result.output
        assert 'PROCESSING' in result.output

    def test_empty_list_message(self, monkeypatch):
        fake_service = MagicMock()
        fake_service.list_reports.return_value = []
        monkeypatch.setattr(
            'wb.cli.portal._get_jam_service',
            lambda profile: fake_service,
        )

        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['jam', 'list'],
            obj={'json_output': False, 'profile': None},
        )

        assert result.exit_code == 0
        assert 'No Jam search-queries reports' in result.output

    def test_json_empty_list(self, monkeypatch):
        import json
        fake_service = MagicMock()
        fake_service.list_reports.return_value = []
        monkeypatch.setattr(
            'wb.cli.portal._get_jam_service',
            lambda profile: fake_service,
        )

        runner = CliRunner()
        result = runner.invoke(
            portal_app,
            ['jam', 'list'],
            obj={'json_output': True, 'profile': None},
        )

        assert result.exit_code == 0
        assert json.loads(result.output) == []
