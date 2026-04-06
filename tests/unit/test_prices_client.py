"""Tests for wb.client.prices.PricesClient."""

from unittest.mock import MagicMock

import pytest

from wb.client.prices import PricesClient
from wb.core.constants import EP_PRICES_GOODS_FILTER


@pytest.fixture()
def mock_http():
    """Create a mock WbHttpClient."""
    return MagicMock()


@pytest.fixture()
def client(mock_http):
    """Create a PricesClient backed by a mock HTTP client."""
    return PricesClient(mock_http)


class TestListGoods:
    """Tests for PricesClient.list_goods()."""

    def test_calls_correct_endpoint(self, client, mock_http):
        mock_http.get.return_value = {'data': {'listGoods': []}}
        client.list_goods()
        mock_http.get.assert_called_once_with(
            EP_PRICES_GOODS_FILTER,
            params={'limit': 1000, 'offset': 0},
        )

    def test_includes_filter_nm_id_when_given(self, client, mock_http):
        mock_http.get.return_value = {'data': {'listGoods': []}}
        client.list_goods(filter_nm_id=12345)
        call_params = mock_http.get.call_args[1]['params']
        assert call_params['filterNmID'] == 12345

    def test_omits_filter_nm_id_when_none(self, client, mock_http):
        mock_http.get.return_value = {'data': {'listGoods': []}}
        client.list_goods(filter_nm_id=None)
        call_params = mock_http.get.call_args[1]['params']
        assert 'filterNmID' not in call_params

    def test_clamps_limit_to_1000(self, client, mock_http):
        mock_http.get.return_value = {}
        client.list_goods(limit=9999)
        call_params = mock_http.get.call_args[1]['params']
        assert call_params['limit'] == 1000

    def test_passes_custom_offset(self, client, mock_http):
        mock_http.get.return_value = {}
        client.list_goods(offset=2000)
        call_params = mock_http.get.call_args[1]['params']
        assert call_params['offset'] == 2000

    def test_returns_dict_on_valid_response(self, client, mock_http):
        mock_http.get.return_value = {'data': {'listGoods': [{'nmID': 1}]}}
        result = client.list_goods()
        assert isinstance(result, dict)

    def test_returns_empty_dict_on_none_response(self, client, mock_http):
        mock_http.get.return_value = None
        result = client.list_goods()
        assert result == {}

    def test_returns_empty_dict_on_non_dict_response(self, client, mock_http):
        mock_http.get.return_value = [1, 2, 3]
        result = client.list_goods()
        assert result == {}
