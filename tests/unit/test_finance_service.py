"""Unit tests for FinanceService — parsing + rrdId pagination loop."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wb.domain.finance import AcquiringReportSummary, SalesReportSummary
from wb.services.finance import DEFAULT_PAGE_SIZE, FinanceService


@pytest.fixture
def mock_client():
    return MagicMock()


@pytest.fixture
def svc(mock_client):
    return FinanceService(mock_client)


# ── list endpoints — parsing ───────────────────────────────────────────


class TestListSalesReports:
    def test_parses_raw_into_summaries(self, svc, mock_client):
        mock_client.list_sales_reports.return_value = [
            {
                'reportId': 1, 'sellerFinanceName': 'A',
                'dateFrom': '2026-05-01', 'dateTo': '2026-05-07',
                'createDate': '2026-05-08', 'currency': 'RUB',
                'reportType': 1, 'retailAmountSum': '100',
                'forPaySum': '90', 'avgSalePercent': 0,
                'deliveryServiceSum': '5', 'paidStorageSum': '2',
                'paidAcceptanceSum': '1', 'deductionSum': '0',
                'penaltySum': '0', 'additionalPaymentSum': '0',
                'cashbackAmountSum': '0', 'cashbackDiscountSum': '0',
                'cashbackCommissionChangeSum': '0',
                'paymentSchedule': '0', 'bankPaymentSum': '82',
            },
        ]
        out = svc.list_sales_reports(date_from='2026-05-01', date_to='2026-05-07')
        assert len(out) == 1
        assert isinstance(out[0], SalesReportSummary)
        assert out[0].report_id == 1
        assert out[0].bank_payment_sum == '82'

    def test_empty_204_yields_empty_list(self, svc, mock_client):
        mock_client.list_sales_reports.return_value = []
        out = svc.list_sales_reports(date_from='2026-05-01', date_to='2026-05-07')
        assert out == []

    def test_none_response_yields_empty_list(self, svc, mock_client):
        # FinanceClient never returns None in the real path, but the
        # service applies its own ``or []`` guard for safety.
        mock_client.list_sales_reports.return_value = None
        out = svc.list_sales_reports(date_from='2026-05-01', date_to='2026-05-07')
        assert out == []


class TestListAcquiringReports:
    def test_parses_raw_into_summaries(self, svc, mock_client):
        mock_client.list_acquiring_reports.return_value = [{
            'reportId': 2, 'sellerFinanceName': 'B',
            'dateFrom': '2026-05-01', 'dateTo': '2026-05-07',
            'createDate': '2026-05-15', 'currency': 'RUB',
            'acquiringFeeSum': '50', 'acquiringFeeVatSum': '8.33',
        }]
        out = svc.list_acquiring_reports(
            date_from='2026-05-01', date_to='2026-05-07',
        )
        assert len(out) == 1
        assert isinstance(out[0], AcquiringReportSummary)
        assert out[0].acquiring_fee_sum == '50'


# ── detailed endpoints — single-page (no --all) ────────────────────────


class TestDetailedSinglePage:
    def test_no_fetch_all_calls_client_once(self, svc, mock_client):
        mock_client.detailed_sales_reports.return_value = [
            {'rrdId': 1}, {'rrdId': 2},
        ]
        out = svc.detailed_sales_reports(
            date_from='2026-05-01', date_to='2026-05-07',
        )
        assert len(out) == 2
        assert mock_client.detailed_sales_reports.call_count == 1

    def test_no_fetch_all_passes_default_page_size(self, svc, mock_client):
        mock_client.detailed_sales_reports.return_value = []
        svc.detailed_sales_reports(
            date_from='2026-05-01', date_to='2026-05-07',
        )
        kw = mock_client.detailed_sales_reports.call_args.kwargs
        assert kw['limit'] == DEFAULT_PAGE_SIZE
        assert kw['rrd_id'] == 0


# ── detailed endpoints — multi-page rrdId loop ─────────────────────────


class TestDetailedPagination:
    def test_three_pages_then_empty(self, svc, mock_client):
        page1 = [{'rrdId': 1}, {'rrdId': 2}]
        page2 = [{'rrdId': 3}, {'rrdId': 4}]
        page3 = [{'rrdId': 5}, {'rrdId': 6}]
        mock_client.detailed_sales_reports.side_effect = [
            page1, page2, page3, [],
        ]
        out = svc.detailed_sales_reports(
            date_from='2026-05-01', date_to='2026-05-07',
            fetch_all=True,
        )
        assert [r['rrdId'] for r in out] == [1, 2, 3, 4, 5, 6]
        assert mock_client.detailed_sales_reports.call_count == 4

    def test_cursor_advances_to_last_rrd(self, svc, mock_client):
        mock_client.detailed_sales_reports.side_effect = [
            [{'rrdId': 100}, {'rrdId': 200}],
            [],
        ]
        svc.detailed_sales_reports(
            date_from='2026-05-01', date_to='2026-05-07',
            fetch_all=True,
        )
        first_call = mock_client.detailed_sales_reports.call_args_list[0]
        second_call = mock_client.detailed_sales_reports.call_args_list[1]
        assert first_call.kwargs['rrd_id'] == 0
        assert second_call.kwargs['rrd_id'] == 200

    def test_stuck_cursor_bails_out(self, svc, mock_client):
        # WB pathology: server echoes the same rrdId forever. We must
        # bail rather than spin.
        same_page = [{'rrdId': 42}]
        mock_client.detailed_sales_reports.side_effect = [same_page, same_page]
        out = svc.detailed_sales_reports(
            date_from='2026-05-01', date_to='2026-05-07',
            fetch_all=True,
        )
        # Service bails on first iteration when last_rrd == cursor.
        # initial cursor=0, page returns rrdId=42 → advance to 42 →
        # second call returns same page with rrdId=42 → bail.
        assert mock_client.detailed_sales_reports.call_count == 2

    def test_missing_rrd_id_bails_out(self, svc, mock_client):
        # If WB ever omits rrdId in a response row, don't crash.
        mock_client.detailed_sales_reports.side_effect = [
            [{'foo': 'bar'}],
            [],
        ]
        out = svc.detailed_sales_reports(
            date_from='2026-05-01', date_to='2026-05-07',
            fetch_all=True,
        )
        # First page kept; loop stops because last row has no rrdId.
        assert out == [{'foo': 'bar'}]
        assert mock_client.detailed_sales_reports.call_count == 1


class TestSalesReportByIdPagination:
    def test_fetch_all_paginates_one_report(self, svc, mock_client):
        mock_client.sales_report_by_id.side_effect = [
            [{'rrdId': 1}, {'rrdId': 2}],
            [{'rrdId': 3}],
            [],
        ]
        out = svc.sales_report_by_id(99, fetch_all=True)
        assert [r['rrdId'] for r in out] == [1, 2, 3]
        assert mock_client.sales_report_by_id.call_count == 3


class TestAcquiringPagination:
    def test_detailed_by_period(self, svc, mock_client):
        mock_client.detailed_acquiring_reports.side_effect = [
            [{'rrdId': 1}], [{'rrdId': 2}], [],
        ]
        out = svc.detailed_acquiring_reports(
            date_from='2026-05-01', date_to='2026-05-07',
            fetch_all=True,
        )
        assert len(out) == 2

    def test_by_id_no_fetch_all(self, svc, mock_client):
        mock_client.acquiring_report_by_id.return_value = [
            {'rrdId': 1}, {'rrdId': 2},
        ]
        out = svc.acquiring_report_by_id(55)
        assert len(out) == 2
        assert mock_client.acquiring_report_by_id.call_count == 1
