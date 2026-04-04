"""Tests for the 'report warehouse stock-runway' CLI command."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.core.exceptions import ApiError
from wb.domain.report_models import (
    StockRunwayItem,
    StockRunwayReport,
    WarehouseRunway,
)

runner = CliRunner()

RUNWAY_FACTORY = 'wb.services._factory.create_stock_runway_service'


def _make_report(**kwargs) -> StockRunwayReport:
    defaults = dict(
        computed_at='2026-04-04T10:00:00',
        sales_period_days=30,
        items=[],
    )
    defaults.update(kwargs)
    return StockRunwayReport(**defaults)


def _make_item(nm_id: int = 111, alert: str | None = None) -> StockRunwayItem:
    return StockRunwayItem(
        nm_id=nm_id,
        avg_daily_sales=2.5,
        confidence='high',
        total_stock=100,
        total_days_of_stock=40,
        alert=alert,
        warehouses=[
            WarehouseRunway('Москва', 100, 40, alert),
        ],
    )


class TestStockRunwayHelp:
    def test_help_exits_zero(self):
        result = runner.invoke(app, ['report', 'warehouse', 'stock-runway', '--help'])
        assert result.exit_code == 0
        assert '--days' in result.output


class TestStockRunwayJsonOutput:
    @patch(RUNWAY_FACTORY)
    def test_json_output_structure(self, mock_factory):
        svc = MagicMock()
        report = _make_report(items=[_make_item(999)])
        svc.get_stock_runway.return_value = (report, False)
        mock_factory.return_value = svc

        result = runner.invoke(app, ['--json', 'report', 'warehouse', 'stock-runway'])
        assert result.exit_code == 0, result.output
        parsed = json.loads(result.output)
        assert parsed['sales_period_days'] == 30
        assert parsed['computed_at'] == '2026-04-04T10:00:00'
        assert len(parsed['items']) == 1
        assert parsed['items'][0]['nm_id'] == 999

    @patch(RUNWAY_FACTORY)
    def test_json_passes_days_option(self, mock_factory):
        svc = MagicMock()
        svc.get_stock_runway.return_value = (_make_report(), False)
        mock_factory.return_value = svc

        runner.invoke(app, ['--json', 'report', 'warehouse', 'stock-runway', '--days', '14'])
        svc.get_stock_runway.assert_called_once_with(
            sales_period_days=14,
            poll_timeout=120.0,
            use_cache=True,
        )

    @patch(RUNWAY_FACTORY)
    def test_empty_items_json(self, mock_factory):
        svc = MagicMock()
        svc.get_stock_runway.return_value = (_make_report(), False)
        mock_factory.return_value = svc

        result = runner.invoke(app, ['--json', 'report', 'warehouse', 'stock-runway'])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed['items'] == []


class TestStockRunwayTableOutput:
    @patch(RUNWAY_FACTORY)
    def test_table_output_contains_nm_id(self, mock_factory):
        svc = MagicMock()
        svc.get_stock_runway.return_value = (_make_report(items=[_make_item(42424)]), False)
        mock_factory.return_value = svc

        result = runner.invoke(app, ['report', 'warehouse', 'stock-runway'])
        assert result.exit_code == 0, result.output
        assert '42424' in result.output

    @patch(RUNWAY_FACTORY)
    def test_empty_items_human_output(self, mock_factory):
        svc = MagicMock()
        svc.get_stock_runway.return_value = (_make_report(), False)
        mock_factory.return_value = svc

        result = runner.invoke(app, ['report', 'warehouse', 'stock-runway'])
        assert result.exit_code == 0
        assert 'No products found' in result.output


class TestStockRunwayErrorHandling:
    @patch(RUNWAY_FACTORY)
    def test_api_error_exits_with_code_6(self, mock_factory):
        svc = MagicMock()
        svc.get_stock_runway.side_effect = ApiError('API down')
        mock_factory.return_value = svc

        result = runner.invoke(app, ['report', 'warehouse', 'stock-runway'])
        assert result.exit_code == 6
