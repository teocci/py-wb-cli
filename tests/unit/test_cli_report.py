"""Tests for report CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.domain.report_models import (
    ProductStockSummary,
    ReportTask,
    WarehouseRemainItem,
    WarehouseStock,
)

runner = CliRunner()

REPORTS_FACTORY = 'wb.services._factory.create_reports_service'


class TestWarehouseCreate:
    """Tests for 'report warehouse create'."""

    def test_help(self):
        result = runner.invoke(
            app, ['report', 'warehouse', 'create', '--help'],
        )
        assert result.exit_code == 0
        assert 'group-by-nm' in result.output.lower()

    @patch(REPORTS_FACTORY)
    def test_json_output(self, mock_factory):
        svc = MagicMock()
        svc.create_warehouse_report.return_value = ReportTask(
            task_id='abc-123', status='new',
        )
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'report', 'warehouse', 'create', '--group-by-nm',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed['task_id'] == 'abc-123'
        assert parsed['status'] == 'new'

    @patch(REPORTS_FACTORY)
    def test_table_output(self, mock_factory):
        svc = MagicMock()
        svc.create_warehouse_report.return_value = ReportTask(
            task_id='abc-123', status='new',
        )
        mock_factory.return_value = svc

        result = runner.invoke(app, ['report', 'warehouse', 'create'])
        assert result.exit_code == 0
        assert 'abc-123' in result.output


class TestWarehouseStatus:
    """Tests for 'report warehouse status'."""

    @patch(REPORTS_FACTORY)
    def test_json_done(self, mock_factory):
        svc = MagicMock()
        svc.check_warehouse_status.return_value = ReportTask(
            task_id='abc-123', status='done',
        )
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'report', 'warehouse', 'status', 'abc-123',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed['status'] == 'done'

    @patch(REPORTS_FACTORY)
    def test_table_shows_download_hint(self, mock_factory):
        svc = MagicMock()
        svc.check_warehouse_status.return_value = ReportTask(
            task_id='abc-123', status='done',
        )
        mock_factory.return_value = svc

        result = runner.invoke(app, ['report', 'warehouse', 'status', 'abc-123'])
        assert result.exit_code == 0
        assert 'Download' in result.output or 'download' in result.output.lower()


class TestWarehouseDownload:
    """Tests for 'report warehouse download'."""

    @patch(REPORTS_FACTORY)
    def test_json_output(self, mock_factory):
        svc = MagicMock()
        svc.download_warehouse_report.return_value = [
            WarehouseRemainItem(
                brand='B1', subject_name='S1', vendor_code='V1',
                nm_id=100, barcode='123', tech_size='0', volume=1.5,
                warehouses=[WarehouseStock('WH-A', 50)],
            ),
        ]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'report', 'warehouse', 'download', 'task-001',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed) == 1
        assert parsed[0]['nm_id'] == 100

    @patch(REPORTS_FACTORY)
    def test_empty_report(self, mock_factory):
        svc = MagicMock()
        svc.download_warehouse_report.return_value = []
        mock_factory.return_value = svc

        result = runner.invoke(app, ['report', 'warehouse', 'download', 'task-001'])
        assert result.exit_code == 0
        assert 'No data' in result.output


class TestWarehouseTop:
    """Tests for 'report warehouse top'."""

    @patch(REPORTS_FACTORY)
    def test_json_output(self, mock_factory):
        svc = MagicMock()
        svc.get_warehouse_top.return_value = (
            [
                ProductStockSummary(
                    nm_id=200, brand='B2', subject_name='S2',
                    vendor_code='V2', total_quantity=200,
                    warehouses=[WarehouseStock('WH-A', 200)],
                ),
                ProductStockSummary(
                    nm_id=100, brand='B1', subject_name='S1',
                    vendor_code='V1', total_quantity=80,
                    warehouses=[
                        WarehouseStock('WH-A', 50),
                        WarehouseStock('WH-B', 30),
                    ],
                ),
            ],
            False,
        )
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'report', 'warehouse', 'top', '--limit', '2',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed) == 2
        assert parsed[0]['nm_id'] == 200
        assert parsed[0]['total_quantity'] == 200

    @patch(REPORTS_FACTORY)
    def test_empty_result(self, mock_factory):
        svc = MagicMock()
        svc.get_warehouse_top.return_value = ([], False)
        mock_factory.return_value = svc

        result = runner.invoke(app, ['report', 'warehouse', 'top'])
        assert result.exit_code == 0
        assert 'No products' in result.output

    @patch(REPORTS_FACTORY)
    def test_table_output(self, mock_factory):
        svc = MagicMock()
        svc.get_warehouse_top.return_value = (
            [
                ProductStockSummary(
                    nm_id=100, brand='TestBrand', subject_name='Shoes',
                    vendor_code='V1', total_quantity=150,
                    warehouses=[WarehouseStock('Коледино', 150)],
                ),
            ],
            False,
        )
        mock_factory.return_value = svc

        result = runner.invoke(app, ['report', 'warehouse', 'top'])
        assert result.exit_code == 0
        assert '100' in result.output
        assert 'TestBrand' in result.output


# ── orders / sales tests ─────────────────────────────────────────────


STATISTICS_FACTORY = 'wb.services._factory.create_statistics_client'


def _sample_orders() -> list[dict]:
    """Three orders across two SKUs, one cancelled."""
    return [
        {
            'date': '2026-05-25T10:00:00',
            'lastChangeDate': '2026-05-25T10:15:00',
            'nmId': 101, 'supplierArticle': 'A-1', 'barcode': 'B-1',
            'brand': 'Acme', 'subject': 'Shoes',
            'warehouseName': 'Коледино', 'regionName': 'Москва',
            'totalPrice': 1000, 'discountPercent': 10,
            'priceWithDisc': 900, 'finishedPrice': 850,
            'isCancel': False,
        },
        {
            'date': '2026-05-25T11:30:00',
            'lastChangeDate': '2026-05-25T11:45:00',
            'nmId': 101, 'supplierArticle': 'A-1', 'barcode': 'B-1',
            'brand': 'Acme', 'subject': 'Shoes',
            'warehouseName': 'Электросталь', 'regionName': 'Москва',
            'totalPrice': 1000, 'discountPercent': 10,
            'priceWithDisc': 900, 'finishedPrice': 850,
            'isCancel': True, 'cancelDate': '2026-05-25T12:00:00',
        },
        {
            'date': '2026-05-25T12:00:00',
            'lastChangeDate': '2026-05-25T12:05:00',
            'nmId': 202, 'supplierArticle': 'B-2', 'barcode': 'B-2',
            'brand': 'Beta', 'subject': 'Bags',
            'warehouseName': 'Коледино', 'regionName': 'Санкт-Петербург',
            'totalPrice': 2000, 'discountPercent': 0,
            'priceWithDisc': 2000, 'finishedPrice': 1800,
            'isCancel': False,
        },
    ]


class TestReportOrdersDateResolution:
    """Tests for the --date / --since / --flag resolution logic."""

    @patch(STATISTICS_FACTORY)
    def test_default_yesterday_flag1(self, mock_factory):
        client = MagicMock()
        client.get_orders.return_value = []
        mock_factory.return_value = client

        result = runner.invoke(app, ['--json', 'report', 'orders'])
        assert result.exit_code == 0

        from datetime import date, timedelta
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        client.get_orders.assert_called_once_with(yesterday, flag=1)

    @patch(STATISTICS_FACTORY)
    def test_explicit_date_uses_flag1(self, mock_factory):
        client = MagicMock()
        client.get_orders.return_value = []
        mock_factory.return_value = client

        result = runner.invoke(app, [
            '--json', 'report', 'orders', '--date', '2026-05-20',
        ])
        assert result.exit_code == 0
        client.get_orders.assert_called_once_with('2026-05-20', flag=1)

    @patch(STATISTICS_FACTORY)
    def test_since_uses_flag0(self, mock_factory):
        client = MagicMock()
        client.get_orders.return_value = []
        mock_factory.return_value = client

        result = runner.invoke(app, [
            '--json', 'report', 'orders', '--since', '2026-05-20T10:00:00',
        ])
        assert result.exit_code == 0
        client.get_orders.assert_called_once_with('2026-05-20T10:00:00', flag=0)

    def test_date_and_since_mutually_exclusive(self):
        result = runner.invoke(app, [
            'report', 'orders',
            '--date', '2026-05-20', '--since', '2026-05-19',
        ])
        assert result.exit_code != 0
        assert 'mutually exclusive' in result.output.lower()

    def test_flag_without_date_or_since_rejected(self):
        result = runner.invoke(app, ['report', 'orders', '--flag', '0'])
        assert result.exit_code != 0
        assert 'requires' in result.output.lower()

    def test_flag_mismatch_rejected(self):
        result = runner.invoke(app, [
            'report', 'orders', '--date', '2026-05-20', '--flag', '0',
        ])
        assert result.exit_code != 0


class TestReportOrdersOutput:
    """Tests for --exclude-cancelled, --by-product, and JSON shape."""

    @patch(STATISTICS_FACTORY)
    def test_raw_json_preserves_all_fields(self, mock_factory):
        client = MagicMock()
        client.get_orders.return_value = _sample_orders()
        mock_factory.return_value = client

        result = runner.invoke(app, [
            '--json', 'report', 'orders', '--date', '2026-05-25',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed) == 3
        assert parsed[0]['srid' if 'srid' in parsed[0] else 'nmId'] is not None
        assert parsed[0]['warehouseName'] == 'Коледино'
        assert parsed[1]['isCancel'] is True

    @patch(STATISTICS_FACTORY)
    def test_exclude_cancelled_drops_cancelled_rows(self, mock_factory):
        client = MagicMock()
        client.get_orders.return_value = _sample_orders()
        mock_factory.return_value = client

        result = runner.invoke(app, [
            '--json', 'report', 'orders',
            '--date', '2026-05-25', '--exclude-cancelled',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed) == 2
        assert all(not row.get('isCancel') for row in parsed)

    @patch(STATISTICS_FACTORY)
    def test_by_product_aggregates(self, mock_factory):
        client = MagicMock()
        client.get_orders.return_value = _sample_orders()
        mock_factory.return_value = client

        result = runner.invoke(app, [
            '--json', 'report', 'orders',
            '--date', '2026-05-25', '--by-product',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed) == 2  # Two unique nmIds
        by_nm = {p['nm_id']: p for p in parsed}
        assert by_nm[101]['order_count'] == 2
        assert by_nm[101]['cancelled_count'] == 1
        assert by_nm[101]['total_revenue'] == 1800.0
        assert sorted(by_nm[101]['warehouses']) == ['Коледино', 'Электросталь']
        assert by_nm[202]['order_count'] == 1
        assert by_nm[202]['cancelled_count'] == 0

    @patch(STATISTICS_FACTORY)
    def test_by_product_with_exclude_cancelled(self, mock_factory):
        client = MagicMock()
        client.get_orders.return_value = _sample_orders()
        mock_factory.return_value = client

        result = runner.invoke(app, [
            '--json', 'report', 'orders',
            '--date', '2026-05-25', '--by-product', '--exclude-cancelled',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        by_nm = {p['nm_id']: p for p in parsed}
        assert by_nm[101]['order_count'] == 1
        assert by_nm[101]['cancelled_count'] == 0

    @patch(STATISTICS_FACTORY)
    def test_table_render_non_empty(self, mock_factory):
        client = MagicMock()
        client.get_orders.return_value = _sample_orders()
        mock_factory.return_value = client

        result = runner.invoke(app, [
            'report', 'orders', '--date', '2026-05-25', '--by-product',
        ])
        assert result.exit_code == 0
        assert '101' in result.output
        assert '202' in result.output

    @patch(STATISTICS_FACTORY)
    def test_empty_response_message(self, mock_factory):
        client = MagicMock()
        client.get_orders.return_value = []
        mock_factory.return_value = client

        result = runner.invoke(app, ['report', 'orders', '--date', '2026-05-25'])
        assert result.exit_code == 0
        assert 'no orders' in result.output.lower()


class TestReportSales:
    """Smoke test for the sales command — wraps StatisticsClient.get_sales."""

    @patch(STATISTICS_FACTORY)
    def test_default_calls_get_sales_flag1(self, mock_factory):
        client = MagicMock()
        client.get_sales.return_value = []
        mock_factory.return_value = client

        result = runner.invoke(app, ['--json', 'report', 'sales'])
        assert result.exit_code == 0

        from datetime import date, timedelta
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        client.get_sales.assert_called_once_with(yesterday, flag=1)
        client.get_orders.assert_not_called()

    @patch(STATISTICS_FACTORY)
    def test_by_product_uses_for_pay(self, mock_factory):
        sales = [
            {'date': '2026-05-25', 'nmId': 101, 'supplierArticle': 'A',
             'brand': 'Acme', 'subject': 'Shoes',
             'warehouseName': 'WH', 'regionName': 'RG',
             'priceWithDisc': 1000, 'forPay': 850, 'finishedPrice': 850,
             'saleID': 'S123'},
            {'date': '2026-05-25', 'nmId': 101, 'supplierArticle': 'A',
             'brand': 'Acme', 'subject': 'Shoes',
             'warehouseName': 'WH', 'regionName': 'RG',
             'priceWithDisc': 1000, 'forPay': 850, 'finishedPrice': 850,
             'saleID': 'S124'},
        ]
        client = MagicMock()
        client.get_sales.return_value = sales
        mock_factory.return_value = client

        result = runner.invoke(app, [
            '--json', 'report', 'sales', '--date', '2026-05-25', '--by-product',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed) == 1
        assert parsed[0]['order_count'] == 2
        assert parsed[0]['total_for_pay'] == 1700.0


class TestResolveOrdersQuery:
    """Direct tests for the date-resolution helper (no CLI runner)."""

    def test_default_yesterday(self):
        from datetime import date, timedelta
        from wb.cli.report import _resolve_orders_query

        date_from, flag, label = _resolve_orders_query(None, None, None)
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        assert date_from == yesterday
        assert flag == 1
        assert 'yesterday' in label.lower()

    def test_explicit_date_default_flag(self):
        from wb.cli.report import _resolve_orders_query
        df, fl, _ = _resolve_orders_query('2026-05-20', None, None)
        assert (df, fl) == ('2026-05-20', 1)

    def test_explicit_since_default_flag(self):
        from wb.cli.report import _resolve_orders_query
        df, fl, _ = _resolve_orders_query(None, '2026-05-20T00:00:00', None)
        assert (df, fl) == ('2026-05-20T00:00:00', 0)

    def test_invalid_flag_value_raises(self):
        from wb.cli.report import _resolve_orders_query
        with pytest.raises(typer_bad_param_class()) as ei:
            _resolve_orders_query('2026-05-20', None, 5)
        assert 'flag' in str(ei.value).lower()


def typer_bad_param_class():
    """Return the Typer BadParameter class (import indirection for clarity)."""
    return typer.BadParameter


import typer  # noqa: E402 — needed by typer_bad_param_class
