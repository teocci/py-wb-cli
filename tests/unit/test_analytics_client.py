"""Tests for wb.client.analytics.AnalyticsClient."""

from unittest.mock import MagicMock

import pytest

from wb.client.analytics import AnalyticsClient
from wb.core.constants import (
    EP_CSV_CREATE,
    EP_CSV_DOWNLOAD,
    EP_CSV_LIST,
    EP_CSV_RETRY,
    EP_FUNNEL_GROUPED,
    EP_FUNNEL_HISTORY,
    EP_FUNNEL_PRODUCTS,
    EP_SEARCH_DETAILS,
    EP_SEARCH_GROUPS,
    EP_SEARCH_ORDERS,
    EP_SEARCH_REPORT,
    EP_SEARCH_TEXTS,
)


@pytest.fixture()
def mock_http():
    """Create a mock WbHttpClient."""
    return MagicMock()


@pytest.fixture()
def client(mock_http):
    """Create an AnalyticsClient with mock HTTP."""
    return AnalyticsClient(mock_http)


# ── Sales Funnel ─────────────────────────────────────────────────────


class TestGetFunnelProducts:
    """Tests for get_funnel_products()."""

    def test_posts_to_correct_endpoint(self, client, mock_http):
        mock_http.post.return_value = {'data': {'products': []}}
        body = {'selectedPeriod': {'begin': '2025-01-01', 'end': '2025-01-31'}}
        client.get_funnel_products(body)
        mock_http.post.assert_called_once_with(
            EP_FUNNEL_PRODUCTS, json_body=body,
        )

    def test_returns_dict(self, client, mock_http):
        mock_http.post.return_value = {'data': {'products': []}}
        result = client.get_funnel_products({})
        assert isinstance(result, dict)

    def test_returns_empty_dict_on_none(self, client, mock_http):
        mock_http.post.return_value = None
        result = client.get_funnel_products({})
        assert result == {}


class TestGetFunnelHistory:
    """Tests for get_funnel_history()."""

    def test_posts_to_correct_endpoint(self, client, mock_http):
        mock_http.post.return_value = []
        body = {'selectedPeriod': {}, 'nmIds': [1]}
        client.get_funnel_history(body)
        mock_http.post.assert_called_once_with(
            EP_FUNNEL_HISTORY, json_body=body,
        )

    def test_returns_list(self, client, mock_http):
        mock_http.post.return_value = [{'product': {}}]
        result = client.get_funnel_history({})
        assert isinstance(result, list)

    def test_returns_empty_list_on_none(self, client, mock_http):
        mock_http.post.return_value = None
        result = client.get_funnel_history({})
        assert result == []


class TestGetFunnelGrouped:
    """Tests for get_funnel_grouped()."""

    def test_posts_to_correct_endpoint(self, client, mock_http):
        mock_http.post.return_value = {'data': []}
        client.get_funnel_grouped({})
        mock_http.post.assert_called_once_with(
            EP_FUNNEL_GROUPED, json_body={},
        )


# ── Search Report ────────────────────────────────────────────────────


class TestGetSearchReport:
    """Tests for get_search_report()."""

    def test_posts_to_correct_endpoint(self, client, mock_http):
        mock_http.post.return_value = {'data': {}}
        client.get_search_report({})
        mock_http.post.assert_called_once_with(
            EP_SEARCH_REPORT, json_body={},
        )


class TestGetSearchGroups:
    """Tests for get_search_groups()."""

    def test_posts_to_correct_endpoint(self, client, mock_http):
        mock_http.post.return_value = {'data': {'groups': []}}
        client.get_search_groups({})
        mock_http.post.assert_called_once_with(
            EP_SEARCH_GROUPS, json_body={},
        )


class TestGetSearchDetails:
    """Tests for get_search_details()."""

    def test_posts_to_correct_endpoint(self, client, mock_http):
        mock_http.post.return_value = {'data': {'products': []}}
        client.get_search_details({})
        mock_http.post.assert_called_once_with(
            EP_SEARCH_DETAILS, json_body={},
        )


class TestGetSearchTexts:
    """Tests for get_search_texts()."""

    def test_posts_to_correct_endpoint(self, client, mock_http):
        mock_http.post.return_value = {'data': {'searchTexts': []}}
        body = {'currentPeriod': {}, 'nmId': 1}
        client.get_search_texts(body)
        mock_http.post.assert_called_once_with(
            EP_SEARCH_TEXTS, json_body=body,
        )


class TestGetSearchOrders:
    """Tests for get_search_orders()."""

    def test_posts_to_correct_endpoint(self, client, mock_http):
        mock_http.post.return_value = {'data': {}}
        body = {'currentPeriod': {}, 'nmId': 1, 'searchTexts': ['test']}
        client.get_search_orders(body)
        mock_http.post.assert_called_once_with(
            EP_SEARCH_ORDERS, json_body=body,
        )


# ── CSV Reports ──────────────────────────────────────────────────────


class TestCreateReport:
    """Tests for create_report()."""

    def test_posts_to_correct_endpoint(self, client, mock_http):
        mock_http.post.return_value = {'data': 'started'}
        body = {'id': 'abc', 'reportType': 'DETAIL_HISTORY_REPORT'}
        client.create_report(body)
        mock_http.post.assert_called_once_with(
            EP_CSV_CREATE, json_body=body,
        )

    def test_returns_empty_dict_on_none(self, client, mock_http):
        mock_http.post.return_value = None
        result = client.create_report({})
        assert result == {}


class TestListReports:
    """Tests for list_reports()."""

    def test_gets_without_filter(self, client, mock_http):
        mock_http.get.return_value = {'data': []}
        client.list_reports()
        mock_http.get.assert_called_once_with(EP_CSV_LIST, params=None)

    def test_gets_with_filter(self, client, mock_http):
        mock_http.get.return_value = {'data': []}
        client.list_reports(['id-1', 'id-2'])
        mock_http.get.assert_called_once_with(
            EP_CSV_LIST,
            params={'filter[downloadIds]': ['id-1', 'id-2']},
        )


class TestRetryReport:
    """Tests for retry_report()."""

    def test_posts_correct_payload(self, client, mock_http):
        mock_http.post.return_value = {'data': 'Retry'}
        client.retry_report('abc-123')
        mock_http.post.assert_called_once_with(
            EP_CSV_RETRY,
            json_body={'downloadId': 'abc-123'},
        )


class TestDownloadReport:
    """Tests for download_report()."""

    def test_calls_request_raw(self, client, mock_http):
        mock_http.request_raw.return_value = b'PK\x03\x04'
        result = client.download_report('abc-123')
        mock_http.request_raw.assert_called_once_with(
            'GET', f'{EP_CSV_DOWNLOAD}/abc-123',
        )
        assert result == b'PK\x03\x04'
