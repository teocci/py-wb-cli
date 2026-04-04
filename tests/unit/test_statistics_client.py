"""Unit tests for StatisticsClient."""

from unittest.mock import MagicMock

import pytest

from wb.client.statistics import StatisticsClient
from wb.core.constants import EP_STATISTICS_SALES


@pytest.fixture
def mock_http():
    return MagicMock()


@pytest.fixture
def client(mock_http):
    return StatisticsClient(mock_http)


class TestGetSales:
    def test_returns_list_from_api(self, client, mock_http):
        raw = [{'nmId': 1, 'date': '2026-03-01', 'quantity': 5}]
        mock_http.get.return_value = raw
        result = client.get_sales('2026-03-01')
        assert result == raw

    def test_non_list_response_returns_empty(self, client, mock_http):
        mock_http.get.return_value = {'error': 'bad'}
        result = client.get_sales('2026-03-01')
        assert result == []

    def test_none_response_returns_empty(self, client, mock_http):
        mock_http.get.return_value = None
        result = client.get_sales('2026-03-01')
        assert result == []

    def test_passes_correct_params_default_flag(self, client, mock_http):
        mock_http.get.return_value = []
        client.get_sales('2026-03-01')
        mock_http.get.assert_called_once_with(
            EP_STATISTICS_SALES,
            params={'dateFrom': '2026-03-01', 'flag': 1},
        )

    def test_passes_custom_flag(self, client, mock_http):
        mock_http.get.return_value = []
        client.get_sales('2026-03-01', flag=0)
        mock_http.get.assert_called_once_with(
            EP_STATISTICS_SALES,
            params={'dateFrom': '2026-03-01', 'flag': 0},
        )
