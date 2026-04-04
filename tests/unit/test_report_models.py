"""Tests for wb.domain.report_models."""

from wb.domain.report_models import (
    ProductStockSummary,
    ReportTask,
    WarehouseRemainItem,
    WarehouseStock,
)


class TestWarehouseStock:
    """Tests for WarehouseStock.from_api."""

    def test_from_api_full(self):
        data = {'warehouseName': 'Коледино', 'quantity': 133}
        ws = WarehouseStock.from_api(data)
        assert ws.warehouse_name == 'Коледино'
        assert ws.quantity == 133

    def test_from_api_missing_fields(self):
        ws = WarehouseStock.from_api({})
        assert ws.warehouse_name == ''
        assert ws.quantity == 0


class TestWarehouseRemainItem:
    """Tests for WarehouseRemainItem.from_api."""

    def test_from_api_full(self):
        data = {
            'brand': 'Wonderful',
            'subjectName': 'Фотоальбомы',
            'vendorCode': '41058/прозрачный',
            'nmId': 183804172,
            'barcode': '2037031652319',
            'techSize': '0',
            'volume': 1.33,
            'warehouses': [
                {'warehouseName': 'Коледино', 'quantity': 133},
                {'warehouseName': 'Невинномысск', 'quantity': 134},
            ],
        }
        item = WarehouseRemainItem.from_api(data)
        assert item.nm_id == 183804172
        assert item.brand == 'Wonderful'
        assert item.vendor_code == '41058/прозрачный'
        assert item.volume == 1.33
        assert len(item.warehouses) == 2
        assert item.warehouses[0].warehouse_name == 'Коледино'
        assert item.warehouses[1].quantity == 134

    def test_total_quantity(self):
        data = {
            'nmId': 1,
            'warehouses': [
                {'warehouseName': 'A', 'quantity': 10},
                {'warehouseName': 'B', 'quantity': 25},
                {'warehouseName': 'C', 'quantity': 5},
            ],
        }
        item = WarehouseRemainItem.from_api(data)
        assert item.total_quantity == 40

    def test_total_quantity_no_warehouses(self):
        item = WarehouseRemainItem.from_api({'nmId': 2})
        assert item.total_quantity == 0

    def test_from_api_missing_fields(self):
        item = WarehouseRemainItem.from_api({})
        assert item.nm_id == 0
        assert item.brand == ''
        assert item.warehouses == []

    def test_from_api_null_warehouses(self):
        item = WarehouseRemainItem.from_api({'nmId': 3, 'warehouses': None})
        assert item.warehouses == []


class TestReportTask:
    """Tests for ReportTask factory methods."""

    def test_from_create(self):
        data = {'data': {'taskId': 'abc-123'}}
        task = ReportTask.from_create(data)
        assert task.task_id == 'abc-123'
        assert task.status == 'new'

    def test_from_create_empty(self):
        task = ReportTask.from_create({})
        assert task.task_id == ''
        assert task.status == 'new'

    def test_from_status_done(self):
        data = {'data': {'id': 'abc-123', 'status': 'done'}}
        task = ReportTask.from_status('abc-123', data)
        assert task.task_id == 'abc-123'
        assert task.status == 'done'
        assert task.is_done is True
        assert task.is_terminal is True

    def test_from_status_processing(self):
        data = {'data': {'id': 'abc-123', 'status': 'processing'}}
        task = ReportTask.from_status('abc-123', data)
        assert task.is_done is False
        assert task.is_terminal is False

    def test_is_terminal_purged(self):
        task = ReportTask(task_id='x', status='purged')
        assert task.is_terminal is True
        assert task.is_done is False

    def test_is_terminal_canceled(self):
        task = ReportTask(task_id='x', status='canceled')
        assert task.is_terminal is True
        assert task.is_done is False


class TestProductStockSummary:
    """Tests for ProductStockSummary dataclass."""

    def test_creation(self):
        wh = [WarehouseStock('WH-A', 50), WarehouseStock('WH-B', 30)]
        summary = ProductStockSummary(
            nm_id=123,
            brand='TestBrand',
            subject_name='Shoes',
            vendor_code='V-001',
            total_quantity=80,
            warehouses=wh,
        )
        assert summary.nm_id == 123
        assert summary.total_quantity == 80
        assert len(summary.warehouses) == 2
