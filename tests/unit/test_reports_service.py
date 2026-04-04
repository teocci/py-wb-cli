"""Tests for wb.services.reports.ReportsService."""

from unittest.mock import MagicMock, patch

import pytest

from wb.core.exceptions import ApiError, ValidationError
from wb.services.reports import ReportsService, _aggregate_top
from wb.domain.report_models import (
    WarehouseRemainItem,
    WarehouseStock,
)


@pytest.fixture()
def mock_client():
    """Create a mock ReportsClient."""
    return MagicMock()


@pytest.fixture()
def svc(mock_client):
    """Create a ReportsService with mock client."""
    return ReportsService(mock_client)


class TestCreateWarehouseReport:
    """Tests for create_warehouse_report()."""

    def test_returns_report_task(self, svc, mock_client):
        mock_client.create_warehouse_remains.return_value = {
            'data': {'taskId': 'task-001'},
        }
        task = svc.create_warehouse_report(group_by_nm=True)
        assert task.task_id == 'task-001'
        assert task.status == 'new'

    def test_forwards_kwargs(self, svc, mock_client):
        mock_client.create_warehouse_remains.return_value = {'data': {'taskId': 'x'}}
        svc.create_warehouse_report(locale='en', group_by_brand=True)
        mock_client.create_warehouse_remains.assert_called_once_with(
            locale='en', group_by_brand=True,
        )


class TestCheckWarehouseStatus:
    """Tests for check_warehouse_status()."""

    def test_returns_status(self, svc, mock_client):
        mock_client.get_warehouse_remains_status.return_value = {
            'data': {'id': 'task-001', 'status': 'done'},
        }
        task = svc.check_warehouse_status('task-001')
        assert task.status == 'done'
        assert task.is_done is True


class TestDownloadWarehouseReport:
    """Tests for download_warehouse_report()."""

    def test_returns_parsed_items(self, svc, mock_client):
        mock_client.download_warehouse_remains.return_value = [
            {
                'brand': 'B1',
                'subjectName': 'Shoes',
                'vendorCode': 'V1',
                'nmId': 100,
                'barcode': '123',
                'techSize': '0',
                'volume': 1.5,
                'warehouses': [
                    {'warehouseName': 'WH-A', 'quantity': 50},
                ],
            },
        ]
        items = svc.download_warehouse_report('task-001')
        assert len(items) == 1
        assert items[0].nm_id == 100
        assert items[0].warehouses[0].quantity == 50

    def test_empty_response(self, svc, mock_client):
        mock_client.download_warehouse_remains.return_value = []
        items = svc.download_warehouse_report('task-001')
        assert items == []


class TestPollWarehouseReport:
    """Tests for poll_warehouse_report()."""

    @patch('wb.services.reports.time.sleep')
    def test_returns_on_done(self, mock_sleep, svc, mock_client):
        mock_client.get_warehouse_remains_status.side_effect = [
            {'data': {'id': 't1', 'status': 'processing'}},
            {'data': {'id': 't1', 'status': 'done'}},
        ]
        task = svc.poll_warehouse_report('t1', interval=1.0, timeout=10.0)
        assert task.is_done is True
        assert mock_sleep.call_count == 1

    @patch('wb.services.reports.time.sleep')
    def test_returns_on_canceled(self, mock_sleep, svc, mock_client):
        mock_client.get_warehouse_remains_status.return_value = {
            'data': {'id': 't1', 'status': 'canceled'},
        }
        task = svc.poll_warehouse_report('t1', interval=1.0, timeout=10.0)
        assert task.status == 'canceled'
        assert task.is_terminal is True
        mock_sleep.assert_not_called()

    @patch('wb.services.reports.time.sleep')
    def test_raises_on_timeout(self, mock_sleep, svc, mock_client):
        mock_client.get_warehouse_remains_status.return_value = {
            'data': {'id': 't1', 'status': 'processing'},
        }
        with pytest.raises(ApiError, match='did not finish'):
            svc.poll_warehouse_report('t1', interval=1.0, timeout=2.0)


class TestGetWarehouseTop:
    """Tests for get_warehouse_top()."""

    def test_invalid_limit(self, svc):
        with pytest.raises(ValidationError, match='limit must be at least 1'):
            svc.get_warehouse_top(limit=0)

    @patch('wb.services.reports.time.sleep')
    def test_end_to_end(self, mock_sleep, svc, mock_client):
        mock_client.create_warehouse_remains.return_value = {
            'data': {'taskId': 't1'},
        }
        mock_client.get_warehouse_remains_status.return_value = {
            'data': {'id': 't1', 'status': 'done'},
        }
        mock_client.download_warehouse_remains.return_value = [
            {
                'nmId': 100, 'brand': 'B1', 'subjectName': 'S1',
                'vendorCode': 'V1',
                'warehouses': [
                    {'warehouseName': 'WH-A', 'quantity': 50},
                    {'warehouseName': 'WH-B', 'quantity': 30},
                ],
            },
            {
                'nmId': 200, 'brand': 'B2', 'subjectName': 'S2',
                'vendorCode': 'V2',
                'warehouses': [
                    {'warehouseName': 'WH-A', 'quantity': 200},
                ],
            },
            {
                'nmId': 300, 'brand': 'B3', 'subjectName': 'S3',
                'vendorCode': 'V3',
                'warehouses': [
                    {'warehouseName': 'WH-C', 'quantity': 10},
                ],
            },
        ]

        result, from_cache = svc.get_warehouse_top(limit=2)
        assert len(result) == 2
        assert result[0].nm_id == 200
        assert result[0].total_quantity == 200
        assert result[1].nm_id == 100
        assert result[1].total_quantity == 80
        assert from_cache is False

    @patch('wb.services.reports.time.sleep')
    def test_raises_on_non_done(self, mock_sleep, svc, mock_client):
        mock_client.create_warehouse_remains.return_value = {
            'data': {'taskId': 't1'},
        }
        mock_client.get_warehouse_remains_status.return_value = {
            'data': {'id': 't1', 'status': 'canceled'},
        }
        with pytest.raises(ApiError, match='ended with status: canceled'):
            svc.get_warehouse_top(limit=5)


class TestAggregateTop:
    """Tests for _aggregate_top helper."""

    def test_sorts_by_total_desc(self):
        items = [
            WarehouseRemainItem(
                brand='B1', subject_name='S1', vendor_code='V1',
                nm_id=1, barcode='', tech_size='', volume=0.0,
                warehouses=[WarehouseStock('WH', 10)],
            ),
            WarehouseRemainItem(
                brand='B2', subject_name='S2', vendor_code='V2',
                nm_id=2, barcode='', tech_size='', volume=0.0,
                warehouses=[WarehouseStock('WH', 100)],
            ),
        ]
        result = _aggregate_top(items, limit=10)
        assert result[0].nm_id == 2
        assert result[0].total_quantity == 100

    def test_respects_limit(self):
        items = [
            WarehouseRemainItem(
                brand='', subject_name='', vendor_code='',
                nm_id=i, barcode='', tech_size='', volume=0.0,
                warehouses=[WarehouseStock('WH', i * 10)],
            )
            for i in range(1, 6)
        ]
        result = _aggregate_top(items, limit=2)
        assert len(result) == 2
        assert result[0].nm_id == 5
        assert result[1].nm_id == 4

    def test_merges_duplicate_nm_ids(self):
        items = [
            WarehouseRemainItem(
                brand='B1', subject_name='S1', vendor_code='V1',
                nm_id=1, barcode='BC1', tech_size='S', volume=0.0,
                warehouses=[WarehouseStock('WH-A', 20)],
            ),
            WarehouseRemainItem(
                brand='B1', subject_name='S1', vendor_code='V1',
                nm_id=1, barcode='BC2', tech_size='M', volume=0.0,
                warehouses=[WarehouseStock('WH-B', 30)],
            ),
        ]
        result = _aggregate_top(items, limit=10)
        assert len(result) == 1
        assert result[0].total_quantity == 50
        assert len(result[0].warehouses) == 2

    def test_empty_input(self):
        result = _aggregate_top([], limit=5)
        assert result == []
