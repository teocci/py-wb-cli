"""Tests for analytics CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.domain.analytics_models import (
    CsvReportStatus,
    ProductFunnelHistory,
    ProductFunnelStats,
    SearchReportGroup,
    SearchTextEntry,
)

runner = CliRunner()

ANALYTICS_FACTORY = 'wb.services._factory.create_analytics_service'


# ── Sales Funnel commands ────────────────────────────────────────────


class TestFunnelProducts:
    """Tests for 'analytics sales-funnel products'."""

    def test_help(self):
        result = runner.invoke(
            app, ['analytics', 'sales-funnel', 'products', '--help'],
        )
        assert result.exit_code == 0
        assert 'period' in result.output.lower()

    @patch(ANALYTICS_FACTORY)
    def test_json_output(self, mock_factory):
        svc = MagicMock()
        svc.get_product_funnel.return_value = [
            ProductFunnelStats(nm_id=123, title='Test', open_count=100),
        ]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'analytics', 'sales-funnel', 'products',
            '--from', '2025-01-01', '--to', '2025-01-31',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]['nm_id'] == 123

    @patch(ANALYTICS_FACTORY)
    def test_empty_result(self, mock_factory):
        svc = MagicMock()
        svc.get_product_funnel.return_value = []
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'analytics', 'sales-funnel', 'products',
            '--from', '2025-01-01', '--to', '2025-01-31',
        ])
        assert result.exit_code == 0
        assert 'No funnel data' in result.output


class TestFunnelHistory:
    """Tests for 'analytics sales-funnel history'."""

    @patch(ANALYTICS_FACTORY)
    def test_json_output(self, mock_factory):
        svc = MagicMock()
        svc.get_product_history.return_value = [
            ProductFunnelHistory(nm_id=1, title='Test', history=[]),
        ]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'analytics', 'sales-funnel', 'history',
            '--from', '2025-01-01', '--to', '2025-01-07',
            '--nm-ids', '1,2',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]['nm_id'] == 1


# ── Search Report commands ───────────────────────────────────────────


class TestSearchMain:
    """Tests for 'analytics search-report main'."""

    def test_help(self):
        result = runner.invoke(
            app, ['analytics', 'search-report', 'main', '--help'],
        )
        assert result.exit_code == 0

    @patch(ANALYTICS_FACTORY)
    def test_json_output(self, mock_factory):
        svc = MagicMock()
        svc.get_search_report.return_value = {
            'commonInfo': {'totalProducts': 10},
        }
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'analytics', 'search-report', 'main',
            '--from', '2025-01-01', '--to', '2025-01-31',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert 'commonInfo' in parsed


class TestSearchTexts:
    """Tests for 'analytics search-report search-texts'."""

    @patch(ANALYTICS_FACTORY)
    def test_json_output(self, mock_factory):
        svc = MagicMock()
        svc.get_search_texts.return_value = [
            SearchTextEntry(text='sneakers', frequency=1000),
        ]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'analytics', 'search-report', 'search-texts',
            '--from', '2025-01-01', '--to', '2025-01-31',
            '--nm-id', '123',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]['text'] == 'sneakers'


# ── CSV Report commands ──────────────────────────────────────────────


class TestCsvList:
    """Tests for 'analytics csv list'."""

    def test_help(self):
        result = runner.invoke(
            app, ['analytics', 'csv', 'list', '--help'],
        )
        assert result.exit_code == 0

    @patch(ANALYTICS_FACTORY)
    def test_json_output(self, mock_factory):
        svc = MagicMock()
        svc.list_csv_reports.return_value = [
            CsvReportStatus(id='abc', name='R1', status='SUCCESS'),
        ]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'analytics', 'csv', 'list',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]['status'] == 'SUCCESS'

    @patch(ANALYTICS_FACTORY)
    def test_empty_list(self, mock_factory):
        svc = MagicMock()
        svc.list_csv_reports.return_value = []
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'analytics', 'csv', 'list',
        ])
        assert result.exit_code == 0
        assert 'No reports found' in result.output


class TestCsvRetry:
    """Tests for 'analytics csv retry'."""

    @patch(ANALYTICS_FACTORY)
    def test_retry(self, mock_factory):
        svc = MagicMock()
        svc.retry_csv_report.return_value = 'Retry'
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'analytics', 'csv', 'retry', '--id', 'abc-123',
        ])
        assert result.exit_code == 0
        assert 'Retry' in result.output


class TestCsvDownload:
    """Tests for 'analytics csv download'."""

    @patch(ANALYTICS_FACTORY)
    def test_download(self, mock_factory, tmp_path):
        svc = MagicMock()
        output = tmp_path / 'report.zip'
        svc.download_csv_report.return_value = output
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'analytics', 'csv', 'download',
            '--id', 'abc-123',
            '--output', str(output),
        ])
        assert result.exit_code == 0
        assert 'saved' in result.output.lower()
