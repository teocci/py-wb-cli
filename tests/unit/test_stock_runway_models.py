"""Unit tests for stock runway domain models."""

import pytest

from wb.domain.report_models import (
    SaleRecord,
    StockRunwayItem,
    StockRunwayReport,
    WarehouseRunway,
)


class TestSaleRecord:
    def test_from_api_maps_fields(self):
        data = {'nmId': 123456, 'date': '2026-03-15T12:00:00', 'quantity': 3}
        rec = SaleRecord.from_api(data)
        assert rec.nm_id == 123456
        assert rec.date == '2026-03-15'
        assert rec.quantity == 3

    def test_from_api_missing_fields_use_defaults(self):
        rec = SaleRecord.from_api({})
        assert rec.nm_id == 0
        assert rec.date == ''
        assert rec.quantity == 0

    def test_from_api_converts_nm_id_to_int(self):
        rec = SaleRecord.from_api({'nmId': '99'})
        assert rec.nm_id == 99


class TestWarehouseRunway:
    def test_direct_construction(self):
        wh = WarehouseRunway(
            warehouse_name='Краснодар',
            quantity=50,
            days_of_stock=21,
            alert='low',
        )
        assert wh.warehouse_name == 'Краснодар'
        assert wh.quantity == 50
        assert wh.days_of_stock == 21
        assert wh.alert == 'low'

    def test_none_days_and_alert(self):
        wh = WarehouseRunway(
            warehouse_name='Склад',
            quantity=0,
            days_of_stock=None,
            alert=None,
        )
        assert wh.days_of_stock is None
        assert wh.alert is None


class TestStockRunwayItem:
    def test_construction_with_warehouses(self):
        wh = WarehouseRunway('Москва', 100, 10, 'critical')
        item = StockRunwayItem(
            nm_id=111,
            avg_daily_sales=10.0,
            confidence='high',
            total_stock=100,
            total_days_of_stock=10,
            alert='critical',
            warehouses=[wh],
        )
        assert item.nm_id == 111
        assert item.confidence == 'high'
        assert len(item.warehouses) == 1

    def test_no_sales_fields(self):
        item = StockRunwayItem(
            nm_id=222,
            avg_daily_sales=0.0,
            confidence='none',
            total_stock=50,
            total_days_of_stock=None,
            alert=None,
        )
        assert item.avg_daily_sales == 0.0
        assert item.total_days_of_stock is None
        assert item.alert is None


class TestStockRunwayReport:
    def test_construction(self):
        report = StockRunwayReport(
            computed_at='2026-04-04T11:00:00',
            sales_period_days=30,
        )
        assert report.computed_at == '2026-04-04T11:00:00'
        assert report.sales_period_days == 30
        assert report.items == []

    def test_with_items(self):
        item = StockRunwayItem(
            nm_id=1,
            avg_daily_sales=1.0,
            confidence='medium',
            total_stock=30,
            total_days_of_stock=30,
            alert=None,
        )
        report = StockRunwayReport(
            computed_at='2026-04-04T00:00:00',
            sales_period_days=30,
            items=[item],
        )
        assert len(report.items) == 1
        assert report.items[0].nm_id == 1
