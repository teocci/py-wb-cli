"""Tests for DailyReportRow, StatsService.get_daily_report, and CLI daily-report."""

from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.domain.analytics_models import ProductFunnelStats
from wb.domain.models import DailyReportRow, NmStats
from wb.services.stats import StatsService

runner = CliRunner()

STATS_FACTORY = 'wb.services._factory.create_stats_service'
ANALYTICS_FACTORY = 'wb.services._factory.create_analytics_service'


# ── Helpers ───────────────────────────────────────────────────────────


def _make_client(
        campaigns: list[dict] | None = None,
        fullstats: list[dict] | None = None,
) -> MagicMock:
    client = MagicMock()
    client.list_campaigns.return_value = campaigns or []
    client.get_campaign_stats.return_value = fullstats or []
    return client


def _fullstats_payload(
        advert_id: int = 1,
        nm_id: int = 100,
        name: str = 'Product A',
        spend: float = 500.0,
        orders: int = 10,
) -> dict:
    return {
        'advertId': advert_id,
        'views': 1000, 'clicks': 50, 'ctr': 5.0,
        'orders': orders, 'sum': spend, 'cpc': 10.0,
        'cr': 1.0, 'atbs': 20, 'shks': 8, 'currency': 'RUB',
        'days': [{
            'date': '2026-04-19',
            'views': 1000, 'clicks': 50, 'orders': orders, 'sum': spend,
            'apps': [{'nms': [{
                'nmId': nm_id, 'name': name,
                'views': 1000, 'clicks': 50, 'ctr': 5.0,
                'orders': orders, 'sum': spend,
                'cpc': 10.0, 'cr': 1.0, 'atbs': 20, 'shks': 8,
            }]}],
        }],
    }


def _make_analytics_svc(nm_id: int, order_count: int) -> MagicMock:
    funnel_row = ProductFunnelStats(nm_id=nm_id, title='Product A', order_count=order_count)
    svc = MagicMock()
    svc.get_product_funnel.return_value = [funnel_row]
    return svc


# ── DailyReportRow model ──────────────────────────────────────────────


class TestDailyReportRow:
    def test_defaults(self) -> None:
        row = DailyReportRow(nm_id=123)
        assert row.name == ''
        assert row.ad_spend == 0.0
        assert row.total_orders == 0

    def test_asdict(self) -> None:
        row = DailyReportRow(nm_id=100, name='P', ad_spend=300.0, total_orders=50)
        d = asdict(row)
        assert d == {'nm_id': 100, 'name': 'P', 'ad_spend': 300.0, 'total_orders': 50}


# ── StatsService._collect_nm_ids_by_status ────────────────────────────


class TestCollectNmIdsByStatus:
    def test_collects_nm_ids_from_campaigns(self) -> None:
        client = _make_client(campaigns=[
            {'id': 1, 'nm_settings': [{'nm_id': 100}, {'nm_id': 200}]},
            {'id': 2, 'nm_settings': [{'nm_id': 200}, {'nm_id': 300}]},
        ])
        svc = StatsService(client)
        result = svc._collect_nm_ids_by_status([9, 11])
        assert set(result) == {100, 200, 300}

    def test_passes_statuses_to_client(self) -> None:
        client = _make_client(campaigns=[])
        svc = StatsService(client)
        svc._collect_nm_ids_by_status([9])
        client.list_campaigns.assert_called_once_with(status=[9])

    def test_handles_null_nm_settings(self) -> None:
        client = _make_client(campaigns=[{'id': 1, 'nm_settings': None}])
        svc = StatsService(client)
        result = svc._collect_nm_ids_by_status([9])
        assert result == []

    def test_empty_campaigns_returns_empty(self) -> None:
        client = _make_client(campaigns=[])
        svc = StatsService(client)
        assert svc._collect_nm_ids_by_status([9]) == []


# ── StatsService._fetch_funnel_orders ────────────────────────────────


class TestFetchFunnelOrders:
    def test_returns_empty_when_no_analytics_svc(self) -> None:
        svc = StatsService(_make_client())
        result = svc._fetch_funnel_orders([100], '2026-04-19', None)
        assert result == {}

    def test_returns_order_counts_from_funnel(self) -> None:
        analytics = _make_analytics_svc(nm_id=100, order_count=223)
        svc = StatsService(_make_client())
        result = svc._fetch_funnel_orders([100], '2026-04-19', analytics)
        assert result == {100: 223}

    def test_returns_empty_on_analytics_exception(self) -> None:
        analytics = MagicMock()
        analytics.get_product_funnel.side_effect = Exception('403 Forbidden')
        svc = StatsService(_make_client())
        result = svc._fetch_funnel_orders([100], '2026-04-19', analytics)
        assert result == {}

    def test_passes_date_as_both_begin_and_end(self) -> None:
        analytics = _make_analytics_svc(100, 10)
        svc = StatsService(_make_client())
        svc._fetch_funnel_orders([100], '2026-04-19', analytics)
        analytics.get_product_funnel.assert_called_once_with(
            '2026-04-19', '2026-04-19', nm_ids=[100],
        )


# ── StatsService.get_daily_report ────────────────────────────────────


class TestGetDailyReport:
    def test_returns_empty_when_no_campaigns(self) -> None:
        client = _make_client(campaigns=[])
        svc = StatsService(client)
        assert svc.get_daily_report('2026-04-19') == []

    def test_joins_spend_and_total_orders(self) -> None:
        client = _make_client(
            campaigns=[{'id': 1, 'nm_settings': [{'nm_id': 100}]}],
            fullstats=[_fullstats_payload(nm_id=100, spend=1250.0, orders=47)],
        )
        analytics = _make_analytics_svc(nm_id=100, order_count=223)
        svc = StatsService(client)
        result = svc.get_daily_report('2026-04-19', analytics_svc=analytics)
        assert len(result) == 1
        row = result[0]
        assert row.nm_id == 100
        assert row.ad_spend == pytest.approx(1250.0)
        assert row.total_orders == 223

    def test_total_orders_zero_when_no_analytics(self) -> None:
        client = _make_client(
            campaigns=[{'id': 1, 'nm_settings': [{'nm_id': 100}]}],
            fullstats=[_fullstats_payload(nm_id=100, spend=500.0)],
        )
        svc = StatsService(client)
        result = svc.get_daily_report('2026-04-19', analytics_svc=None)
        assert result[0].total_orders == 0

    def test_sorted_by_ad_spend_descending(self) -> None:
        raw = {
            'advertId': 1,
            'views': 0, 'clicks': 0, 'ctr': 0, 'orders': 0,
            'sum': 700.0, 'cpc': 0, 'cr': 0, 'atbs': 0, 'shks': 0,
            'currency': 'RUB',
            'days': [{
                'date': '2026-04-19', 'views': 0, 'clicks': 0, 'orders': 0, 'sum': 700.0,
                'apps': [{'nms': [
                    {'nmId': 10, 'name': 'A', 'views': 0, 'clicks': 0, 'ctr': 0,
                     'orders': 0, 'sum': 200.0, 'cpc': 0, 'cr': 0, 'atbs': 0, 'shks': 0},
                    {'nmId': 20, 'name': 'B', 'views': 0, 'clicks': 0, 'ctr': 0,
                     'orders': 0, 'sum': 500.0, 'cpc': 0, 'cr': 0, 'atbs': 0, 'shks': 0},
                ]}],
            }],
        }
        client = _make_client(
            campaigns=[{'id': 1, 'nm_settings': [{'nm_id': 10}, {'nm_id': 20}]}],
            fullstats=[raw],
        )
        svc = StatsService(client)
        result = svc.get_daily_report('2026-04-19')
        assert result[0].nm_id == 20
        assert result[1].nm_id == 10

    def test_uses_active_statuses_by_default(self) -> None:
        client = _make_client(campaigns=[])
        svc = StatsService(client)
        svc.get_daily_report('2026-04-19')
        client.list_campaigns.assert_called_once_with(status=[9, 11])

    def test_respects_custom_statuses(self) -> None:
        client = _make_client(campaigns=[])
        svc = StatsService(client)
        svc.get_daily_report('2026-04-19', statuses=[9])
        client.list_campaigns.assert_called_once_with(status=[9])

    def test_validation_error_on_bad_date(self) -> None:
        from wb.core.exceptions import ValidationError
        svc = StatsService(_make_client())
        with pytest.raises(ValidationError):
            svc.get_daily_report('not-a-date')

    def test_product_name_taken_from_spend_row(self) -> None:
        client = _make_client(
            campaigns=[{'id': 1, 'nm_settings': [{'nm_id': 100}]}],
            fullstats=[_fullstats_payload(nm_id=100, name='Test Perfume', spend=300.0)],
        )
        svc = StatsService(client)
        result = svc.get_daily_report('2026-04-19')
        assert result[0].name == 'Test Perfume'


# ── CLI stats daily-report ────────────────────────────────────────────


class TestCliDailyReport:
    def test_help(self) -> None:
        result = runner.invoke(app, ['stats', 'daily-report', '--help'])
        assert result.exit_code == 0

    @patch(ANALYTICS_FACTORY)
    @patch(STATS_FACTORY)
    def test_json_output(self, mock_stats: MagicMock, mock_analytics: MagicMock) -> None:
        svc = MagicMock()
        svc.get_daily_report.return_value = [
            DailyReportRow(nm_id=100, name='Product A', ad_spend=1250.0, total_orders=223),
        ]
        mock_stats.return_value = svc
        mock_analytics.return_value = MagicMock()

        result = runner.invoke(app, [
            '--json', 'stats', 'daily-report', '--date', '2026-04-19',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]['nm_id'] == 100
        assert parsed[0]['ad_spend'] == 1250.0
        assert parsed[0]['total_orders'] == 223

    @patch(ANALYTICS_FACTORY)
    @patch(STATS_FACTORY)
    def test_empty_result_shows_message(
            self, mock_stats: MagicMock, mock_analytics: MagicMock,
    ) -> None:
        svc = MagicMock()
        svc.get_daily_report.return_value = []
        mock_stats.return_value = svc
        mock_analytics.return_value = MagicMock()

        result = runner.invoke(app, [
            '--json', 'stats', 'daily-report', '--date', '2026-04-19',
        ])
        assert result.exit_code == 0
        assert 'No active campaigns' in result.output

    def test_invalid_status_exits_with_error(self) -> None:
        result = runner.invoke(app, [
            'stats', 'daily-report', '--date', '2026-04-19', '--status', 'invalid',
        ])
        assert result.exit_code != 0

    @patch(ANALYTICS_FACTORY)
    @patch(STATS_FACTORY)
    def test_passes_status_map_to_service(
            self, mock_stats: MagicMock, mock_analytics: MagicMock,
    ) -> None:
        svc = MagicMock()
        svc.get_daily_report.return_value = []
        mock_stats.return_value = svc
        mock_analytics.return_value = MagicMock()

        runner.invoke(app, [
            '--json', 'stats', 'daily-report',
            '--date', '2026-04-19', '--status', 'running',
        ])
        call_kwargs = svc.get_daily_report.call_args
        assert call_kwargs.kwargs['statuses'] == [9]

    @patch(ANALYTICS_FACTORY, side_effect=Exception('no token'))
    @patch(STATS_FACTORY)
    def test_graceful_degradation_when_analytics_unavailable(
            self, mock_stats: MagicMock, mock_analytics: MagicMock,
    ) -> None:
        svc = MagicMock()
        svc.get_daily_report.return_value = [
            DailyReportRow(nm_id=100, name='P', ad_spend=500.0, total_orders=0),
        ]
        mock_stats.return_value = svc

        result = runner.invoke(app, [
            '--json', 'stats', 'daily-report', '--date', '2026-04-19',
        ])
        assert result.exit_code == 0
        call_kwargs = svc.get_daily_report.call_args
        assert call_kwargs.kwargs.get('analytics_svc') is None
