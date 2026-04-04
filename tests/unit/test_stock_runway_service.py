"""Unit tests for ReportsService.get_stock_runway()."""

from unittest.mock import MagicMock, patch

import pytest

from wb.core.exceptions import ApiError, ValidationError
from wb.domain.report_models import (
    ReportTask,
    WarehouseRemainItem,
    WarehouseStock,
)
from wb.services.reports import ReportsService


def _make_remain_item(nm_id: int, warehouses: list[WarehouseStock]) -> WarehouseRemainItem:
    return WarehouseRemainItem(
        brand='Brand',
        subject_name='Subject',
        vendor_code='VC',
        nm_id=nm_id,
        barcode='123',
        tech_size='',
        volume=0.0,
        warehouses=warehouses,
    )


def _make_sale_raw(nm_id: int, date: str, quantity: int) -> dict:
    return {'nmId': nm_id, 'date': date, 'quantity': quantity}


@pytest.fixture
def reports_client():
    return MagicMock()


@pytest.fixture
def stats_client():
    return MagicMock()


@pytest.fixture
def svc(reports_client, stats_client):
    return ReportsService(reports_client, stats_client)


def _setup_warehouse_report(reports_client, items: list[WarehouseRemainItem]):
    """Configure reports_client mock to return items after create/status/download cycle."""
    task_id = 'task-001'
    reports_client.create_warehouse_remains.return_value = {
        'data': {'taskId': task_id}
    }
    reports_client.get_warehouse_remains_status.return_value = {
        'data': {'id': task_id, 'status': 'done'}
    }
    raw_items = []
    for item in items:
        raw_items.append({
            'brand': item.brand,
            'subjectName': item.subject_name,
            'vendorCode': item.vendor_code,
            'nmId': item.nm_id,
            'barcode': item.barcode,
            'techSize': item.tech_size,
            'volume': item.volume,
            'warehouses': [
                {'warehouseName': w.warehouse_name, 'quantity': w.quantity}
                for w in item.warehouses
            ],
        })
    reports_client.download_warehouse_remains.return_value = raw_items


class TestGetStockRunwayValidation:
    def test_raises_without_statistics_client(self, reports_client):
        svc_no_stats = ReportsService(reports_client)  # no stats_client
        with pytest.raises(ValidationError, match='statistics_client'):
            svc_no_stats.get_stock_runway()

    def test_raises_for_invalid_period(self, svc):
        with pytest.raises(ValidationError, match='sales_period_days'):
            svc.get_stock_runway(sales_period_days=0)


class TestGetStockRunwayComputation:
    @patch('wb.services.reports.time.sleep')
    @patch('wb.services.reports._utc_now_iso', return_value='2026-04-04T00:00:00')
    def test_high_confidence_avg_computed_correctly(
            self, mock_now, mock_sleep, svc, reports_client, stats_client,
    ):
        """30 days of sales data → high confidence, correct avg."""
        items = [_make_remain_item(100, [WarehouseStock('Москва', 120)])]
        _setup_warehouse_report(reports_client, items)

        # 30 sale-days, 3 qty each → total 90, avg = 3.0/day
        sales = [_make_sale_raw(100, f'2026-03-{d:02d}', 3) for d in range(1, 31)]
        stats_client.get_sales.return_value = sales

        report, _ = svc.get_stock_runway(sales_period_days=30)
        assert len(report.items) == 1
        item = report.items[0]
        assert item.nm_id == 100
        assert item.avg_daily_sales == 3.0
        assert item.confidence == 'high'   # 30 sale-days >= 20
        assert item.total_stock == 120
        assert item.total_days_of_stock == 40   # 120 / 3

    @patch('wb.services.reports.time.sleep')
    @patch('wb.services.reports._utc_now_iso', return_value='2026-04-04T00:00:00')
    def test_no_sales_gives_none_confidence(
            self, mock_now, mock_sleep, svc, reports_client, stats_client,
    ):
        items = [_make_remain_item(200, [WarehouseStock('Москва', 50)])]
        _setup_warehouse_report(reports_client, items)
        stats_client.get_sales.return_value = []

        report, _ = svc.get_stock_runway(sales_period_days=30)
        item = report.items[0]
        assert item.avg_daily_sales == 0.0
        assert item.confidence == 'none'
        assert item.total_days_of_stock is None
        assert item.alert is None

    @patch('wb.services.reports.time.sleep')
    @patch('wb.services.reports._utc_now_iso', return_value='2026-04-04T00:00:00')
    def test_alert_critical_when_leq_7_days(
            self, mock_now, mock_sleep, svc, reports_client, stats_client,
    ):
        # 10 units stock, 2 units/day → 5 days → critical
        items = [_make_remain_item(300, [WarehouseStock('Казань', 10)])]
        _setup_warehouse_report(reports_client, items)
        # 20 sale-days (high confidence), total 60, avg=2.0
        sales = [_make_sale_raw(300, f'2026-03-{d:02d}', 3) for d in range(1, 21)]
        stats_client.get_sales.return_value = sales

        report, _ = svc.get_stock_runway(sales_period_days=30)
        item = report.items[0]
        assert item.total_days_of_stock == 5
        assert item.alert == 'critical'
        assert item.warehouses[0].alert == 'critical'

    @patch('wb.services.reports.time.sleep')
    @patch('wb.services.reports._utc_now_iso', return_value='2026-04-04T00:00:00')
    def test_alert_low_when_leq_14_days(
            self, mock_now, mock_sleep, svc, reports_client, stats_client,
    ):
        # 20 units stock, avg 2.0/day (60 total / 30 days) → 10 days → low
        items = [_make_remain_item(400, [WarehouseStock('Краснодар', 20)])]
        _setup_warehouse_report(reports_client, items)
        # 20 sale-days × qty=3 → total=60, avg=60/30=2.0/day
        sales = [_make_sale_raw(400, f'2026-03-{d:02d}', 3) for d in range(1, 21)]
        stats_client.get_sales.return_value = sales

        report, _ = svc.get_stock_runway(sales_period_days=30)
        item = report.items[0]
        assert item.warehouses[0].days_of_stock == 10
        assert item.warehouses[0].alert == 'low'
        assert item.alert == 'low'

    @patch('wb.services.reports.time.sleep')
    @patch('wb.services.reports._utc_now_iso', return_value='2026-04-04T00:00:00')
    def test_excludes_transit_warehouses(
            self, mock_now, mock_sleep, svc, reports_client, stats_client,
    ):
        warehouses = [
            WarehouseStock('Москва', 100),
            WarehouseStock('В пути до получателей', 10),
            WarehouseStock('Всего находится на складах', 110),
        ]
        items = [_make_remain_item(500, warehouses)]
        _setup_warehouse_report(reports_client, items)
        sales = [_make_sale_raw(500, '2026-03-01', 10)]
        stats_client.get_sales.return_value = sales

        report, _ = svc.get_stock_runway(sales_period_days=30)
        item = report.items[0]
        # Only 'Москва' should survive
        assert len(item.warehouses) == 1
        assert item.warehouses[0].warehouse_name == 'Москва'
        assert item.total_stock == 100

    @patch('wb.services.reports.time.sleep')
    @patch('wb.services.reports._utc_now_iso', return_value='2026-04-04T00:00:00')
    def test_medium_confidence_for_10_to_19_sale_days(
            self, mock_now, mock_sleep, svc, reports_client, stats_client,
    ):
        items = [_make_remain_item(600, [WarehouseStock('Склад', 150)])]
        _setup_warehouse_report(reports_client, items)
        # 15 unique sale-days → medium confidence
        sales = [_make_sale_raw(600, f'2026-03-{d:02d}', 1) for d in range(1, 16)]
        stats_client.get_sales.return_value = sales

        report, _ = svc.get_stock_runway(sales_period_days=30)
        assert report.items[0].confidence == 'medium'

    @patch('wb.services.reports.time.sleep')
    @patch('wb.services.reports._utc_now_iso', return_value='2026-04-04T00:00:00')
    def test_low_confidence_for_1_to_9_sale_days(
            self, mock_now, mock_sleep, svc, reports_client, stats_client,
    ):
        items = [_make_remain_item(700, [WarehouseStock('Склад', 150)])]
        _setup_warehouse_report(reports_client, items)
        # 5 unique sale-days → low confidence
        sales = [_make_sale_raw(700, f'2026-03-{d:02d}', 1) for d in range(1, 6)]
        stats_client.get_sales.return_value = sales

        report, _ = svc.get_stock_runway(sales_period_days=30)
        assert report.items[0].confidence == 'low'

    @patch('wb.services.reports.time.sleep')
    @patch('wb.services.reports._utc_now_iso', return_value='2026-04-04T00:00:00')
    def test_report_metadata(self, mock_now, mock_sleep, svc, reports_client, stats_client):
        _setup_warehouse_report(reports_client, [])
        stats_client.get_sales.return_value = []

        report, _ = svc.get_stock_runway(sales_period_days=14)
        assert report.computed_at == '2026-04-04T00:00:00'
        assert report.sales_period_days == 14
