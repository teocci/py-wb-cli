"""Tests for wb.client.reports.ReportsClient."""

from unittest.mock import MagicMock

import pytest

from wb.client.reports import ReportsClient
from wb.core.constants import (
    EP_WAREHOUSE_REMAINS_CREATE,
    EP_WAREHOUSE_REMAINS_DOWNLOAD,
    EP_WAREHOUSE_REMAINS_STATUS,
)


@pytest.fixture()
def mock_http():
    """Create a mock WbHttpClient."""
    return MagicMock()


@pytest.fixture()
def client(mock_http):
    """Create a ReportsClient with mock HTTP."""
    return ReportsClient(mock_http)


class TestCreateWarehouseRemains:
    """Tests for create_warehouse_remains()."""

    def test_calls_get_with_correct_params(self, client, mock_http):
        mock_http.get.return_value = {'data': {'taskId': 'abc'}}
        client.create_warehouse_remains(
            locale='en',
            group_by_nm=True,
            group_by_brand=True,
        )
        mock_http.get.assert_called_once()
        args, kwargs = mock_http.get.call_args
        assert args[0] == EP_WAREHOUSE_REMAINS_CREATE
        params = kwargs.get('params', args[1] if len(args) > 1 else {})
        assert params['locale'] == 'en'
        assert params['groupByNm'] == 'true'
        assert params['groupByBrand'] == 'true'
        assert params['groupBySubject'] == 'false'

    def test_returns_dict(self, client, mock_http):
        mock_http.get.return_value = {'data': {'taskId': 'abc'}}
        result = client.create_warehouse_remains()
        assert isinstance(result, dict)

    def test_returns_empty_dict_on_none(self, client, mock_http):
        mock_http.get.return_value = None
        result = client.create_warehouse_remains()
        assert result == {}

    def test_default_params(self, client, mock_http):
        mock_http.get.return_value = {}
        client.create_warehouse_remains()
        _, kwargs = mock_http.get.call_args
        params = kwargs.get('params', {})
        assert params['locale'] == 'ru'
        assert params['groupByNm'] == 'false'
        assert params['filterPics'] == 0
        assert params['filterVolume'] == 0


class TestGetWarehouseRemainsStatus:
    """Tests for get_warehouse_remains_status()."""

    def test_calls_correct_path(self, client, mock_http):
        mock_http.get.return_value = {'data': {'id': 'abc', 'status': 'done'}}
        client.get_warehouse_remains_status('abc-123')
        expected = f'{EP_WAREHOUSE_REMAINS_STATUS}/abc-123/status'
        mock_http.get.assert_called_once_with(expected)

    def test_returns_dict(self, client, mock_http):
        mock_http.get.return_value = {'data': {'status': 'processing'}}
        result = client.get_warehouse_remains_status('abc')
        assert isinstance(result, dict)

    def test_returns_empty_dict_on_none(self, client, mock_http):
        mock_http.get.return_value = None
        result = client.get_warehouse_remains_status('abc')
        assert result == {}


class TestDownloadWarehouseRemains:
    """Tests for download_warehouse_remains()."""

    def test_calls_correct_path(self, client, mock_http):
        mock_http.get.return_value = []
        client.download_warehouse_remains('xyz-456')
        expected = f'{EP_WAREHOUSE_REMAINS_DOWNLOAD}/xyz-456/download'
        mock_http.get.assert_called_once_with(expected)

    def test_returns_list(self, client, mock_http):
        mock_http.get.return_value = [{'nmId': 1, 'warehouses': []}]
        result = client.download_warehouse_remains('abc')
        assert isinstance(result, list)
        assert len(result) == 1

    def test_returns_empty_list_on_none(self, client, mock_http):
        mock_http.get.return_value = None
        result = client.download_warehouse_remains('abc')
        assert result == []

    def test_returns_empty_list_on_dict(self, client, mock_http):
        mock_http.get.return_value = {'error': 'not found'}
        result = client.download_warehouse_remains('abc')
        assert result == []
