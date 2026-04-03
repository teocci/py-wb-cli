"""Tests for wb.sdk Python SDK facade."""

from unittest.mock import MagicMock, patch

import pytest

from wb.domain.enums import CampaignType, OptimizationAction, PaymentType
from wb.domain.models import Campaign, MutationResult, OptimizationDecision


@pytest.fixture()
def mock_campaign():
    """Create a mock Campaign object."""
    return Campaign(
        campaign_id=123,
        name='Test Campaign',
        status='RUNNING',
        campaign_type=CampaignType.AUTO,
        payment_type=PaymentType.CPM,
        bid_type='manual',
        currency='RUB',
        daily_budget=1000,
        create_time='2025-01-01T00:00:00',
        start_time='2025-01-05T00:00:00',
        updated_time='2025-01-10T00:00:00',
    )


class TestCampaignSDK:
    """Tests for campaign SDK operations."""

    @patch('wb.sdk.create_campaign_service')
    def test_list_campaigns(self, mock_factory, mock_campaign):
        """Test list_campaigns SDK function."""
        mock_svc = MagicMock()
        mock_svc.list_campaigns.return_value = [mock_campaign]
        mock_factory.return_value = mock_svc

        from wb.sdk import list_campaigns
        result = list_campaigns(profile='test')

        assert len(result) == 1
        assert result[0].campaign_id == 123
        mock_factory.assert_called_once_with('test')
        mock_svc.list_campaigns.assert_called_once()

    @patch('wb.sdk.create_campaign_service')
    def test_get_campaign(self, mock_factory, mock_campaign):
        """Test get_campaign SDK function."""
        mock_svc = MagicMock()
        mock_svc.get_campaign.return_value = mock_campaign
        mock_factory.return_value = mock_svc

        from wb.sdk import get_campaign
        result = get_campaign(123, profile='test')

        assert result.campaign_id == 123
        mock_factory.assert_called_once_with('test')
        mock_svc.get_campaign.assert_called_once_with(123)

    @patch('wb.sdk.create_campaign_service')
    def test_create_campaign(self, mock_factory):
        """Test create_campaign SDK function."""
        mock_svc = MagicMock()
        mock_result = MutationResult(
            success=True,
            action='create',
            target_id='456',
            message='Created',
        )
        mock_svc.create_campaign.return_value = mock_result
        mock_factory.return_value = mock_svc

        from wb.sdk import create_campaign
        result = create_campaign(
            name='New Campaign',
            nm_ids=[100, 101],
            dry_run=False,
            profile='test',
        )

        assert result.success is True
        assert result.target_id == '456'
        mock_factory.assert_called_once_with('test')
        mock_svc.create_campaign.assert_called_once()

    @patch('wb.sdk.create_campaign_service')
    def test_clone_campaign_with_defaults(self, mock_factory, mock_campaign):
        """Test clone_campaign with default name."""
        mock_svc = MagicMock()
        mock_svc.get_campaign.return_value = mock_campaign
        mock_result = MutationResult(
            success=True,
            action='create',
            target_id='789',
            message='Cloned',
        )
        mock_svc.create_campaign.return_value = mock_result
        mock_factory.return_value = mock_svc

        from wb.sdk import clone_campaign
        result = clone_campaign(
            campaign_id=123,
            nm_ids=[100, 101],
            profile='test',
        )

        assert result.success is True
        assert result.target_id == '789'
        mock_svc.get_campaign.assert_called_once_with(123)
        # Verify create_campaign was called with correct params
        call_args = mock_svc.create_campaign.call_args
        params = call_args[0][0]
        assert params.name == 'Test Campaign (copy)'
        assert params.nm_ids == [100, 101]
        assert params.bid_type == 'manual'

    @patch('wb.sdk.create_campaign_service')
    def test_clone_campaign_custom_name(self, mock_factory, mock_campaign):
        """Test clone_campaign with custom name."""
        mock_svc = MagicMock()
        mock_svc.get_campaign.return_value = mock_campaign
        mock_result = MutationResult(
            success=True,
            action='create',
            target_id='789',
            message='Cloned',
        )
        mock_svc.create_campaign.return_value = mock_result
        mock_factory.return_value = mock_svc

        from wb.sdk import clone_campaign
        result = clone_campaign(
            campaign_id=123,
            name='Custom Name',
            nm_ids=[100, 101],
            profile='test',
        )

        assert result.success is True
        call_args = mock_svc.create_campaign.call_args
        params = call_args[0][0]
        assert params.name == 'Custom Name'

    @patch('wb.sdk.create_campaign_service')
    def test_clone_campaign_no_nms_raises(self, mock_factory):
        """Test clone_campaign raises ValueError if nm_ids is None."""
        from wb.sdk import clone_campaign

        with pytest.raises(ValueError, match='nm_ids is required'):
            clone_campaign(campaign_id=123, nm_ids=None)

    @patch('wb.sdk.create_campaign_service')
    def test_clone_campaign_empty_nms_raises(self, mock_factory):
        """Test clone_campaign raises ValueError if nm_ids is empty."""
        from wb.sdk import clone_campaign

        with pytest.raises(ValueError, match='nm_ids is required'):
            clone_campaign(campaign_id=123, nm_ids=[])

    @patch('wb.sdk.create_campaign_service')
    def test_start_campaign(self, mock_factory):
        """Test start_campaign SDK function."""
        mock_svc = MagicMock()
        mock_result = MutationResult(
            success=True,
            action='start',
            target_id='123',
            message='Started',
        )
        mock_svc.start_campaign.return_value = mock_result
        mock_factory.return_value = mock_svc

        from wb.sdk import start_campaign
        result = start_campaign(123, dry_run=False, profile='test')

        assert result.success is True
        mock_svc.start_campaign.assert_called_once_with(123, dry_run=False)

    @patch('wb.sdk.create_campaign_service')
    def test_pause_campaign(self, mock_factory):
        """Test pause_campaign SDK function."""
        mock_svc = MagicMock()
        mock_result = MutationResult(
            success=True,
            action='pause',
            target_id='123',
            message='Paused',
        )
        mock_svc.pause_campaign.return_value = mock_result
        mock_factory.return_value = mock_svc

        from wb.sdk import pause_campaign
        result = pause_campaign(123, profile='test')

        assert result.success is True
        mock_svc.pause_campaign.assert_called_once()

    @patch('wb.sdk.create_campaign_service')
    def test_stop_campaign(self, mock_factory):
        """Test stop_campaign SDK function."""
        mock_svc = MagicMock()
        mock_result = MutationResult(
            success=True,
            action='stop',
            target_id='123',
            message='Stopped',
        )
        mock_svc.stop_campaign.return_value = mock_result
        mock_factory.return_value = mock_svc

        from wb.sdk import stop_campaign
        result = stop_campaign(123, profile='test')

        assert result.success is True
        mock_svc.stop_campaign.assert_called_once()


class TestBudgetSDK:
    """Tests for budget SDK operations."""

    @patch('wb.sdk.create_budget_service')
    def test_get_balance(self, mock_factory):
        """Test get_balance SDK function."""
        mock_svc = MagicMock()
        mock_balance = MagicMock()
        mock_svc.get_balance.return_value = mock_balance
        mock_factory.return_value = mock_svc

        from wb.sdk import get_balance
        result = get_balance(profile='test')

        assert result == mock_balance
        mock_factory.assert_called_once_with('test')

    @patch('wb.sdk.create_budget_service')
    def test_get_budget(self, mock_factory):
        """Test get_budget SDK function."""
        mock_svc = MagicMock()
        mock_budget = MagicMock()
        mock_svc.get_budget.return_value = mock_budget
        mock_factory.return_value = mock_svc

        from wb.sdk import get_budget
        result = get_budget(123, profile='test')

        assert result == mock_budget
        mock_svc.get_budget.assert_called_once_with(123)

    @patch('wb.sdk.create_budget_service')
    def test_topup_budget(self, mock_factory):
        """Test topup_budget SDK function."""
        mock_svc = MagicMock()
        mock_result = MutationResult(
            success=True,
            action='topup',
            target_id='123',
            message='Topup',
        )
        mock_svc.topup.return_value = mock_result
        mock_factory.return_value = mock_svc

        from wb.sdk import topup_budget
        result = topup_budget(123, 5000, dry_run=False, profile='test')

        assert result.success is True
        mock_svc.topup.assert_called_once_with(123, 5000, dry_run=False)


class TestClusterSDK:
    """Tests for cluster SDK operations."""

    @patch('wb.sdk.create_cluster_service')
    def test_list_clusters(self, mock_factory):
        """Test list_clusters SDK function."""
        mock_svc = MagicMock()
        mock_svc.list_clusters.return_value = []
        mock_factory.return_value = mock_svc

        from wb.sdk import list_clusters
        result = list_clusters(123, 100, profile='test')

        assert result == []
        mock_svc.list_clusters.assert_called_once_with(123, 100)

    @patch('wb.sdk.create_cluster_service')
    def test_set_cluster_bids(self, mock_factory):
        """Test set_cluster_bids SDK function."""
        mock_svc = MagicMock()
        mock_result = MutationResult(
            success=True,
            action='set_bids',
            target_id='123',
            message='Bids set',
        )
        mock_svc.set_cluster_bids.return_value = mock_result
        mock_factory.return_value = mock_svc

        from wb.sdk import set_cluster_bids
        mutations = []
        result = set_cluster_bids(123, mutations, profile='test')

        assert result.success is True
        mock_svc.set_cluster_bids.assert_called_once()

    @patch('wb.sdk.create_cluster_service')
    def test_set_minus_phrases(self, mock_factory):
        """Test set_minus_phrases SDK function."""
        mock_svc = MagicMock()
        mock_result = MutationResult(
            success=True,
            action='set_phrases',
            target_id='100',
            message='Phrases set',
        )
        mock_svc.set_minus_phrases.return_value = mock_result
        mock_factory.return_value = mock_svc

        from wb.sdk import set_minus_phrases
        result = set_minus_phrases(123, 100, ['phrase1'], profile='test')

        assert result.success is True
        mock_svc.set_minus_phrases.assert_called_once()


class TestOptimizerSDK:
    """Tests for optimizer SDK operations."""

    @patch('wb.sdk.create_optimizer_service')
    def test_plan_clusters(self, mock_factory):
        """Test plan_clusters SDK function."""
        mock_svc = MagicMock()
        mock_decision = OptimizationDecision(
            action=OptimizationAction.RAISE_CLUSTER_BID,
            target_type='cluster',
            target_id='query',
            current_value='100',
            proposed_value='120',
            reason='Test',
            confidence=0.9,
        )
        mock_svc.plan_clusters.return_value = [mock_decision]
        mock_factory.return_value = mock_svc

        from wb.sdk import plan_clusters
        result = plan_clusters(123, 100, '2025-01-01', '2025-01-31', profile='test')

        assert len(result) == 1
        assert result[0].action == OptimizationAction.RAISE_CLUSTER_BID
        mock_svc.plan_clusters.assert_called_once()

    @patch('wb.sdk.create_optimizer_service')
    def test_plan_budget(self, mock_factory):
        """Test plan_budget SDK function."""
        mock_svc = MagicMock()
        mock_svc.plan_budget.return_value = []
        mock_factory.return_value = mock_svc

        from wb.sdk import plan_budget
        result = plan_budget(123, profile='test')

        assert result == []
        mock_svc.plan_budget.assert_called_once_with(123)

    @patch('wb.sdk.create_optimizer_service')
    def test_plan_negatives(self, mock_factory):
        """Test plan_negatives SDK function."""
        mock_svc = MagicMock()
        mock_svc.plan_negatives.return_value = []
        mock_factory.return_value = mock_svc

        from wb.sdk import plan_negatives
        result = plan_negatives(123, 100, '2025-01-01', '2025-01-31', profile='test')

        assert result == []

    @patch('wb.sdk.create_optimizer_service')
    def test_plan_all(self, mock_factory):
        """Test plan_all SDK function."""
        mock_svc = MagicMock()
        mock_svc.plan_all.return_value = []
        mock_factory.return_value = mock_svc

        from wb.sdk import plan_all
        result = plan_all(123, 100, '2025-01-01', '2025-01-31', profile='test')

        assert result == []

    @patch('wb.sdk.create_optimizer_service')
    def test_apply_clusters(self, mock_factory):
        """Test apply_clusters SDK function."""
        mock_svc = MagicMock()
        mock_result = MutationResult(
            success=True,
            action='apply',
            target_id='123',
            message='Applied',
        )
        mock_svc.apply_clusters.return_value = [mock_result]
        mock_factory.return_value = mock_svc

        from wb.sdk import apply_clusters
        result = apply_clusters(123, 100, '2025-01-01', '2025-01-31', profile='test')

        assert len(result) == 1
        assert result[0].success is True

    @patch('wb.sdk.create_optimizer_service')
    def test_apply_all(self, mock_factory):
        """Test apply_all SDK function."""
        mock_svc = MagicMock()
        mock_svc.apply_all.return_value = []
        mock_factory.return_value = mock_svc

        from wb.sdk import apply_all
        result = apply_all(123, 100, '2025-01-01', '2025-01-31', profile='test')

        assert result == []
