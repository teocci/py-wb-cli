"""Tests for wb.services.optimizer.OptimizerService."""

from unittest.mock import MagicMock

import pytest

from wb.domain.enums import ClusterClass, OptimizationAction, TargetType
from wb.domain.models import BudgetSnapshot, CampaignStats, ClusterStats, SearchCluster
from wb.services.optimizer import (
    MIN_VIEWS,
    OptimizerService,
    _classify_cluster,
    _view_confidence,
)


@pytest.fixture()
def mock_services():
    """Create mock service dependencies."""
    return {
        'campaign_svc': MagicMock(),
        'bid_svc': MagicMock(),
        'cluster_svc': MagicMock(),
        'stats_svc': MagicMock(),
        'budget_svc': MagicMock(),
    }


@pytest.fixture()
def service(mock_services):
    """Create an OptimizerService with mock dependencies."""
    return OptimizerService(**mock_services)


def _make_cluster_stats(
    norm_query: str = 'sneakers',
    views: int = 200,
    clicks: int = 10,
    ctr: float = 5.0,
    orders: int = 2,
    spend: int = 1000,
    avg_pos: float = 3.0,
) -> ClusterStats:
    """Build a ClusterStats for testing."""
    return ClusterStats(
        norm_query=norm_query,
        views=views,
        clicks=clicks,
        ctr=ctr,
        orders=orders,
        spend=spend,
        avg_pos=avg_pos,
    )


# ── View confidence ──────────────────────────────────────────────────


class TestViewConfidence:
    """Tests for _view_confidence helper."""

    def test_full_confidence(self):
        assert _view_confidence(200) == 1.0
        assert _view_confidence(500) == 1.0

    def test_partial_confidence(self):
        assert _view_confidence(100) == 0.5

    def test_zero_views(self):
        assert _view_confidence(0) == 0.0


# ── Cluster classification ───────────────────────────────────────────


class TestClassifyCluster:
    """Tests for _classify_cluster helper."""

    def test_efficient_cluster(self):
        stats = _make_cluster_stats(ctr=5.0, orders=3)
        assert _classify_cluster(stats) == ClusterClass.EFFICIENT

    def test_visible_weak_cluster(self):
        stats = _make_cluster_stats(ctr=0.5, orders=0, spend=100)
        assert _classify_cluster(stats) == ClusterClass.VISIBLE_WEAK

    def test_expensive_non_converting(self):
        stats = _make_cluster_stats(ctr=2.0, orders=0, spend=600)
        assert _classify_cluster(stats) == ClusterClass.EXPENSIVE_NON_CONVERTING

    def test_noisy_exclusion_wasteful_and_low_ctr(self):
        """Test NOISY_EXCLUSION classification for wasteful + low CTR cluster.

        Need views < MIN_VIEWS to avoid VISIBLE_WEAK classification.
        """
        stats = _make_cluster_stats(views=20, ctr=0.5, orders=0, spend=600)
        assert _classify_cluster(stats) == ClusterClass.NOISY_EXCLUSION


# ── Plan clusters ────────────────────────────────────────────────────


class TestPlanClusters:
    """Tests for OptimizerService.plan_clusters."""

    def test_efficient_cluster_gets_raise(self, service, mock_services):
        mock_services['cluster_svc'].get_cluster_stats.return_value = [
            _make_cluster_stats(ctr=5.0, orders=3, avg_pos=6.0),
        ]
        mock_services['cluster_svc'].get_cluster_bids.return_value = [
            SearchCluster(norm_query='sneakers', bid=500, nm_id=100),
        ]

        decisions = service.plan_clusters(1, 100, '2025-01-01', '2025-01-31')

        assert len(decisions) == 1
        assert decisions[0].action == OptimizationAction.RAISE_CLUSTER_BID
        assert decisions[0].target_id == 'sneakers'
        assert int(decisions[0].proposed_value) == 600  # 500 * 1.2

    def test_visible_weak_cluster_gets_lower(self, service, mock_services):
        mock_services['cluster_svc'].get_cluster_stats.return_value = [
            _make_cluster_stats(ctr=0.5, orders=0, spend=100),
        ]
        mock_services['cluster_svc'].get_cluster_bids.return_value = [
            SearchCluster(norm_query='sneakers', bid=300, nm_id=100),
        ]

        decisions = service.plan_clusters(1, 100, '2025-01-01', '2025-01-31')

        assert len(decisions) == 1
        assert decisions[0].action == OptimizationAction.LOWER_CLUSTER_BID
        assert int(decisions[0].proposed_value) == 240  # 300 * 0.8

    def test_wasteful_cluster_gets_delete(self, service, mock_services):
        mock_services['cluster_svc'].get_cluster_stats.return_value = [
            _make_cluster_stats(ctr=2.0, orders=0, spend=600),
        ]
        mock_services['cluster_svc'].get_cluster_bids.return_value = [
            SearchCluster(norm_query='sneakers', bid=400, nm_id=100),
        ]

        decisions = service.plan_clusters(1, 100, '2025-01-01', '2025-01-31')

        assert len(decisions) == 1
        assert decisions[0].action == OptimizationAction.DELETE_CLUSTER_BID

    def test_low_views_cluster_skipped(self, service, mock_services):
        mock_services['cluster_svc'].get_cluster_stats.return_value = [
            _make_cluster_stats(views=30),
        ]
        mock_services['cluster_svc'].get_cluster_bids.return_value = []

        decisions = service.plan_clusters(1, 100, '2025-01-01', '2025-01-31')

        assert len(decisions) == 0

    def test_empty_stats(self, service, mock_services):
        mock_services['cluster_svc'].get_cluster_stats.return_value = []
        mock_services['cluster_svc'].get_cluster_bids.return_value = []

        decisions = service.plan_clusters(1, 100, '2025-01-01', '2025-01-31')

        assert decisions == []

    def test_no_bid_efficient_cluster_skipped(self, service, mock_services):
        """Efficient cluster with no existing bid produces no decision."""
        mock_services['cluster_svc'].get_cluster_stats.return_value = [
            _make_cluster_stats(ctr=5.0, orders=3),
        ]
        mock_services['cluster_svc'].get_cluster_bids.return_value = []

        decisions = service.plan_clusters(1, 100, '2025-01-01', '2025-01-31')

        assert decisions == []


# ── Plan budget ──────────────────────────────────────────────────────


class TestPlanBudget:
    """Tests for OptimizerService.plan_budget."""

    def test_budget_at_risk(self, service, mock_services):
        mock_services['budget_svc'].get_budget.return_value = BudgetSnapshot(
            campaign_id=1, total=10000, cash=1000,
        )

        decisions = service.plan_budget(1)

        assert len(decisions) == 1
        assert decisions[0].action == OptimizationAction.TOPUP_BUDGET
        assert int(decisions[0].proposed_value) == 5000

    def test_budget_healthy(self, service, mock_services):
        mock_services['budget_svc'].get_budget.return_value = BudgetSnapshot(
            campaign_id=1, total=10000, cash=5000,
        )

        decisions = service.plan_budget(1)

        assert decisions == []

    def test_zero_budget(self, service, mock_services):
        mock_services['budget_svc'].get_budget.return_value = BudgetSnapshot(
            campaign_id=1, total=0, cash=0,
        )

        decisions = service.plan_budget(1)

        assert decisions == []


# ── Plan negatives ───────────────────────────────────────────────────


class TestPlanNegatives:
    """Tests for OptimizerService.plan_negatives."""

    def test_wasteful_cluster_recommended(self, service, mock_services):
        mock_services['cluster_svc'].get_cluster_stats.return_value = [
            _make_cluster_stats(
                norm_query='bad shoes', views=100, orders=0, spend=600,
            ),
        ]

        decisions = service.plan_negatives(1, 100, '2025-01-01', '2025-01-31')

        assert len(decisions) == 1
        assert decisions[0].action == OptimizationAction.ADD_MINUS_PHRASE
        assert decisions[0].target_id == 'bad shoes'

    def test_converting_cluster_not_recommended(self, service, mock_services):
        mock_services['cluster_svc'].get_cluster_stats.return_value = [
            _make_cluster_stats(orders=5, spend=600),
        ]

        decisions = service.plan_negatives(1, 100, '2025-01-01', '2025-01-31')

        assert decisions == []


# ── Plan portfolio ───────────────────────────────────────────────────


class TestPlanPortfolio:
    """Tests for OptimizerService.plan_portfolio."""

    def test_clicks_no_orders_recommends_pause(self, service, mock_services):
        mock_services['stats_svc'].get_campaign_stats.return_value = CampaignStats(
            campaign_id=1, views=500, clicks=100, orders=0,
        )

        decisions = service.plan_portfolio(1, '2025-01-01', '2025-01-31')

        assert len(decisions) == 1
        assert decisions[0].action == OptimizationAction.PAUSE_CAMPAIGN

    def test_healthy_campaign_no_decision(self, service, mock_services):
        mock_services['stats_svc'].get_campaign_stats.return_value = CampaignStats(
            campaign_id=1, views=500, clicks=100, orders=10,
        )

        decisions = service.plan_portfolio(1, '2025-01-01', '2025-01-31')

        assert decisions == []


# ── Plan all ─────────────────────────────────────────────────────────


class TestPlanAll:
    """Tests for OptimizerService.plan_all."""

    def test_combines_cluster_and_budget(self, service, mock_services):
        mock_services['cluster_svc'].get_cluster_stats.return_value = [
            _make_cluster_stats(ctr=0.5, orders=0, spend=100),
        ]
        mock_services['cluster_svc'].get_cluster_bids.return_value = [
            SearchCluster(norm_query='sneakers', bid=300, nm_id=100),
        ]
        mock_services['budget_svc'].get_budget.return_value = BudgetSnapshot(
            campaign_id=1, total=10000, cash=500,
        )

        decisions = service.plan_all(1, 100, '2025-01-01', '2025-01-31')

        actions = {d.action for d in decisions}
        assert OptimizationAction.LOWER_CLUSTER_BID in actions
        assert OptimizationAction.TOPUP_BUDGET in actions


# ── Apply decisions ──────────────────────────────────────────────────


class TestApplyDecisions:
    """Tests for _apply_decision routing."""

    def test_apply_clusters_calls_service(self, service, mock_services):
        mock_services['cluster_svc'].get_cluster_stats.return_value = [
            _make_cluster_stats(ctr=0.5, orders=0, spend=100),
        ]
        mock_services['cluster_svc'].get_cluster_bids.return_value = [
            SearchCluster(norm_query='sneakers', bid=300, nm_id=100),
        ]
        mock_services['cluster_svc'].set_cluster_bids.return_value = MagicMock(
            success=True,
        )

        results = service.apply_clusters(
            1, 100, '2025-01-01', '2025-01-31', dry_run=True,
        )

        assert len(results) == 1

    def test_apply_budget_calls_topup(self, service, mock_services):
        mock_services['budget_svc'].get_budget.return_value = BudgetSnapshot(
            campaign_id=1, total=10000, cash=500,
        )
        mock_services['budget_svc'].topup.return_value = MagicMock(success=True)

        results = service.apply_budget(1, dry_run=True)

        assert len(results) == 1

    def test_apply_negatives_batches_phrases(self, service, mock_services):
        mock_services['cluster_svc'].get_cluster_stats.return_value = [
            _make_cluster_stats(
                norm_query='bad1', views=100, orders=0, spend=600,
            ),
            _make_cluster_stats(
                norm_query='bad2', views=150, orders=0, spend=700,
            ),
        ]
        mock_services['cluster_svc'].set_minus_phrases.return_value = MagicMock(
            success=True,
        )

        results = service.apply_negatives(
            1, 100, '2025-01-01', '2025-01-31', dry_run=True,
        )

        assert len(results) == 1
        call_args = mock_services['cluster_svc'].set_minus_phrases.call_args
        assert 'bad1' in call_args[0][2]
        assert 'bad2' in call_args[0][2]

    def test_apply_empty_decisions(self, service, mock_services):
        mock_services['cluster_svc'].get_cluster_stats.return_value = []
        mock_services['cluster_svc'].get_cluster_bids.return_value = []

        results = service.apply_clusters(
            1, 100, '2025-01-01', '2025-01-31',
        )

        assert results == []


# ── Decision explainability ──────────────────────────────────────────


class TestDecisionExplainability:
    """Tests that decisions contain explainable reason strings."""

    def test_cluster_decision_has_reason(self, service, mock_services):
        mock_services['cluster_svc'].get_cluster_stats.return_value = [
            _make_cluster_stats(ctr=5.0, orders=3),
        ]
        mock_services['cluster_svc'].get_cluster_bids.return_value = [
            SearchCluster(norm_query='sneakers', bid=500, nm_id=100),
        ]

        decisions = service.plan_clusters(1, 100, '2025-01-01', '2025-01-31')

        assert decisions[0].reason
        assert 'sneakers' in decisions[0].reason

    def test_budget_decision_has_reason(self, service, mock_services):
        mock_services['budget_svc'].get_budget.return_value = BudgetSnapshot(
            campaign_id=1, total=10000, cash=500,
        )

        decisions = service.plan_budget(1)

        assert decisions[0].reason
        assert 'exhaustion' in decisions[0].reason

    def test_negative_decision_has_reason(self, service, mock_services):
        mock_services['cluster_svc'].get_cluster_stats.return_value = [
            _make_cluster_stats(orders=0, spend=600),
        ]

        decisions = service.plan_negatives(1, 100, '2025-01-01', '2025-01-31')

        assert decisions[0].reason
        assert 'exclusion' in decisions[0].reason
