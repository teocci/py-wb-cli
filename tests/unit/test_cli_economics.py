"""Tests for the ``wb economics`` CLI commands (I-26)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from wb.cli.app import app
from wb.domain.economics_models import EconomicsPeriod, ProductEconomics


runner = CliRunner()

FACTORY = 'wb.services._factory.create_economics_service'


def _sample(nm_id: int = 1, **overrides) -> ProductEconomics:
    base = dict(
        nm_id=nm_id, vendor_code='VC-1', subject_name='Subject', brand='Brand',
        units_in_stock=10, units_sold=2, revenue=2000.0, avg_sale_price=1000.0,
        commission_rub=300.0, acquiring_rub=10.0, logistics_rub=100.0,
        storage_rub=0.0, deductions_rub=0.0, gross_payout_rub=1500.0,
        net_payout_rub=1400.0, wb_cost_total=600.0, wb_cost_per_sold=300.0,
        period_cost_per_sold=0.0, margin_per_sold=700.0, margin_pct=70.0,
        wb_cost_per_held=60.0, storage_per_held=0.0, cogs_per_unit=None,
        net_profit_per_sold=None, period_costs_apportioned=False,
        stock_from_cache=False,
    )
    base.update(overrides)
    return ProductEconomics(**base)


def _period(**overrides) -> EconomicsPeriod:
    base = dict(
        revenue=2000.0, gross_payout=1500.0, logistics=100.0, storage=200.0,
        deductions=300.0, bank_payment=900.0, wb_cost_total=1100.0,
        wb_cost_pct=55.0, products=1,
    )
    base.update(overrides)
    return EconomicsPeriod(**base)


def _mock_svc(products, period=None):
    svc = MagicMock()
    svc.get_product_economics.return_value = (products, period or _period())
    return svc


class TestHelp:
    def test_group_help(self):
        result = runner.invoke(app, ['economics', '--help'])
        assert result.exit_code == 0
        assert 'product' in result.output

    def test_command_help_lists_flags(self):
        result = runner.invoke(app, ['economics', 'product', '--help'])
        assert result.exit_code == 0
        for flag in ('--from', '--to', '--scope', '--apportion', '--cogs-file', '--min-stock'):
            assert flag in result.output


class TestProductCommand:
    @patch(FACTORY)
    def test_json_output(self, mock_factory):
        mock_factory.return_value = _mock_svc([_sample(1)])
        result = runner.invoke(app, [
            '--json', 'economics', 'product',
            '--from', '2026-05-01', '--to', '2026-05-31',
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data[0]['nm_id'] == 1
        assert data[0]['wb_cost_total'] == 600.0
        assert data[0]['margin_per_sold'] == 700.0
        assert data[0]['period_costs_apportioned'] is False

    @patch(FACTORY)
    def test_table_output_with_period_footer(self, mock_factory):
        mock_factory.return_value = _mock_svc([_sample(7)])
        result = runner.invoke(app, [
            'economics', 'product', '--from', '2026-05-01', '--to', '2026-05-31',
        ])
        assert result.exit_code == 0, result.output
        assert '7' in result.output
        assert 'VC-1' in result.output
        assert 'bank_payment' in result.output  # period footer

    @patch(FACTORY)
    def test_empty_results_still_shows_period(self, mock_factory):
        mock_factory.return_value = _mock_svc([])
        result = runner.invoke(app, [
            'economics', 'product', '--from', '2026-05-01', '--to', '2026-05-31',
        ])
        assert result.exit_code == 0
        assert 'No products' in result.output
        assert 'bank_payment' in result.output

    @patch(FACTORY)
    def test_apportion_passed_through(self, mock_factory):
        svc = _mock_svc([])
        mock_factory.return_value = svc
        result = runner.invoke(app, [
            'economics', 'product', '--from', '2026-05-01', '--to', '2026-05-31',
            '--apportion',
        ])
        assert result.exit_code == 0
        assert svc.get_product_economics.call_args.kwargs['apportion'] is True

    @patch(FACTORY)
    def test_scope_passed_through(self, mock_factory):
        svc = _mock_svc([])
        mock_factory.return_value = svc
        result = runner.invoke(app, [
            'economics', 'product', '--from', '2026-05-01', '--to', '2026-05-31',
            '--scope', 'all',
        ])
        assert result.exit_code == 0
        assert svc.get_product_economics.call_args.kwargs['scope'] == 'all'

    @patch(FACTORY)
    def test_cogs_file_parsed(self, mock_factory, tmp_path):
        svc = _mock_svc([])
        mock_factory.return_value = svc
        cogs = tmp_path / 'cogs.json'
        cogs.write_text(json.dumps({'1': 100.0, '2': 50}), encoding='utf-8')
        result = runner.invoke(app, [
            'economics', 'product', '--from', '2026-05-01', '--to', '2026-05-31',
            '--cogs-file', str(cogs),
        ])
        assert result.exit_code == 0, result.output
        assert svc.get_product_economics.call_args.kwargs['cogs_map'] == {1: 100.0, 2: 50.0}


class TestValidation:
    def test_inverted_date_range(self):
        result = runner.invoke(app, [
            'economics', 'product', '--from', '2026-05-31', '--to', '2026-05-01',
        ])
        assert result.exit_code != 0
        assert 'after' in result.output.lower()

    def test_invalid_scope(self):
        result = runner.invoke(app, [
            'economics', 'product', '--from', '2026-05-01', '--to', '2026-05-31',
            '--scope', 'bogus',
        ])
        assert result.exit_code != 0
        assert 'scope' in result.output.lower()

    def test_malformed_cogs_file(self, tmp_path):
        cogs = tmp_path / 'bad.json'
        cogs.write_text('{not json', encoding='utf-8')
        result = runner.invoke(app, [
            'economics', 'product', '--from', '2026-05-01', '--to', '2026-05-31',
            '--cogs-file', str(cogs),
        ])
        assert result.exit_code != 0

    def test_negative_cogs_value(self, tmp_path):
        cogs = tmp_path / 'neg.json'
        cogs.write_text(json.dumps({'1': -5}), encoding='utf-8')
        result = runner.invoke(app, [
            'economics', 'product', '--from', '2026-05-01', '--to', '2026-05-31',
            '--cogs-file', str(cogs),
        ])
        assert result.exit_code != 0
        assert 'negative' in result.output.lower()


class TestFactory:
    @patch('wb.services._factory.create_finance_service')
    @patch('wb.services._factory.create_reports_service')
    def test_create_economics_service(self, mock_reports, mock_finance):
        from wb.services._factory import create_economics_service
        from wb.services.economics import EconomicsService

        svc = create_economics_service('some_profile')
        assert isinstance(svc, EconomicsService)
        mock_reports.assert_called_once_with('some_profile')
        mock_finance.assert_called_once_with('some_profile')
