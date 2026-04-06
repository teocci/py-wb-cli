"""Unit tests for ProductService composite operations and idempotent mutations."""

from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.core.exceptions import WbCliError
from wb.domain.enums import CampaignStatus, CampaignType, PaymentType
from wb.domain.models import (
    BudgetSnapshot,
    Campaign,
    CampaignOverview,
    CampaignStats,
    MutationResult,
    NmStats,
    ProductSummary,
    SearchCluster,
)
from wb.services.budgets import BudgetService
from wb.services.campaigns import CampaignService
from wb.services.clusters import ClusterService
from wb.services.product import ProductService
from wb.services.stats import StatsService

runner = CliRunner()

PRODUCT_FACTORY = 'wb.services._factory.create_product_service'
CAMPAIGN_FACTORY = 'wb.services._factory.create_campaign_service'

# ── Helpers ──────────────────────────────────────────────────────────────


def _make_campaign(
        campaign_id: int = 1,
        status: CampaignStatus = CampaignStatus.RUNNING,
        nm_ids: list[int] | None = None,
) -> Campaign:
    return Campaign(
        campaign_id=campaign_id,
        name=f'Campaign {campaign_id}',
        status=status,
        campaign_type=CampaignType.STANDARD,
        payment_type=PaymentType.CPM,
        nm_ids=nm_ids or [],
    )


def _make_stats(campaign_id: int = 1, spend: float = 500.0) -> CampaignStats:
    return CampaignStats(
        campaign_id=campaign_id,
        views=1000,
        clicks=50,
        orders=10,
        spend=spend,
        nm_stats=[NmStats(nm_id=100, spend=spend, views=1000, clicks=50, orders=10)],
    )


def _make_budget(campaign_id: int = 1, total: int = 50000, cash: int = 30000) -> BudgetSnapshot:
    return BudgetSnapshot(campaign_id=campaign_id, total=total, cash=cash, netting=20000)


def _make_cluster(nm_id: int = 100, is_active: bool = True) -> SearchCluster:
    return SearchCluster(norm_query='test query', nm_id=nm_id, is_active=is_active)


def _make_product_service(
        campaigns: list[Campaign] | None = None,
        nm_stats: list[NmStats] | None = None,
        budget: BudgetSnapshot | None = None,
        clusters: list[SearchCluster] | None = None,
        analytics_svc=None,
        prices_svc=None,
) -> ProductService:
    """Build a ProductService with mocked sub-services."""
    campaign_svc = MagicMock(spec=CampaignService)
    campaign_svc.list_campaigns.return_value = campaigns or []
    if campaigns:
        campaign_svc.get_campaign.side_effect = lambda cid: next(
            (c for c in campaigns if c.campaign_id == cid), campaigns[0]
        )

    stats_svc = MagicMock(spec=StatsService)
    stats_svc.get_product_spend.return_value = nm_stats or []
    stats_svc.get_campaign_stats.return_value = (
        _make_stats() if budget is None else _make_stats(campaigns[0].campaign_id if campaigns else 1)
    )

    budget_svc = MagicMock(spec=BudgetService)
    budget_svc.get_budget.return_value = budget or _make_budget()

    cluster_svc = MagicMock(spec=ClusterService)
    cluster_svc.list_clusters.return_value = clusters or []

    return ProductService(
        campaign_service=campaign_svc,
        budget_service=budget_svc,
        stats_service=stats_svc,
        cluster_service=cluster_svc,
        analytics_service=analytics_svc,
        prices_service=prices_svc,
    )


# ── ProductService.get_product_summary ──────────────────────────────────


class TestGetProductSummary:
    """get_product_summary unit tests."""

    def test_returns_empty_list_for_no_nm_ids(self) -> None:
        svc = _make_product_service()
        result = svc.get_product_summary([], '2026-04-01', '2026-04-07')
        assert result == []

    def test_returns_one_summary_per_nm_id(self) -> None:
        nm_stats = [NmStats(nm_id=100, spend=200.0), NmStats(nm_id=200, spend=100.0)]
        svc = _make_product_service(nm_stats=nm_stats)
        result = svc.get_product_summary([100, 200], '2026-04-01', '2026-04-07')
        assert len(result) == 2
        assert result[0].nm_id == 100
        assert result[1].nm_id == 200

    def test_ad_spend_populated_from_stats_service(self) -> None:
        nm_stats = [NmStats(nm_id=100, spend=999.0, views=500, clicks=20, orders=5)]
        svc = _make_product_service(nm_stats=nm_stats)
        result = svc.get_product_summary([100], '2026-04-01', '2026-04-07')
        assert result[0].ad_spend == pytest.approx(999.0)
        assert result[0].ad_views == 500
        assert result[0].ad_clicks == 20
        assert result[0].ad_orders == 5

    def test_campaign_ids_populated_from_matching_campaigns(self) -> None:
        camp = _make_campaign(campaign_id=42, nm_ids=[100])
        svc = _make_product_service(campaigns=[camp])
        result = svc.get_product_summary([100], '2026-04-01', '2026-04-07')
        assert 42 in result[0].campaign_ids

    def test_nm_not_in_any_campaign_has_empty_campaign_ids(self) -> None:
        camp = _make_campaign(campaign_id=42, nm_ids=[999])
        svc = _make_product_service(campaigns=[camp])
        result = svc.get_product_summary([100], '2026-04-01', '2026-04-07')
        assert result[0].campaign_ids == []

    def test_cluster_counts_computed(self) -> None:
        camp = _make_campaign(campaign_id=1, nm_ids=[100])
        clusters = [_make_cluster(100, True), _make_cluster(100, False)]
        svc = _make_product_service(campaigns=[camp], clusters=clusters)
        result = svc.get_product_summary([100], '2026-04-01', '2026-04-07')
        assert result[0].cluster_count == 2
        assert result[0].active_cluster_count == 1

    def test_analytics_unavailable_fields_default_zero(self) -> None:
        analytics_svc = MagicMock()
        analytics_svc.get_product_funnel.side_effect = WbCliError('no analytics')
        svc = _make_product_service(analytics_svc=analytics_svc)
        result = svc.get_product_summary([100], '2026-04-01', '2026-04-07')
        assert result[0].open_count == 0
        assert result[0].order_count == 0

    def test_prices_unavailable_fields_default_zero(self) -> None:
        prices_svc = MagicMock()
        prices_svc.get_prices.side_effect = WbCliError('no prices')
        svc = _make_product_service(prices_svc=prices_svc)
        result = svc.get_product_summary([100], '2026-04-01', '2026-04-07')
        assert result[0].base_price == 0.0
        assert result[0].discount == 0

    def test_prices_none_fields_default_zero(self) -> None:
        svc = _make_product_service(prices_svc=None)
        result = svc.get_product_summary([100], '2026-04-01', '2026-04-07')
        assert result[0].base_price == 0.0

    def test_analytics_none_fields_default_zero(self) -> None:
        svc = _make_product_service(analytics_svc=None)
        result = svc.get_product_summary([100], '2026-04-01', '2026-04-07')
        assert result[0].open_count == 0

    def test_prices_data_populates_fields(self) -> None:
        price_mock = MagicMock()
        price_mock.nm_id = 100
        price_mock.vendor_code = 'VC-001'
        price_mock.base_price = 1190.0
        price_mock.final_price = 869.0
        price_mock.discount = 27
        prices_svc = MagicMock()
        prices_svc.get_prices.return_value = [price_mock]
        svc = _make_product_service(prices_svc=prices_svc)
        result = svc.get_product_summary([100], '2026-04-01', '2026-04-07')
        assert result[0].vendor_code == 'VC-001'
        assert result[0].base_price == pytest.approx(1190.0)
        assert result[0].discount == 27

    def test_analytics_data_populates_funnel_fields(self) -> None:
        funnel_mock = MagicMock()
        funnel_mock.nm_id = 100
        funnel_mock.open_count = 500
        funnel_mock.cart_count = 50
        funnel_mock.order_count = 20
        funnel_mock.order_sum = 10000
        analytics_svc = MagicMock()
        analytics_svc.get_product_funnel.return_value = [funnel_mock]
        svc = _make_product_service(analytics_svc=analytics_svc)
        result = svc.get_product_summary([100], '2026-04-01', '2026-04-07')
        assert result[0].open_count == 500
        assert result[0].order_count == 20

    def test_campaigns_error_returns_defaults(self) -> None:
        campaign_svc = MagicMock(spec=CampaignService)
        campaign_svc.list_campaigns.side_effect = WbCliError('api error')
        svc = ProductService(
            campaign_service=campaign_svc,
            budget_service=MagicMock(),
            stats_service=MagicMock(),
            cluster_service=MagicMock(),
        )
        svc._stats.get_product_spend.return_value = []
        result = svc.get_product_summary([100], '2026-04-01', '2026-04-07')
        assert result[0].campaign_ids == []


# ── ProductService.get_campaign_overview ─────────────────────────────────


class TestGetCampaignOverview:
    """get_campaign_overview unit tests."""

    def test_basic_aggregation(self) -> None:
        camp = _make_campaign(campaign_id=1, nm_ids=[100, 200])
        svc = _make_product_service(campaigns=[camp])
        overview = svc.get_campaign_overview(1, '2026-04-01', '2026-04-07')
        assert overview.campaign_id == 1
        assert overview.name == 'Campaign 1'
        assert overview.status == CampaignStatus.RUNNING

    def test_budget_fields_populated(self) -> None:
        camp = _make_campaign(campaign_id=1, nm_ids=[100])
        budget = _make_budget(total=60000, cash=40000)
        svc = _make_product_service(campaigns=[camp], budget=budget)
        overview = svc.get_campaign_overview(1, '2026-04-01', '2026-04-07')
        assert overview.total_budget == 60000
        assert overview.cash == 40000

    def test_stats_fields_populated(self) -> None:
        camp = _make_campaign(campaign_id=1, nm_ids=[100])
        svc = _make_product_service(campaigns=[camp])
        svc._stats.get_campaign_stats.return_value = CampaignStats(
            campaign_id=1, views=2000, clicks=100, orders=20, spend=1500.0,
        )
        overview = svc.get_campaign_overview(1, '2026-04-01', '2026-04-07')
        assert overview.views == 2000
        assert overview.spend == pytest.approx(1500.0)

    def test_cluster_count_across_nms(self) -> None:
        camp = _make_campaign(campaign_id=1, nm_ids=[100, 200])
        clusters = [_make_cluster(100, True), _make_cluster(200, False)]
        svc = _make_product_service(campaigns=[camp], clusters=clusters)
        # list_clusters returns 1 cluster per call (one per nm_id)
        svc._clusters.list_clusters.side_effect = [
            [_make_cluster(100, True)],
            [_make_cluster(200, False)],
        ]
        overview = svc.get_campaign_overview(1, '2026-04-01', '2026-04-07')
        assert overview.cluster_count == 2
        assert overview.active_cluster_count == 1

    def test_budget_error_returns_zero_budget(self) -> None:
        camp = _make_campaign(campaign_id=1, nm_ids=[100])
        svc = _make_product_service(campaigns=[camp])
        svc._budget.get_budget.side_effect = WbCliError('budget error')
        overview = svc.get_campaign_overview(1, '2026-04-01', '2026-04-07')
        assert overview.total_budget == 0
        assert overview.cash == 0

    def test_stats_error_returns_zero_stats(self) -> None:
        camp = _make_campaign(campaign_id=1, nm_ids=[100])
        svc = _make_product_service(campaigns=[camp])
        svc._stats.get_campaign_stats.side_effect = WbCliError('stats error')
        overview = svc.get_campaign_overview(1, '2026-04-01', '2026-04-07')
        assert overview.views == 0
        assert overview.spend == 0.0


# ── Idempotent mutations on CampaignService ───────────────────────────────


class TestIdempotentMutations:
    """Idempotent start/pause/stop on CampaignService."""

    def _make_client(self, campaign_id: int, status: CampaignStatus) -> MagicMock:
        client = MagicMock()
        raw = {
            'id': campaign_id,
            'status': status.value,
            'type': 9,
            'bid_type': 'manual',
            'currency': 'RUB',
            'settings': {'name': 'Test', 'payment_type': 'cpm'},
            'timestamps': {},
            'nm_settings': [],
        }
        client.get_campaign.return_value = raw
        client.list_campaigns.return_value = [raw]
        return client

    def test_start_already_running_returns_already_applied(self) -> None:
        from wb.services.campaigns import CampaignService
        client = self._make_client(1, CampaignStatus.RUNNING)
        svc = CampaignService(client)
        result = svc.start_campaign(1)
        assert result.already_applied is True
        assert result.success is True
        client.start_campaign.assert_not_called()

    def test_pause_already_paused_returns_already_applied(self) -> None:
        from wb.services.campaigns import CampaignService
        client = self._make_client(1, CampaignStatus.PAUSED)
        svc = CampaignService(client)
        result = svc.pause_campaign(1)
        assert result.already_applied is True
        client.pause_campaign.assert_not_called()

    def test_stop_already_stopped_returns_already_applied(self) -> None:
        from wb.services.campaigns import CampaignService
        client = self._make_client(1, CampaignStatus.READY)
        svc = CampaignService(client)
        result = svc.stop_campaign(1)
        assert result.already_applied is True
        client.stop_campaign.assert_not_called()

    def test_start_paused_campaign_calls_api(self) -> None:
        from wb.services.campaigns import CampaignService
        client = self._make_client(1, CampaignStatus.PAUSED)
        svc = CampaignService(client)
        result = svc.start_campaign(1)
        assert result.already_applied is False
        assert result.success is True
        client.start_campaign.assert_called_once_with(1)

    def test_start_dry_run_does_not_check_status(self) -> None:
        from wb.services.campaigns import CampaignService
        client = self._make_client(1, CampaignStatus.RUNNING)
        svc = CampaignService(client)
        result = svc.start_campaign(1, dry_run=True)
        assert result.dry_run is True
        assert result.already_applied is False
        client.get_campaign.assert_not_called()

    def test_mutation_result_already_applied_defaults_false(self) -> None:
        r = MutationResult(success=True, action='test', target_id='1')
        assert r.already_applied is False

    def test_batch_start_skips_already_running(self) -> None:
        from wb.services.campaigns import CampaignService
        client = MagicMock()
        running_raw = {
            'id': 1, 'status': CampaignStatus.RUNNING.value, 'type': 9,
            'bid_type': 'manual', 'currency': 'RUB',
            'settings': {'name': 'R', 'payment_type': 'cpm'},
            'timestamps': {}, 'nm_settings': [],
        }
        paused_raw = {
            'id': 2, 'status': CampaignStatus.PAUSED.value, 'type': 9,
            'bid_type': 'manual', 'currency': 'RUB',
            'settings': {'name': 'P', 'payment_type': 'cpm'},
            'timestamps': {}, 'nm_settings': [],
        }
        client.list_campaigns.return_value = [running_raw, paused_raw]
        svc = CampaignService(client)
        results = svc.start_campaigns([1, 2])
        assert results[0].already_applied is True   # id=1 already RUNNING
        assert results[1].already_applied is False  # id=2 was PAUSED → started
        client.start_campaign.assert_called_once_with(2)

    def test_batch_start_dry_run_does_not_list_campaigns(self) -> None:
        from wb.services.campaigns import CampaignService
        client = MagicMock()
        client.get_campaign.return_value = {
            'id': 1, 'status': CampaignStatus.PAUSED.value, 'type': 9,
            'bid_type': 'manual', 'currency': 'RUB',
            'settings': {'name': 'P', 'payment_type': 'cpm'},
            'timestamps': {}, 'nm_settings': [],
        }
        svc = CampaignService(client)
        results = svc.start_campaigns([1], dry_run=True)
        assert all(r.dry_run for r in results)
        client.list_campaigns.assert_not_called()


# ── CLI wb product summary ─────────────────────────────────────────────


class TestCliProductSummary:
    """CLI tests for 'product summary'."""

    def test_help(self) -> None:
        result = runner.invoke(app, ['product', 'summary', '--help'])
        assert result.exit_code == 0

    @patch(PRODUCT_FACTORY)
    def test_json_output_shape(self, mock_factory: MagicMock) -> None:
        svc = MagicMock()
        svc.get_product_summary.return_value = [
            ProductSummary(nm_id=100, ad_spend=500.0, campaign_ids=[1, 2]),
        ]
        mock_factory.return_value = svc
        result = runner.invoke(app, [
            '--json', 'product', 'summary', '--nms', '100',
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]['nm_id'] == 100
        assert data[0]['ad_spend'] == pytest.approx(500.0)
        assert data[0]['campaign_ids'] == [1, 2]

    @patch(PRODUCT_FACTORY)
    def test_fields_filter_applied(self, mock_factory: MagicMock) -> None:
        svc = MagicMock()
        svc.get_product_summary.return_value = [
            ProductSummary(nm_id=100, ad_spend=200.0),
        ]
        mock_factory.return_value = svc
        result = runner.invoke(app, [
            '--json', '--fields', 'nm_id,ad_spend',
            'product', 'summary', '--nms', '100',
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'nm_id' in data[0]
        assert 'ad_spend' in data[0]
        assert 'campaign_ids' not in data[0]

    @patch(PRODUCT_FACTORY)
    def test_empty_result_message(self, mock_factory: MagicMock) -> None:
        svc = MagicMock()
        svc.get_product_summary.return_value = []
        mock_factory.return_value = svc
        result = runner.invoke(app, [
            '--json', 'product', 'summary', '--nms', '100',
        ])
        assert result.exit_code == 0
        assert 'No data' in result.output

    def test_missing_nms_option_fails(self) -> None:
        result = runner.invoke(app, ['product', 'summary'])
        assert result.exit_code != 0


# ── CLI wb campaign overview ───────────────────────────────────────────


class TestCliCampaignOverview:
    """CLI tests for 'campaign overview'."""

    def test_help(self) -> None:
        result = runner.invoke(app, ['campaign', 'overview', '--help'])
        assert result.exit_code == 0

    @patch(PRODUCT_FACTORY)
    def test_json_output_shape(self, mock_factory: MagicMock) -> None:
        svc = MagicMock()
        svc.get_campaign_overview.return_value = CampaignOverview(
            campaign_id=42,
            name='Test Camp',
            status=CampaignStatus.RUNNING,
            campaign_type=CampaignType.STANDARD,
            nm_ids=[100],
            total_budget=50000,
            views=1000,
        )
        mock_factory.return_value = svc
        result = runner.invoke(app, ['--json', 'campaign', 'overview', '42'])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data['campaign_id'] == 42
        assert data['name'] == 'Test Camp'
        assert data['total_budget'] == 50000

    @patch(PRODUCT_FACTORY)
    def test_days_flag_passed_correctly(self, mock_factory: MagicMock) -> None:
        svc = MagicMock()
        svc.get_campaign_overview.return_value = CampaignOverview(
            campaign_id=1,
            name='X',
            status=CampaignStatus.PAUSED,
            campaign_type=CampaignType.STANDARD,
        )
        mock_factory.return_value = svc
        result = runner.invoke(app, ['--json', 'campaign', 'overview', '1', '--days', '3'])
        assert result.exit_code == 0
        # Verify the service was called (date args computed internally)
        svc.get_campaign_overview.assert_called_once()

    def test_missing_campaign_id_fails(self) -> None:
        result = runner.invoke(app, ['campaign', 'overview'])
        assert result.exit_code != 0
