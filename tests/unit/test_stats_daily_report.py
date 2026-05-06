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


def _make_analytics_svc(
        nm_id: int,
        order_count: int = 0,
        open_count: int = 0,
        cart_count: int = 0,
        order_sum: int = 0,
        buyout_count: int = 0,
) -> MagicMock:
    funnel_row = ProductFunnelStats(
        nm_id=nm_id,
        title='Product A',
        open_count=open_count,
        cart_count=cart_count,
        order_count=order_count,
        order_sum=order_sum,
        buyout_count=buyout_count,
    )
    svc = MagicMock()
    svc.get_product_funnel.return_value = [funnel_row]
    return svc


def _make_rich_row(nm_id: int = 100, **kwargs) -> DailyReportRow:
    defaults = dict(
        name='Product A',
        views=1000, clicks=50, ad_orders=10,
        spend=500.0, avg_position=0.0,
        opens=200, cart_adds=80, orders=30,
        order_sum=15000, buyouts=25,
    )
    defaults.update(kwargs)
    return DailyReportRow(nm_id=nm_id, **defaults)


# ── DailyReportRow model ──────────────────────────────────────────────


class TestDailyReportRow:
    def test_defaults(self) -> None:
        row = DailyReportRow(nm_id=123)
        assert row.name == ''
        assert row.spend == 0.0
        assert row.orders == 0
        assert row.views == 0
        assert row.clicks == 0
        assert row.ad_orders == 0
        assert row.avg_position == 0.0
        assert row.opens == 0
        assert row.cart_adds == 0
        assert row.order_sum == 0
        assert row.buyouts == 0

    def test_asdict_has_all_eleven_fields(self) -> None:
        row = DailyReportRow(
            nm_id=100, name='P',
            views=10, clicks=5, ad_orders=2,
            spend=300.0, avg_position=3.5,
            opens=50, cart_adds=20, orders=8,
            order_sum=4000, buyouts=7,
        )
        d = asdict(row)
        assert set(d.keys()) == {
            'nm_id', 'name',
            'views', 'clicks', 'ad_orders', 'spend', 'avg_position',
            'opens', 'cart_adds', 'orders', 'order_sum', 'buyouts',
        }
        assert d['spend'] == 300.0
        assert d['orders'] == 8
        assert d['buyouts'] == 7


# ── StatsService._collect_nm_ids_from_campaigns ──────────────────────


class TestCollectNmIdsFromCampaigns:
    """F-11: in-memory status filter over a pre-fetched campaign list."""

    def test_collects_nm_ids_across_matching_campaigns(self) -> None:
        svc = StatsService(_make_client())
        result = svc._collect_nm_ids_from_campaigns(
            [
                {'id': 1, 'status': 9, 'nm_settings': [{'nm_id': 100}, {'nm_id': 200}]},
                {'id': 2, 'status': 11, 'nm_settings': [{'nm_id': 200}, {'nm_id': 300}]},
            ],
            status_set={9, 11},
        )
        assert set(result) == {100, 200, 300}

    def test_excludes_campaigns_with_non_matching_status(self) -> None:
        svc = StatsService(_make_client())
        result = svc._collect_nm_ids_from_campaigns(
            [
                {'id': 1, 'status': 9, 'nm_settings': [{'nm_id': 100}]},
                {'id': 2, 'status': 7, 'nm_settings': [{'nm_id': 200}]},  # stopped
            ],
            status_set={9, 11},
        )
        assert set(result) == {100}

    def test_handles_null_nm_settings(self) -> None:
        svc = StatsService(_make_client())
        result = svc._collect_nm_ids_from_campaigns(
            [{'id': 1, 'status': 9, 'nm_settings': None}],
            status_set={9},
        )
        assert result == []

    def test_empty_campaigns_returns_empty(self) -> None:
        svc = StatsService(_make_client())
        assert svc._collect_nm_ids_from_campaigns([], status_set={9}) == []


# ── StatsService._fetch_funnel_rows ──────────────────────────────────


class TestFetchFunnelRows:
    def test_returns_empty_when_no_analytics_svc(self) -> None:
        svc = StatsService(_make_client())
        result = svc._fetch_funnel_rows([100], '2026-04-19', '2026-04-19', None)
        assert result == {}

    def test_returns_full_funnel_objects_keyed_by_nm_id(self) -> None:
        analytics = _make_analytics_svc(nm_id=100, order_count=223, open_count=500)
        svc = StatsService(_make_client())
        result = svc._fetch_funnel_rows([100], '2026-04-19', '2026-04-19', analytics)
        assert 100 in result
        assert result[100].order_count == 223
        assert result[100].open_count == 500

    def test_returns_empty_on_analytics_exception(self) -> None:
        analytics = MagicMock()
        analytics.get_product_funnel.side_effect = Exception('403 Forbidden')
        svc = StatsService(_make_client())
        result = svc._fetch_funnel_rows([100], '2026-04-19', '2026-04-19', analytics)
        assert result == {}

    def test_passes_date_range_to_analytics(self) -> None:
        analytics = _make_analytics_svc(100, 10)
        svc = StatsService(_make_client())
        svc._fetch_funnel_rows([100], '2026-04-13', '2026-04-19', analytics)
        analytics.get_product_funnel.assert_called_once_with(
            '2026-04-13', '2026-04-19', nm_ids=[100],
        )


# ── StatsService.get_daily_report ────────────────────────────────────


class TestGetDailyReport:
    def test_returns_empty_when_no_campaigns(self) -> None:
        client = _make_client(campaigns=[])
        svc = StatsService(client)
        assert svc.get_daily_report('2026-04-19') == []

    def test_joins_spend_and_funnel_rich_shape(self) -> None:
        client = _make_client(
            campaigns=[{'id': 1, 'status': 9, 'nm_settings': [{'nm_id': 100}]}],
            fullstats=[_fullstats_payload(nm_id=100, spend=1250.0, orders=47)],
        )
        analytics = _make_analytics_svc(
            nm_id=100, order_count=223, open_count=500,
            cart_count=80, order_sum=15000, buyout_count=20,
        )
        svc = StatsService(client)
        result = svc.get_daily_report('2026-04-19', analytics_svc=analytics)
        assert len(result) == 1
        row = result[0]
        assert row.nm_id == 100
        assert row.spend == pytest.approx(1250.0)
        assert row.ad_orders == 47
        assert row.views == 1000
        assert row.clicks == 50
        assert row.orders == 223
        assert row.opens == 500
        assert row.cart_adds == 80
        assert row.order_sum == 15000
        assert row.buyouts == 20

    def test_funnel_fields_zero_when_no_analytics(self) -> None:
        client = _make_client(
            campaigns=[{'id': 1, 'status': 9, 'nm_settings': [{'nm_id': 100}]}],
            fullstats=[_fullstats_payload(nm_id=100, spend=500.0)],
        )
        svc = StatsService(client)
        result = svc.get_daily_report('2026-04-19', analytics_svc=None)
        row = result[0]
        assert row.orders == 0
        assert row.opens == 0
        assert row.cart_adds == 0
        assert row.order_sum == 0
        assert row.buyouts == 0

    def test_sorted_by_spend_descending(self) -> None:
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
            campaigns=[{'id': 1, 'status': 9, 'nm_settings': [{'nm_id': 10}, {'nm_id': 20}]}],
            fullstats=[raw],
        )
        svc = StatsService(client)
        result = svc.get_daily_report('2026-04-19')
        assert result[0].nm_id == 20
        assert result[1].nm_id == 10

    def test_uses_active_statuses_by_default(self) -> None:
        """Default statuses [9, 11] filter in-memory; stopped campaigns excluded."""
        client = _make_client(
            campaigns=[
                {'id': 1, 'status': 9, 'nm_settings': [{'nm_id': 100}]},
                {'id': 2, 'status': 11, 'nm_settings': [{'nm_id': 200}]},
                {'id': 3, 'status': 7, 'nm_settings': [{'nm_id': 300}]},  # stopped
            ],
            fullstats=[_fullstats_payload(advert_id=1, nm_id=100, spend=100.0)],
        )
        svc = StatsService(client)
        result = svc.get_daily_report('2026-04-19')
        result_nm_ids = {r.nm_id for r in result}
        assert 300 not in result_nm_ids
        assert result_nm_ids <= {100, 200}

    def test_respects_custom_statuses(self) -> None:
        client = _make_client(
            campaigns=[
                {'id': 1, 'status': 9, 'nm_settings': [{'nm_id': 100}]},
                {'id': 2, 'status': 11, 'nm_settings': [{'nm_id': 200}]},
            ],
            fullstats=[_fullstats_payload(advert_id=1, nm_id=100, spend=100.0)],
        )
        svc = StatsService(client)
        result = svc.get_daily_report('2026-04-19', statuses=[9])
        result_nm_ids = {r.nm_id for r in result}
        assert 200 not in result_nm_ids

    def test_calls_list_campaigns_exactly_once(self) -> None:
        """F-11: dedup — list_campaigns must fire once per daily-report, not twice."""
        client = _make_client(
            campaigns=[{'id': 1, 'status': 9, 'nm_settings': [{'nm_id': 100}]}],
            fullstats=[_fullstats_payload(nm_id=100, spend=500.0)],
        )
        svc = StatsService(client)
        svc.get_daily_report('2026-04-19')
        assert client.list_campaigns.call_count == 1

    def test_list_campaigns_called_without_status_filter(self) -> None:
        """F-11: the single call is unfiltered — statuses applied client-side."""
        client = _make_client(
            campaigns=[{'id': 1, 'status': 9, 'nm_settings': [{'nm_id': 100}]}],
            fullstats=[_fullstats_payload(nm_id=100, spend=500.0)],
        )
        svc = StatsService(client)
        svc.get_daily_report('2026-04-19', statuses=[9])
        client.list_campaigns.assert_called_once_with()

    def test_validation_error_on_bad_date(self) -> None:
        from wb.core.exceptions import ValidationError
        svc = StatsService(_make_client())
        with pytest.raises(ValidationError):
            svc.get_daily_report('not-a-date')

    def test_product_name_taken_from_spend_row(self) -> None:
        client = _make_client(
            campaigns=[{'id': 1, 'status': 9, 'nm_settings': [{'nm_id': 100}]}],
            fullstats=[_fullstats_payload(nm_id=100, name='Test Perfume', spend=300.0)],
        )
        svc = StatsService(client)
        result = svc.get_daily_report('2026-04-19')
        assert result[0].name == 'Test Perfume'


# ── StatsService.get_daily_report — range mode ───────────────────────


class TestGetDailyReportRange:
    def test_passes_date_range_to_spend_and_funnel(self) -> None:
        """Range mode threads date_to through both spend and funnel fetches."""
        client = _make_client(
            campaigns=[{'id': 1, 'status': 9, 'nm_settings': [{'nm_id': 100}]}],
            fullstats=[_fullstats_payload(nm_id=100, spend=800.0)],
        )
        analytics = _make_analytics_svc(nm_id=100, order_count=50)
        svc = StatsService(client)

        result = svc.get_daily_report(
            '2026-04-13', date_to='2026-04-19', analytics_svc=analytics,
        )

        analytics.get_product_funnel.assert_called_once_with(
            '2026-04-13', '2026-04-19', nm_ids=[100],
        )
        client.get_campaign_stats.assert_called_once_with(
            [1], '2026-04-13', '2026-04-19',
        )
        assert len(result) == 1
        assert result[0].spend == pytest.approx(800.0)
        assert result[0].orders == 50

    def test_single_date_and_same_date_to_are_equivalent(self) -> None:
        """get_daily_report('D') and get_daily_report('D', date_to='D') produce identical calls."""
        client_a = _make_client(
            campaigns=[{'id': 1, 'status': 9, 'nm_settings': [{'nm_id': 100}]}],
            fullstats=[_fullstats_payload(nm_id=100, spend=500.0)],
        )
        client_b = _make_client(
            campaigns=[{'id': 1, 'status': 9, 'nm_settings': [{'nm_id': 100}]}],
            fullstats=[_fullstats_payload(nm_id=100, spend=500.0)],
        )
        svc_a = StatsService(client_a)
        svc_b = StatsService(client_b)

        svc_a.get_daily_report('2026-04-19')
        svc_b.get_daily_report('2026-04-19', date_to='2026-04-19')

        assert client_a.get_campaign_stats.call_args == client_b.get_campaign_stats.call_args

    def test_range_cache_key_differs_from_single_date(self) -> None:
        """Range and single-date entries must not collide in the response cache."""
        from unittest.mock import MagicMock

        from wb.storage.response_cache import ResponseCache

        cache = MagicMock(spec=ResponseCache)
        cache.get.return_value = None

        client = _make_client(
            campaigns=[{'id': 1, 'status': 9, 'nm_settings': [{'nm_id': 100}]}],
            fullstats=[_fullstats_payload(nm_id=100, spend=500.0)],
        )
        svc = StatsService(client, response_cache=cache, cache_token='tok')

        svc.get_daily_report('2026-04-13')
        key_single = cache.put.call_args[0][0]

        cache.reset_mock()
        cache.get.return_value = None

        svc.get_daily_report('2026-04-13', date_to='2026-04-19')
        key_range = cache.put.call_args[0][0]

        assert key_single != key_range


# ── StatsService._cached_or_fetch — stale schema ─────────────────────


class TestStaleCacheGuard:
    def test_stale_cache_entry_falls_through_to_fresh_fetch(self) -> None:
        """Old cache schema (ad_spend/total_orders) triggers fresh fetch, no crash."""
        from wb.storage.response_cache import ResponseCache

        cache = MagicMock(spec=ResponseCache)
        # Old schema: DailyReportRow(**old_row) raises TypeError on unknown fields
        old_row = [{'nm_id': 100, 'name': 'P', 'ad_spend': 500.0, 'total_orders': 10}]
        cache.get.return_value = old_row

        client = _make_client(
            campaigns=[{'id': 1, 'status': 9, 'nm_settings': [{'nm_id': 100}]}],
            fullstats=[_fullstats_payload(nm_id=100, spend=500.0)],
        )
        svc = StatsService(client, response_cache=cache, cache_token='tok')

        result = svc.get_daily_report('2026-04-13')

        # Fresh fetch ran despite cache hit
        client.list_campaigns.assert_called_once()
        assert result[0].spend == pytest.approx(500.0)


# ── CLI stats daily-report ────────────────────────────────────────────


class TestCliDailyReport:
    def test_help(self) -> None:
        result = runner.invoke(app, ['stats', 'daily-report', '--help'])
        assert result.exit_code == 0

    @patch(ANALYTICS_FACTORY)
    @patch(STATS_FACTORY)
    def test_json_output_has_rich_shape(
            self, mock_stats: MagicMock, mock_analytics: MagicMock,
    ) -> None:
        svc = MagicMock()
        svc.get_daily_report.return_value = [_make_rich_row(nm_id=100)]
        mock_stats.return_value = svc
        mock_analytics.return_value = MagicMock()

        result = runner.invoke(app, [
            '--json', 'stats', 'daily-report', '--date', '2026-04-19',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        row = parsed[0]
        assert row['nm_id'] == 100
        assert row['spend'] == 500.0
        assert row['orders'] == 30
        assert row['opens'] == 200
        assert row['cart_adds'] == 80
        assert row['buyouts'] == 25
        assert row['ad_orders'] == 10
        assert row['views'] == 1000
        assert row['clicks'] == 50

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
        svc.get_daily_report.return_value = [_make_rich_row(nm_id=100, orders=0)]
        mock_stats.return_value = svc

        result = runner.invoke(app, [
            '--json', 'stats', 'daily-report', '--date', '2026-04-19',
        ])
        assert result.exit_code == 0
        call_kwargs = svc.get_daily_report.call_args
        assert call_kwargs.kwargs.get('analytics_svc') is None

    @patch(ANALYTICS_FACTORY)
    @patch(STATS_FACTORY)
    def test_days_mode_passes_range_to_service(
            self, mock_stats: MagicMock, mock_analytics: MagicMock,
    ) -> None:
        """--days 3 resolves to (today-3, today-1) and passes date_to to service."""
        from datetime import date, timedelta

        svc = MagicMock()
        svc.get_daily_report.return_value = []
        mock_stats.return_value = svc
        mock_analytics.return_value = MagicMock()

        today = date.today()
        expected_from = str(today - timedelta(days=3))
        expected_to = str(today - timedelta(days=1))

        runner.invoke(app, ['--json', 'stats', 'daily-report', '--days', '3'])

        call_args = svc.get_daily_report.call_args
        assert call_args.args[0] == expected_from
        assert call_args.kwargs['date_to'] == expected_to

    @patch(ANALYTICS_FACTORY)
    @patch(STATS_FACTORY)
    def test_from_to_mode_passes_range_to_service(
            self, mock_stats: MagicMock, mock_analytics: MagicMock,
    ) -> None:
        svc = MagicMock()
        svc.get_daily_report.return_value = []
        mock_stats.return_value = svc
        mock_analytics.return_value = MagicMock()

        runner.invoke(app, [
            '--json', 'stats', 'daily-report',
            '--from', '2026-04-28', '--to', '2026-05-02',
        ])

        call_args = svc.get_daily_report.call_args
        assert call_args.args[0] == '2026-04-28'
        assert call_args.kwargs['date_to'] == '2026-05-02'

    @patch(ANALYTICS_FACTORY)
    @patch(STATS_FACTORY)
    def test_fields_projection_narrows_json_output(
            self, mock_stats: MagicMock, mock_analytics: MagicMock,
    ) -> None:
        """--fields nm_id,name,spend,orders emits only those 4 keys."""
        svc = MagicMock()
        svc.get_daily_report.return_value = [_make_rich_row(nm_id=100)]
        mock_stats.return_value = svc
        mock_analytics.return_value = MagicMock()

        result = runner.invoke(app, [
            '--json', '--fields', 'nm_id,name,spend,orders',
            'stats', 'daily-report', '--date', '2026-04-19',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert set(parsed[0].keys()) == {'nm_id', 'name', 'spend', 'orders'}


# ── CLI _resolve_daily_range validation ──────────────────────────────


class TestResolveDailyRange:
    """Unit tests for the date-filter validator (black-box via CLI exit codes)."""

    def _invoke(self, *args: str) -> int:
        result = runner.invoke(app, ['stats', 'daily-report', *args])
        return result.exit_code

    @patch(ANALYTICS_FACTORY)
    @patch(STATS_FACTORY)
    def test_mutual_exclusion_date_and_days(
            self, mock_stats: MagicMock, mock_analytics: MagicMock,
    ) -> None:
        mock_stats.return_value = MagicMock(get_daily_report=MagicMock(return_value=[]))
        mock_analytics.return_value = MagicMock()
        code = self._invoke('--date', '2026-04-19', '--days', '3')
        assert code != 0

    @patch(ANALYTICS_FACTORY)
    @patch(STATS_FACTORY)
    def test_mutual_exclusion_date_and_from_to(
            self, mock_stats: MagicMock, mock_analytics: MagicMock,
    ) -> None:
        mock_stats.return_value = MagicMock(get_daily_report=MagicMock(return_value=[]))
        mock_analytics.return_value = MagicMock()
        code = self._invoke('--date', '2026-04-19', '--from', '2026-04-13', '--to', '2026-04-19')
        assert code != 0

    @patch(ANALYTICS_FACTORY)
    @patch(STATS_FACTORY)
    def test_missing_to_with_from(
            self, mock_stats: MagicMock, mock_analytics: MagicMock,
    ) -> None:
        mock_stats.return_value = MagicMock(get_daily_report=MagicMock(return_value=[]))
        mock_analytics.return_value = MagicMock()
        code = self._invoke('--from', '2026-04-13')
        assert code != 0

    @patch(ANALYTICS_FACTORY)
    @patch(STATS_FACTORY)
    def test_range_exceeds_7_days(
            self, mock_stats: MagicMock, mock_analytics: MagicMock,
    ) -> None:
        mock_stats.return_value = MagicMock(get_daily_report=MagicMock(return_value=[]))
        mock_analytics.return_value = MagicMock()
        code = self._invoke('--from', '2026-04-11', '--to', '2026-04-19')
        assert code != 0

    @patch(ANALYTICS_FACTORY)
    @patch(STATS_FACTORY)
    def test_days_exceeds_7(
            self, mock_stats: MagicMock, mock_analytics: MagicMock,
    ) -> None:
        mock_stats.return_value = MagicMock(get_daily_report=MagicMock(return_value=[]))
        mock_analytics.return_value = MagicMock()
        code = self._invoke('--days', '8')
        assert code != 0

    @patch(ANALYTICS_FACTORY)
    @patch(STATS_FACTORY)
    def test_inverted_range(
            self, mock_stats: MagicMock, mock_analytics: MagicMock,
    ) -> None:
        mock_stats.return_value = MagicMock(get_daily_report=MagicMock(return_value=[]))
        mock_analytics.return_value = MagicMock()
        code = self._invoke('--from', '2026-04-19', '--to', '2026-04-13')
        assert code != 0
