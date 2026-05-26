"""Unit tests for FinanceClient and finance domain models."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wb.client.finance import FinanceClient
from wb.core.constants import (
    EP_FINANCE_ACQUIRING_DETAILED,
    EP_FINANCE_ACQUIRING_LIST,
    EP_FINANCE_SALES_REPORT_DETAILED,
    EP_FINANCE_SALES_REPORT_LIST,
)
from wb.domain.finance import AcquiringReportSummary, SalesReportSummary


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_http():
    return MagicMock()


@pytest.fixture
def client(mock_http):
    return FinanceClient(mock_http)


# ── Domain parsing ────────────────────────────────────────────────────


class TestSalesReportSummary:
    def test_from_api_full(self):
        raw = {
            'reportId': 307401554,
            'sellerFinanceName': 'ИП Кружинин В. Р.',
            'dateFrom': '2026-03-16',
            'dateTo': '2026-03-22',
            'createDate': '2026-03-23',
            'currency': 'RUB',
            'reportType': 1,
            'retailAmountSum': '258',
            'forPaySum': '183.79',
            'avgSalePercent': 0,
            'deliveryServiceSum': '2558.47',
            'paidStorageSum': '626.84',
            'paidAcceptanceSum': '243.81',
            'deductionSum': '150',
            'penaltySum': '1457.61',
            'additionalPaymentSum': '9509.71',
            'cashbackAmountSum': '2',
            'cashbackDiscountSum': '19',
            'cashbackCommissionChangeSum': '0.2',
            'paymentSchedule': '-1',
            'bankPaymentSum': '5172.94',
        }
        s = SalesReportSummary.from_api(raw)
        assert s.report_id == 307401554
        assert s.seller_finance_name == 'ИП Кружинин В. Р.'
        assert s.currency == 'RUB'
        assert s.report_type == 1
        assert s.retail_amount_sum == '258'
        assert s.for_pay_sum == '183.79'
        assert s.bank_payment_sum == '5172.94'

    def test_from_api_missing_optional_keys(self):
        # Defensive: empty input should not raise, money fields default to '0'.
        s = SalesReportSummary.from_api({})
        assert s.report_id == 0
        assert s.seller_finance_name == ''
        assert s.retail_amount_sum == '0'
        assert s.bank_payment_sum == '0'
        assert s.avg_sale_percent == 0.0

    def test_from_api_null_percent(self):
        # WB sometimes ships nulls in optional number fields.
        s = SalesReportSummary.from_api({'avgSalePercent': None})
        assert s.avg_sale_percent == 0.0


class TestAcquiringReportSummary:
    def test_from_api_full(self):
        raw = {
            'reportId': 307401555,
            'sellerFinanceName': 'ИП Тест',
            'dateFrom': '2026-03-16',
            'dateTo': '2026-03-22',
            'createDate': '2026-03-31',
            'currency': 'RUB',
            'acquiringFeeSum': '258',
            'acquiringFeeVatSum': '83.79',
        }
        s = AcquiringReportSummary.from_api(raw)
        assert s.report_id == 307401555
        assert s.acquiring_fee_sum == '258'
        assert s.acquiring_fee_vat_sum == '83.79'

    def test_from_api_empty(self):
        s = AcquiringReportSummary.from_api({})
        assert s.report_id == 0
        assert s.acquiring_fee_sum == '0'
        assert s.acquiring_fee_vat_sum == '0'


# ── Client — sales-reports ────────────────────────────────────────────


class TestListSalesReports:
    def test_passes_required_body(self, client, mock_http):
        mock_http.post.return_value = []
        client.list_sales_reports(date_from='2026-01-01', date_to='2026-05-26')
        mock_http.post.assert_called_once_with(
            EP_FINANCE_SALES_REPORT_LIST,
            json_body={'dateFrom': '2026-01-01', 'dateTo': '2026-05-26'},
        )

    def test_optional_params_included_only_when_set(self, client, mock_http):
        mock_http.post.return_value = []
        client.list_sales_reports(
            date_from='2026-01-01', date_to='2026-05-26',
            period='daily', limit=500, offset=10,
        )
        body = mock_http.post.call_args.kwargs['json_body']
        assert body == {
            'dateFrom': '2026-01-01',
            'dateTo': '2026-05-26',
            'period': 'daily',
            'limit': 500,
            'offset': 10,
        }

    def test_non_list_response_returns_empty(self, client, mock_http):
        mock_http.post.return_value = {'error': 'oops'}
        result = client.list_sales_reports(
            date_from='2026-01-01', date_to='2026-05-26',
        )
        assert result == []

    def test_none_204_returns_empty(self, client, mock_http):
        # WB returns 204 No Content → WbHttpClient.post returns None.
        mock_http.post.return_value = None
        result = client.list_sales_reports(
            date_from='2026-01-01', date_to='2026-05-26',
        )
        assert result == []


class TestDetailedSalesReports:
    def test_passes_rrd_id_for_pagination(self, client, mock_http):
        mock_http.post.return_value = []
        client.detailed_sales_reports(
            date_from='2026-01-01', date_to='2026-05-26',
            limit=100_000, rrd_id=42,
        )
        body = mock_http.post.call_args.kwargs['json_body']
        assert body['rrdId'] == 42
        assert body['limit'] == 100_000
        assert mock_http.post.call_args.args[0] == EP_FINANCE_SALES_REPORT_DETAILED


class TestSalesReportById:
    def test_formats_report_id_into_path(self, client, mock_http):
        mock_http.post.return_value = []
        client.sales_report_by_id(123456, rrd_id=0)
        called_path = mock_http.post.call_args.args[0]
        assert called_path == '/api/finance/v1/sales-reports/detailed/123456'

    def test_body_excludes_unset_params(self, client, mock_http):
        mock_http.post.return_value = []
        client.sales_report_by_id(123456)
        body = mock_http.post.call_args.kwargs['json_body']
        assert body == {}


# ── Client — acquiring ────────────────────────────────────────────────


class TestListAcquiringReports:
    def test_default_body(self, client, mock_http):
        mock_http.post.return_value = []
        client.list_acquiring_reports(
            date_from='2026-01-01', date_to='2026-05-26',
        )
        mock_http.post.assert_called_once_with(
            EP_FINANCE_ACQUIRING_LIST,
            json_body={'dateFrom': '2026-01-01', 'dateTo': '2026-05-26'},
        )

    def test_with_limit_offset(self, client, mock_http):
        mock_http.post.return_value = []
        client.list_acquiring_reports(
            date_from='2026-01-01', date_to='2026-05-26',
            limit=100, offset=200,
        )
        body = mock_http.post.call_args.kwargs['json_body']
        assert body == {
            'dateFrom': '2026-01-01',
            'dateTo': '2026-05-26',
            'limit': 100,
            'offset': 200,
        }


class TestDetailedAcquiringReports:
    def test_uses_correct_endpoint(self, client, mock_http):
        mock_http.post.return_value = []
        client.detailed_acquiring_reports(
            date_from='2026-01-01', date_to='2026-05-26',
        )
        assert (
            mock_http.post.call_args.args[0] == EP_FINANCE_ACQUIRING_DETAILED
        )


class TestAcquiringReportById:
    def test_path_template_substitution(self, client, mock_http):
        mock_http.post.return_value = []
        client.acquiring_report_by_id(999)
        called_path = mock_http.post.call_args.args[0]
        assert called_path == '/api/finance/v1/acquiring/detailed/999'
