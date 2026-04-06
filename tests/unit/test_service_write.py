"""Tests for write methods in CampaignService, BudgetService, BidService."""

from unittest.mock import MagicMock

import pytest

from wb.core.constants import BID_BATCH_SIZE
from wb.core.exceptions import ValidationError, WbCliError
from wb.domain.models import BidMutation, CampaignCreate, MutationResult, PlacementConfig
from wb.services.bids import BidService
from wb.services.budgets import BudgetService
from wb.services.campaigns import CampaignService


# ── Shared fixtures ──────────────────────────────────────────────────

@pytest.fixture()
def mock_client():
    """Create a mock PromotionClient."""
    return MagicMock()


@pytest.fixture()
def campaign_svc(mock_client):
    """Create a CampaignService with mock client."""
    return CampaignService(mock_client)


@pytest.fixture()
def budget_svc(mock_client):
    """Create a BudgetService with mock client."""
    return BudgetService(mock_client)


@pytest.fixture()
def bid_svc(mock_client):
    """Create a BidService with mock client."""
    return BidService(mock_client)


# ── CampaignService write tests ──────────────────────────────────────

class TestCampaignServiceStart:
    """Tests for CampaignService.start_campaign()."""

    def test_calls_client_and_returns_result(self, campaign_svc, mock_client):
        result = campaign_svc.start_campaign(1)
        mock_client.start_campaign.assert_called_once_with(1)
        assert result.success is True
        assert result.target_id == '1'
        assert result.dry_run is False

    def test_dry_run_skips_client(self, campaign_svc, mock_client):
        result = campaign_svc.start_campaign(1, dry_run=True)
        mock_client.start_campaign.assert_not_called()
        assert result.dry_run is True
        assert result.success is True


class TestCampaignServicePause:
    """Tests for CampaignService.pause_campaign()."""

    def test_calls_client(self, campaign_svc, mock_client):
        campaign_svc.pause_campaign(2)
        mock_client.pause_campaign.assert_called_once_with(2)

    def test_dry_run_skips_client(self, campaign_svc, mock_client):
        result = campaign_svc.pause_campaign(2, dry_run=True)
        mock_client.pause_campaign.assert_not_called()
        assert result.dry_run is True


class TestCampaignServiceStop:
    """Tests for CampaignService.stop_campaign()."""

    def test_calls_client(self, campaign_svc, mock_client):
        campaign_svc.stop_campaign(3)
        mock_client.stop_campaign.assert_called_once_with(3)

    def test_dry_run_skips_client(self, campaign_svc, mock_client):
        result = campaign_svc.stop_campaign(3, dry_run=True)
        mock_client.stop_campaign.assert_not_called()
        assert result.dry_run is True


class TestCampaignServiceRename:
    """Tests for CampaignService.rename_campaign()."""

    def test_calls_client_with_name(self, campaign_svc, mock_client):
        result = campaign_svc.rename_campaign(4, 'New Name')
        mock_client.rename_campaign.assert_called_once_with(4, 'New Name')
        assert result.success is True

    def test_dry_run_skips_client(self, campaign_svc, mock_client):
        result = campaign_svc.rename_campaign(4, 'X', dry_run=True)
        mock_client.rename_campaign.assert_not_called()
        assert result.dry_run is True


class TestCampaignServiceDelete:
    """Tests for CampaignService.delete_campaign()."""

    def test_calls_client(self, campaign_svc, mock_client):
        campaign_svc.delete_campaign(5)
        mock_client.delete_campaign.assert_called_once_with(5)

    def test_dry_run_skips_client(self, campaign_svc, mock_client):
        result = campaign_svc.delete_campaign(5, dry_run=True)
        mock_client.delete_campaign.assert_not_called()
        assert result.dry_run is True


class TestCampaignServiceCreate:
    """Tests for CampaignService.create_campaign()."""

    def test_calls_client_with_payload(self, campaign_svc, mock_client):
        mock_client.create_campaign.return_value = {'advertId': 99}
        params = CampaignCreate(
            name='Test', nm_ids=[100], bid_type='manual',
        )
        result = campaign_svc.create_campaign(params)
        mock_client.create_campaign.assert_called_once()
        assert result.target_id == '99'
        assert result.success is True

    def test_dry_run_skips_client(self, campaign_svc, mock_client):
        params = CampaignCreate(name='Test')
        result = campaign_svc.create_campaign(params, dry_run=True)
        mock_client.create_campaign.assert_not_called()
        assert result.dry_run is True


class TestCampaignServiceAddItems:
    """Tests for CampaignService.add_items()."""

    def test_calls_client_with_nms(self, campaign_svc, mock_client):
        result = campaign_svc.add_items(10, [1, 2, 3])
        mock_client.add_items.assert_called_once_with(10, [1, 2, 3])
        assert '3 item(s)' in result.action

    def test_dry_run_skips_client(self, campaign_svc, mock_client):
        result = campaign_svc.add_items(10, [1], dry_run=True)
        mock_client.add_items.assert_not_called()
        assert result.dry_run is True


class TestCampaignServiceRemoveItems:
    """Tests for CampaignService.remove_items()."""

    def test_calls_client(self, campaign_svc, mock_client):
        campaign_svc.remove_items(10, [5])
        mock_client.remove_items.assert_called_once_with(10, [5])

    def test_dry_run_skips_client(self, campaign_svc, mock_client):
        result = campaign_svc.remove_items(10, [5], dry_run=True)
        mock_client.remove_items.assert_not_called()
        assert result.dry_run is True


class TestCampaignServiceSetPlacements:
    """Tests for CampaignService.set_placements()."""

    def test_calls_client_with_payload(self, campaign_svc, mock_client):
        config = PlacementConfig(search_enabled=True, recommendations_enabled=False)
        result = campaign_svc.set_placements(10, config)
        mock_client.set_placements.assert_called_once()
        assert result.success is True

    def test_dry_run_skips_client(self, campaign_svc, mock_client):
        config = PlacementConfig()
        result = campaign_svc.set_placements(10, config, dry_run=True)
        mock_client.set_placements.assert_not_called()
        assert result.dry_run is True


# ── BudgetService write tests ─────────────────────────────────────────

class TestBudgetServiceTopup:
    """Tests for BudgetService.topup()."""

    def test_calls_deposit_and_returns_result(self, budget_svc, mock_client):
        result = budget_svc.topup(20, 3000)
        mock_client.deposit_budget.assert_called_once_with(20, 3000)
        assert result.success is True
        assert result.dry_run is False

    def test_dry_run_skips_client(self, budget_svc, mock_client):
        result = budget_svc.topup(20, 3000, dry_run=True)
        mock_client.deposit_budget.assert_not_called()
        assert result.dry_run is True

    def test_raises_on_zero_amount(self, budget_svc):
        with pytest.raises(ValidationError):
            budget_svc.topup(1, 0)

    def test_raises_on_negative_amount(self, budget_svc):
        with pytest.raises(ValidationError):
            budget_svc.topup(1, -100)


# ── BidService write tests ────────────────────────────────────────────

class TestBidServiceSetItemBid:
    """Tests for BidService.set_item_bid()."""

    def test_calls_client_with_payload(self, bid_svc, mock_client):
        mutation = BidMutation(nm_id=123, bid_kopecks=500)
        result = bid_svc.set_item_bid(10, mutation)
        mock_client.set_item_bid.assert_called_once_with(
            mutation.to_api(10)
        )
        assert result.success is True

    def test_dry_run_skips_client(self, bid_svc, mock_client):
        mutation = BidMutation(nm_id=1, bid_kopecks=100)
        result = bid_svc.set_item_bid(5, mutation, dry_run=True)
        mock_client.set_item_bid.assert_not_called()
        assert result.dry_run is True

    def test_raises_on_zero_bid(self, bid_svc):
        with pytest.raises(ValidationError):
            bid_svc.set_item_bid(1, BidMutation(nm_id=1, bid_kopecks=0))

    def test_raises_on_negative_bid(self, bid_svc):
        with pytest.raises(ValidationError):
            bid_svc.set_item_bid(1, BidMutation(nm_id=1, bid_kopecks=-50))


class TestBidServiceSetItemBids:
    """Tests for BidService.set_item_bids()."""

    def test_returns_result_per_mutation(self, bid_svc, mock_client):
        mutations = [BidMutation(nm_id=1, bid_kopecks=100), BidMutation(nm_id=2, bid_kopecks=200)]
        results = bid_svc.set_item_bids(10, mutations)
        assert len(results) == 2
        mock_client.set_item_bids_batch.assert_called_once()

    def test_dry_run_calls_nothing(self, bid_svc, mock_client):
        mutations = [BidMutation(nm_id=1, bid_kopecks=100)]
        results = bid_svc.set_item_bids(5, mutations, dry_run=True)
        mock_client.set_item_bids_batch.assert_not_called()
        assert all(r.dry_run for r in results)

    def test_empty_list_returns_empty(self, bid_svc, mock_client):
        results = bid_svc.set_item_bids(5, [])
        assert results == []


# ── Domain model tests ────────────────────────────────────────────────

class TestMutationResult:
    """Tests for MutationResult model."""

    def test_defaults(self):
        r = MutationResult(success=True, action='test', target_id='1')
        assert r.dry_run is False
        assert r.message == ''

    def test_dry_run_flag(self):
        r = MutationResult(
            success=True, action='x', target_id='2', dry_run=True,
        )
        assert r.dry_run is True


class TestCampaignCreate:
    """Tests for CampaignCreate.to_api()."""

    def test_to_api_basic(self):
        params = CampaignCreate(
            name='Test', nm_ids=[10, 20],
            bid_type='manual', placement_types=['search'],
        )
        payload = params.to_api()
        assert payload['name'] == 'Test'
        assert payload['nms'] == [10, 20]
        assert payload['bid_type'] == 'manual'
        assert payload['placement_types'] == ['search']

    def test_to_api_with_unified_bid(self):
        params = CampaignCreate(
            name='T', bid_type='unified',
            placement_types=['search', 'recommendations'],
        )
        payload = params.to_api()
        assert payload['bid_type'] == 'unified'
        assert payload['placement_types'] == ['search', 'recommendations']

    def test_to_api_empty_nms(self):
        params = CampaignCreate(name='T')
        payload = params.to_api()
        assert payload['nms'] == []


class TestBidMutation:
    """Tests for BidMutation.to_api()."""

    def test_to_api_payload(self):
        m = BidMutation(nm_id=123, bid_kopecks=400, placement='search')
        payload = m.to_api(campaign_id=99)
        assert payload['advert_id'] == 99
        nm_bids = payload['nm_bids']
        assert len(nm_bids) == 1
        assert nm_bids[0]['nm_id'] == 123
        assert nm_bids[0]['bid_kopecks'] == 400
        assert nm_bids[0]['placement'] == 'search'


class TestPlacementConfig:
    """Tests for PlacementConfig.to_api()."""

    def test_to_api_payload(self):
        config = PlacementConfig(
            search_enabled=True, recommendations_enabled=False,
        )
        payload = config.to_api(campaign_id=5)
        assert payload['advert_id'] == 5
        placements = payload['placements']
        assert placements['search'] is True
        assert placements['recommendations'] is False


# ── BidService batch tests ────────────────────────────────────────────

class TestBidServiceSetItemsBatch:
    """Tests for BidService.set_item_bids() — true batch, N+1 eliminated."""

    def test_empty_mutations_returns_empty(self, bid_svc, mock_client):
        results = bid_svc.set_item_bids(10, [])
        assert results == []
        mock_client.set_item_bids_batch.assert_not_called()

    def test_single_valid_mutation_calls_batch_not_single(
            self, bid_svc, mock_client,
    ):
        m = BidMutation(nm_id=123, bid_kopecks=500)
        results = bid_svc.set_item_bids(10, [m])
        mock_client.set_item_bids_batch.assert_called_once()
        mock_client.set_item_bid.assert_not_called()
        assert len(results) == 1
        assert results[0].success is True

    def test_two_valid_mutations_one_batch_call(self, bid_svc, mock_client):
        mutations = [
            BidMutation(nm_id=1, bid_kopecks=100),
            BidMutation(nm_id=2, bid_kopecks=200),
        ]
        bid_svc.set_item_bids(10, mutations)
        assert mock_client.set_item_bids_batch.call_count == 1
        payload = mock_client.set_item_bids_batch.call_args[0][0]
        assert len(payload) == 2

    def test_invalid_bid_gets_failure_result_not_exception(
            self, bid_svc, mock_client,
    ):
        m = BidMutation(nm_id=123, bid_kopecks=0)
        results = bid_svc.set_item_bids(10, [m])
        assert results[0].success is False
        assert 'positive' in results[0].message
        mock_client.set_item_bids_batch.assert_not_called()

    def test_mixed_valid_and_invalid(self, bid_svc, mock_client):
        mutations = [
            BidMutation(nm_id=1, bid_kopecks=100),   # valid
            BidMutation(nm_id=2, bid_kopecks=-1),    # invalid
            BidMutation(nm_id=3, bid_kopecks=300),   # valid
        ]
        results = bid_svc.set_item_bids(10, mutations)
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is True
        payload = mock_client.set_item_bids_batch.call_args[0][0]
        assert len(payload) == 2   # only valid ones sent

    def test_dry_run_skips_batch_call(self, bid_svc, mock_client):
        mutations = [BidMutation(nm_id=1, bid_kopecks=100)]
        results = bid_svc.set_item_bids(10, mutations, dry_run=True)
        mock_client.set_item_bids_batch.assert_not_called()
        assert results[0].dry_run is True

    def test_over_batch_size_makes_multiple_calls(self, bid_svc, mock_client):
        mutations = [
            BidMutation(nm_id=i, bid_kopecks=100) for i in range(BID_BATCH_SIZE + 1)
        ]
        bid_svc.set_item_bids(10, mutations)
        assert mock_client.set_item_bids_batch.call_count == 2

    def test_all_invalid_no_batch_call(self, bid_svc, mock_client):
        mutations = [BidMutation(nm_id=i, bid_kopecks=0) for i in range(3)]
        results = bid_svc.set_item_bids(10, mutations)
        mock_client.set_item_bids_batch.assert_not_called()
        assert all(not r.success for r in results)


# ── CampaignService batch action tests ───────────────────────────────

class TestCampaignServiceBatch:
    """Tests for CampaignService.start/pause/stop/delete_campaigns()."""

    def test_start_campaigns_calls_start_for_each(
            self, campaign_svc, mock_client,
    ):
        mock_client.start_campaign.return_value = None
        results = campaign_svc.start_campaigns([1, 2, 3])
        assert mock_client.start_campaign.call_count == 3
        assert len(results) == 3
        assert all(r.success for r in results)

    def test_start_campaigns_empty_returns_empty(
            self, campaign_svc, mock_client,
    ):
        results = campaign_svc.start_campaigns([])
        assert results == []
        mock_client.start_campaign.assert_not_called()

    def test_start_campaigns_partial_failure(self, campaign_svc, mock_client):
        def _raise_on_second(cid):
            if cid == 2:
                raise WbCliError('API error')
        mock_client.start_campaign.side_effect = _raise_on_second
        results = campaign_svc.start_campaigns([1, 2, 3])
        assert results[0].success is True
        assert results[1].success is False
        assert 'API error' in results[1].message
        assert results[2].success is True

    def test_pause_campaigns(self, campaign_svc, mock_client):
        results = campaign_svc.pause_campaigns([10, 20])
        assert mock_client.pause_campaign.call_count == 2
        assert all(r.success for r in results)

    def test_stop_campaigns(self, campaign_svc, mock_client):
        results = campaign_svc.stop_campaigns([5])
        mock_client.stop_campaign.assert_called_once_with(5)
        assert results[0].success is True

    def test_delete_campaigns(self, campaign_svc, mock_client):
        results = campaign_svc.delete_campaigns([7, 8])
        assert mock_client.delete_campaign.call_count == 2
        assert all(r.success for r in results)

    def test_dry_run_propagates(self, campaign_svc, mock_client):
        results = campaign_svc.start_campaigns([1, 2], dry_run=True)
        mock_client.start_campaign.assert_not_called()
        assert all(r.dry_run for r in results)
