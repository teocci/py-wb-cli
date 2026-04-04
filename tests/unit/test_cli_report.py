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
        svc.get_warehouse_top.return_value = [
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
        ]
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
        svc.get_warehouse_top.return_value = []
        mock_factory.return_value = svc

        result = runner.invoke(app, ['report', 'warehouse', 'top'])
        assert result.exit_code == 0
        assert 'No products' in result.output

    @patch(REPORTS_FACTORY)
    def test_table_output(self, mock_factory):
        svc = MagicMock()
        svc.get_warehouse_top.return_value = [
            ProductStockSummary(
                nm_id=100, brand='TestBrand', subject_name='Shoes',
                vendor_code='V1', total_quantity=150,
                warehouses=[WarehouseStock('Коледино', 150)],
            ),
        ]
        mock_factory.return_value = svc

        result = runner.invoke(app, ['report', 'warehouse', 'top'])
        assert result.exit_code == 0
        assert '100' in result.output
        assert 'TestBrand' in result.output
