"""Tests for wb.services.analytics.AnalyticsService."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from wb.core.exceptions import ValidationError
from wb.domain.analytics_models import (
    CsvReportStatus,
    ProductFunnelHistory,
    ProductFunnelStats,
    SearchReportGroup,
    SearchReportProduct,
    SearchTextEntry,
)
from wb.services.analytics import AnalyticsService


@pytest.fixture()
def mock_client():
    """Create a mock AnalyticsClient."""
    return MagicMock()


@pytest.fixture()
def service(mock_client):
    """Create an AnalyticsService with mock client."""
    return AnalyticsService(mock_client)


# ── Sales Funnel ─────────────────────────────────────────────────────


class TestGetProductFunnel:
    """Tests for AnalyticsService.get_product_funnel."""

    def test_returns_product_funnel_stats(self, service, mock_client):
        mock_client.get_funnel_products.return_value = {
            'data': {
                'products': [{
                    'product': {'nmId': 123, 'title': 'Sneakers'},
                    'statistic': {
                        'selected': {
                            'openCount': 100,
                            'conversions': {},
                        },
                    },
                }],
                'currency': 'RUB',
            },
        }
        result = service.get_product_funnel('2025-01-01', '2025-01-31')
        assert len(result) == 1
        assert isinstance(result[0], ProductFunnelStats)
        assert result[0].nm_id == 123

    def test_empty_products(self, service, mock_client):
        mock_client.get_funnel_products.return_value = {
            'data': {'products': [], 'currency': 'RUB'},
        }
        result = service.get_product_funnel('2025-01-01', '2025-01-31')
        assert result == []

    def test_passes_filters(self, service, mock_client):
        mock_client.get_funnel_products.return_value = {'data': {'products': []}}
        service.get_product_funnel(
            '2025-01-01', '2025-01-31',
            nm_ids=[1, 2],
            brand_names=['Nike'],
            subject_ids=[10],
            limit=5,
        )
        call_body = mock_client.get_funnel_products.call_args[0][0]
        assert call_body['nmIds'] == [1, 2]
        assert call_body['brandNames'] == ['Nike']
        assert call_body['limit'] == 5


class TestGetProductHistory:
    """Tests for AnalyticsService.get_product_history."""

    def test_returns_history(self, service, mock_client):
        mock_client.get_funnel_history.return_value = [{
            'product': {'nmId': 1, 'title': 'Test'},
            'history': [{'date': '2025-01-01', 'openCount': 10}],
            'currency': 'RUB',
        }]
        result = service.get_product_history('2025-01-01', '2025-01-07', [1])
        assert len(result) == 1
        assert isinstance(result[0], ProductFunnelHistory)

    def test_empty_nm_ids_raises(self, service):
        with pytest.raises(ValidationError, match='At least one'):
            service.get_product_history('2025-01-01', '2025-01-07', [])

    def test_21_nm_ids_auto_chunks_into_two_calls(self, service, mock_client):
        mock_client.get_funnel_history.return_value = []
        service.get_product_history('2025-01-01', '2025-01-07', list(range(21)))
        assert mock_client.get_funnel_history.call_count == 2
        first_call_ids = mock_client.get_funnel_history.call_args_list[0][0][0]['nmIds']
        second_call_ids = mock_client.get_funnel_history.call_args_list[1][0][0]['nmIds']
        assert len(first_call_ids) == 20
        assert len(second_call_ids) == 1

    def test_exactly_20_nm_ids_one_call(self, service, mock_client):
        mock_client.get_funnel_history.return_value = []
        service.get_product_history('2025-01-01', '2025-01-07', list(range(20)))
        assert mock_client.get_funnel_history.call_count == 1

    def test_40_nm_ids_two_calls_of_20(self, service, mock_client):
        mock_client.get_funnel_history.return_value = []
        service.get_product_history('2025-01-01', '2025-01-07', list(range(40)))
        assert mock_client.get_funnel_history.call_count == 2

    def test_results_from_chunks_are_merged(self, service, mock_client):
        chunk1_item = {
            'product': {'nmId': 1, 'title': 'A'},
            'history': [],
            'currency': 'RUB',
        }
        chunk2_item = {
            'product': {'nmId': 21, 'title': 'B'},
            'history': [],
            'currency': 'RUB',
        }
        mock_client.get_funnel_history.side_effect = [[chunk1_item], [chunk2_item]]
        results = service.get_product_history(
            '2025-01-01', '2025-01-07', list(range(21))
        )
        assert len(results) == 2


class TestGetGroupedHistory:
    """Tests for AnalyticsService.get_grouped_history."""

    def test_returns_grouped(self, service, mock_client):
        mock_client.get_funnel_grouped.return_value = {
            'data': [{
                'product': {'nmId': 1},
                'history': [],
                'currency': 'RUB',
            }],
        }
        result = service.get_grouped_history('2025-01-01', '2025-01-07')
        assert len(result) == 1

    def test_empty_data(self, service, mock_client):
        mock_client.get_funnel_grouped.return_value = {'data': []}
        result = service.get_grouped_history('2025-01-01', '2025-01-07')
        assert result == []


# ── Search Report ────────────────────────────────────────────────────


class TestGetSearchReport:
    """Tests for AnalyticsService.get_search_report."""

    def test_returns_data_dict(self, service, mock_client):
        mock_client.get_search_report.return_value = {
            'data': {'commonInfo': {}, 'groups': []},
        }
        result = service.get_search_report('2025-01-01', '2025-01-31')
        assert isinstance(result, dict)
        assert 'commonInfo' in result


class TestGetSearchGroups:
    """Tests for AnalyticsService.get_search_groups."""

    def test_returns_groups(self, service, mock_client):
        mock_client.get_search_groups.return_value = {
            'data': {
                'groups': [{
                    'subjectId': 10,
                    'subjectName': 'Shoes',
                    'brandName': 'Nike',
                    'products': [],
                }],
            },
        }
        result = service.get_search_groups('2025-01-01', '2025-01-31')
        assert len(result) == 1
        assert isinstance(result[0], SearchReportGroup)
        assert result[0].subject_name == 'Shoes'


class TestGetSearchDetails:
    """Tests for AnalyticsService.get_search_details."""

    def test_returns_products(self, service, mock_client):
        mock_client.get_search_details.return_value = {
            'data': {
                'products': [
                    {'nmId': 1, 'openCard': 50},
                ],
            },
        }
        result = service.get_search_details(
            '2025-01-01', '2025-01-31',
            subject_id=10,
            brand_name='Nike',
        )
        assert len(result) == 1
        assert isinstance(result[0], SearchReportProduct)


class TestGetSearchTexts:
    """Tests for AnalyticsService.get_search_texts."""

    def test_returns_text_entries(self, service, mock_client):
        mock_client.get_search_texts.return_value = {
            'data': {
                'searchTexts': [
                    {'text': 'sneakers', 'frequency': 1000, 'openCard': 50},
                ],
            },
        }
        result = service.get_search_texts('2025-01-01', '2025-01-31', 123)
        assert len(result) == 1
        assert isinstance(result[0], SearchTextEntry)
        assert result[0].text == 'sneakers'

    def test_empty_texts(self, service, mock_client):
        mock_client.get_search_texts.return_value = {
            'data': {'searchTexts': []},
        }
        result = service.get_search_texts('2025-01-01', '2025-01-31', 123)
        assert result == []


class TestGetSearchOrders:
    """Tests for AnalyticsService.get_search_orders."""

    def test_returns_data(self, service, mock_client):
        mock_client.get_search_orders.return_value = {
            'data': {'orders': []},
        }
        result = service.get_search_orders(
            '2025-01-01', '2025-01-31', 123, ['sneakers'],
        )
        assert isinstance(result, dict)


# ── CSV Reports ──────────────────────────────────────────────────────


class TestCreateCsvReport:
    """Tests for AnalyticsService.create_csv_report."""

    def test_creates_report_with_uuid(self, service, mock_client):
        mock_client.create_report.return_value = {'data': 'started'}
        result = service.create_csv_report(
            'DETAIL_HISTORY_REPORT', 'My Report', {'startDate': '2025-01-01'},
        )
        assert isinstance(result, CsvReportStatus)
        assert result.name == 'My Report'
        assert result.status == 'WAITING'
        assert len(result.id) == 36  # UUID format

    def test_passes_params_to_client(self, service, mock_client):
        mock_client.create_report.return_value = {'data': 'started'}
        service.create_csv_report('TYPE', 'Name', {'key': 'val'})
        call_body = mock_client.create_report.call_args[0][0]
        assert call_body['reportType'] == 'TYPE'
        assert call_body['userReportName'] == 'Name'
        assert call_body['params'] == {'key': 'val'}


class TestListCsvReports:
    """Tests for AnalyticsService.list_csv_reports."""

    def test_returns_statuses(self, service, mock_client):
        mock_client.list_reports.return_value = {
            'data': [
                {'id': 'abc', 'status': 'SUCCESS', 'name': 'R1'},
            ],
        }
        result = service.list_csv_reports()
        assert len(result) == 1
        assert isinstance(result[0], CsvReportStatus)
        assert result[0].status == 'SUCCESS'

    def test_empty_list(self, service, mock_client):
        mock_client.list_reports.return_value = {'data': []}
        result = service.list_csv_reports()
        assert result == []


class TestRetryCsvReport:
    """Tests for AnalyticsService.retry_csv_report."""

    def test_returns_message(self, service, mock_client):
        mock_client.retry_report.return_value = {'data': 'Retry'}
        result = service.retry_csv_report('abc-123')
        assert result == 'Retry'


class TestDownloadCsvReport:
    """Tests for AnalyticsService.download_csv_report."""

    def test_writes_file(self, service, mock_client, tmp_path):
        mock_client.download_report.return_value = b'PK\x03\x04fake'
        output = tmp_path / 'report.zip'
        result = service.download_csv_report('abc-123', output)
        assert result == output
        assert output.read_bytes() == b'PK\x03\x04fake'
