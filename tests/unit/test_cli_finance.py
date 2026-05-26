"""Tests for the ``wb finance`` CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.domain.finance import AcquiringReportSummary, SalesReportSummary


runner = CliRunner()

FINANCE_FACTORY = 'wb.services._factory.create_finance_service'


def _sample_sales_summary(report_id: int = 1) -> SalesReportSummary:
    return SalesReportSummary(
        report_id=report_id,
        seller_finance_name='ИП Тест',
        date_from='2026-05-01',
        date_to='2026-05-07',
        create_date='2026-05-08',
        currency='RUB',
        report_type=1,
        retail_amount_sum='1000',
        for_pay_sum='800',
        avg_sale_percent=0.0,
        delivery_service_sum='50',
        paid_storage_sum='20',
        paid_acceptance_sum='10',
        deduction_sum='0',
        penalty_sum='0',
        additional_payment_sum='0',
        cashback_amount_sum='0',
        cashback_discount_sum='0',
        cashback_commission_change_sum='0',
        payment_schedule='0',
        bank_payment_sum='720',
    )


def _sample_acquiring_summary(report_id: int = 2) -> AcquiringReportSummary:
    return AcquiringReportSummary(
        report_id=report_id,
        seller_finance_name='ИП Тест',
        date_from='2026-05-01',
        date_to='2026-05-07',
        create_date='2026-05-15',
        currency='RUB',
        acquiring_fee_sum='50',
        acquiring_fee_vat_sum='8.33',
    )


# ── help ──────────────────────────────────────────────────────────────


class TestHelp:
    def test_root(self):
        result = runner.invoke(app, ['finance', '--help'])
        assert result.exit_code == 0
        assert 'sales-reports' in result.output
        assert 'acquiring' in result.output

    def test_sales_reports_group(self):
        result = runner.invoke(app, ['finance', 'sales-reports', '--help'])
        assert result.exit_code == 0
        for sub in ('list', 'get', 'detailed'):
            assert sub in result.output

    def test_acquiring_group(self):
        result = runner.invoke(app, ['finance', 'acquiring', '--help'])
        assert result.exit_code == 0
        for sub in ('list', 'get', 'detailed'):
            assert sub in result.output


# ── sales-reports list ────────────────────────────────────────────────


class TestSalesReportsList:
    @patch(FINANCE_FACTORY)
    def test_json_output(self, mock_factory):
        svc = MagicMock()
        svc.list_sales_reports.return_value = [_sample_sales_summary(1)]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'finance', 'sales-reports', 'list',
            '--from', '2026-05-01', '--to', '2026-05-07',
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]['report_id'] == 1
        assert data[0]['bank_payment_sum'] == '720'

    @patch(FINANCE_FACTORY)
    def test_table_output(self, mock_factory):
        svc = MagicMock()
        svc.list_sales_reports.return_value = [_sample_sales_summary(7)]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'finance', 'sales-reports', 'list',
            '--from', '2026-05-01', '--to', '2026-05-07',
        ])
        assert result.exit_code == 0, result.output
        # Table title and at least one cell value appear in output.
        assert '7' in result.output
        assert '720' in result.output

    @patch(FINANCE_FACTORY)
    def test_empty_results_table_mode(self, mock_factory):
        svc = MagicMock()
        svc.list_sales_reports.return_value = []
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'finance', 'sales-reports', 'list',
            '--from', '2026-05-01', '--to', '2026-05-07',
        ])
        assert result.exit_code == 0
        assert 'No sales reports' in result.output

    @patch(FINANCE_FACTORY)
    def test_passes_period_through(self, mock_factory):
        svc = MagicMock()
        svc.list_sales_reports.return_value = []
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'finance', 'sales-reports', 'list',
            '--from', '2026-05-01', '--to', '2026-05-07',
            '--period', 'daily',
        ])
        assert result.exit_code == 0
        kw = svc.list_sales_reports.call_args.kwargs
        assert kw['period'] == 'daily'

    def test_bad_period_rejected(self):
        result = runner.invoke(app, [
            'finance', 'sales-reports', 'list',
            '--from', '2026-05-01', '--to', '2026-05-07',
            '--period', 'monthly',
        ])
        # Typer exits 2 on BadParameter.
        assert result.exit_code == 2

    def test_inverted_range_rejected(self):
        result = runner.invoke(app, [
            'finance', 'sales-reports', 'list',
            '--from', '2026-05-07', '--to', '2026-05-01',
        ])
        assert result.exit_code == 2

    def test_unparseable_date_rejected(self):
        result = runner.invoke(app, [
            'finance', 'sales-reports', 'list',
            '--from', 'not-a-date', '--to', '2026-05-07',
        ])
        assert result.exit_code == 2


# ── sales-reports get ─────────────────────────────────────────────────


class TestSalesReportsGet:
    @patch(FINANCE_FACTORY)
    def test_json_passes_through_raw_rows(self, mock_factory):
        svc = MagicMock()
        svc.sales_report_by_id.return_value = [
            {'rrdId': 100, 'nmId': 1234, 'forPay': '50'},
        ]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'finance', 'sales-reports', 'get', '12345',
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data[0]['rrdId'] == 100
        assert data[0]['nmId'] == 1234

    @patch(FINANCE_FACTORY)
    def test_empty_results_table_mode(self, mock_factory):
        svc = MagicMock()
        svc.sales_report_by_id.return_value = []
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'finance', 'sales-reports', 'get', '12345',
        ])
        assert result.exit_code == 0
        assert 'No detail rows' in result.output

    @patch(FINANCE_FACTORY)
    def test_all_flag_propagates(self, mock_factory):
        svc = MagicMock()
        svc.sales_report_by_id.return_value = []
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'finance', 'sales-reports', 'get', '12345', '--all',
        ])
        assert result.exit_code == 0
        assert svc.sales_report_by_id.call_args.kwargs['fetch_all'] is True


# ── sales-reports detailed ────────────────────────────────────────────


class TestSalesReportsDetailed:
    @patch(FINANCE_FACTORY)
    def test_json_passes_through_raw_rows(self, mock_factory):
        svc = MagicMock()
        svc.detailed_sales_reports.return_value = [
            {'rrdId': 1, 'nmId': 9999, 'docTypeName': 'Продажа'},
        ]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'finance', 'sales-reports', 'detailed',
            '--from', '2026-05-01', '--to', '2026-05-07',
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data[0]['nmId'] == 9999
        assert data[0]['docTypeName'] == 'Продажа'

    @patch(FINANCE_FACTORY)
    def test_all_flag_propagates(self, mock_factory):
        svc = MagicMock()
        svc.detailed_sales_reports.return_value = []
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'finance', 'sales-reports', 'detailed',
            '--from', '2026-05-01', '--to', '2026-05-07', '--all',
        ])
        assert result.exit_code == 0
        assert svc.detailed_sales_reports.call_args.kwargs['fetch_all'] is True


# ── acquiring list / get / detailed ───────────────────────────────────


class TestAcquiringList:
    @patch(FINANCE_FACTORY)
    def test_json_output(self, mock_factory):
        svc = MagicMock()
        svc.list_acquiring_reports.return_value = [_sample_acquiring_summary(5)]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'finance', 'acquiring', 'list',
            '--from', '2026-05-01', '--to', '2026-05-07',
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data[0]['report_id'] == 5
        assert data[0]['acquiring_fee_sum'] == '50'

    @patch(FINANCE_FACTORY)
    def test_table_output(self, mock_factory):
        svc = MagicMock()
        svc.list_acquiring_reports.return_value = [_sample_acquiring_summary(5)]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'finance', 'acquiring', 'list',
            '--from', '2026-05-01', '--to', '2026-05-07',
        ])
        assert result.exit_code == 0
        assert '5' in result.output
        assert '50' in result.output

    @patch(FINANCE_FACTORY)
    def test_empty_results(self, mock_factory):
        svc = MagicMock()
        svc.list_acquiring_reports.return_value = []
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'finance', 'acquiring', 'list',
            '--from', '2026-05-01', '--to', '2026-05-07',
        ])
        assert result.exit_code == 0
        assert 'No acquiring reports' in result.output


class TestAcquiringGet:
    @patch(FINANCE_FACTORY)
    def test_json_passes_through_raw_rows(self, mock_factory):
        svc = MagicMock()
        svc.acquiring_report_by_id.return_value = [
            {'rrdId': 1, 'acquiringFee': '14.89', 'acquiringFeeVat': '4.06'},
        ]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'finance', 'acquiring', 'get', '999',
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data[0]['acquiringFee'] == '14.89'


class TestAcquiringDetailed:
    @patch(FINANCE_FACTORY)
    def test_passes_dates_through(self, mock_factory):
        svc = MagicMock()
        svc.detailed_acquiring_reports.return_value = []
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'finance', 'acquiring', 'detailed',
            '--from', '2026-05-01', '--to', '2026-05-07',
        ])
        assert result.exit_code == 0
        kw = svc.detailed_acquiring_reports.call_args.kwargs
        assert kw['date_from'] == '2026-05-01'
        assert kw['date_to'] == '2026-05-07'
        assert kw['fetch_all'] is False
