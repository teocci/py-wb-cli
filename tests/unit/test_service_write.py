"""Tests for write methods in CampaignService, BudgetService, BidService."""

from unittest.mock import MagicMock

import pytest

from wb.core.exceptions import ValidationError
from wb.domain.enums import CampaignType
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
            name='Test', campaign_type=CampaignType.AUTO,
            daily_budget=5000, nm_ids=[100],
        )
        result = campaign_svc.create_campaign(params)
        mock_client.create_campaign.assert_called_once()
        assert result.target_id == '99'
        assert result.success is True

    def test_dry_run_skips_client(self, campaign_svc, mock_client):
        params = CampaignCreate(
            name='Test', campaign_type=CampaignType.AUTO, daily_budget=5000,
        )
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
        config = PlacementConfig(search_enabled=True, catalog_enabled=False)
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
        mutation = BidMutation(nm_id=123, cpm=500, subject_id=0)
        result = bid_svc.set_item_bid(10, mutation)
        mock_client.set_item_bid.assert_called_once_with(
            mutation.to_api(10)
        )
        assert result.success is True

    def test_dry_run_skips_client(self, bid_svc, mock_client):
        mutation = BidMutation(nm_id=1, cpm=100)
        result = bid_svc.set_item_bid(5, mutation, dry_run=True)
        mock_client.set_item_bid.assert_not_called()
        assert result.dry_run is True

    def test_raises_on_zero_cpm(self, bid_svc):
        with pytest.raises(ValidationError):
            bid_svc.set_item_bid(1, BidMutation(nm_id=1, cpm=0))

    def test_raises_on_negative_cpm(self, bid_svc):
        with pytest.raises(ValidationError):
            bid_svc.set_item_bid(1, BidMutation(nm_id=1, cpm=-50))


class TestBidServiceSetItemBids:
    """Tests for BidService.set_item_bids()."""

    def test_returns_result_per_mutation(self, bid_svc, mock_client):
        mutations = [BidMutation(nm_id=1, cpm=100), BidMutation(nm_id=2, cpm=200)]
        results = bid_svc.set_item_bids(10, mutations)
        assert len(results) == 2
        assert mock_client.set_item_bid.call_count == 2

    def test_dry_run_calls_nothing(self, bid_svc, mock_client):
        mutations = [BidMutation(nm_id=1, cpm=100)]
        results = bid_svc.set_item_bids(5, mutations, dry_run=True)
        mock_client.set_item_bid.assert_not_called()
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
            name='Test', campaign_type=CampaignType.AUTO,
            daily_budget=5000, nm_ids=[10, 20],
        )
        payload = params.to_api()
        assert payload['name'] == 'Test'
        assert payload['type'] == CampaignType.AUTO.value
        assert payload['dailyBudget'] == 5000
        assert payload['nms'] == [10, 20]

    def test_to_api_with_subject(self):
        params = CampaignCreate(
            name='T', campaign_type=CampaignType.AUTO,
            daily_budget=1000, subject_id=42,
        )
        payload = params.to_api()
        assert payload['subjectId'] == 42

    def test_to_api_no_nms_excludes_key(self):
        params = CampaignCreate(
            name='T', campaign_type=CampaignType.AUTO, daily_budget=1000,
        )
        payload = params.to_api()
        assert 'nms' not in payload


class TestBidMutation:
    """Tests for BidMutation.to_api()."""

    def test_to_api_payload(self):
        m = BidMutation(nm_id=123, cpm=400, subject_id=0)
        payload = m.to_api(campaign_id=99)
        assert payload['advertId'] == 99
        assert payload['cpm'] == 400
        assert payload['type'] == 8
        assert payload['param'] == 0


class TestPlacementConfig:
    """Tests for PlacementConfig.to_api()."""

    def test_to_api_payload(self):
        config = PlacementConfig(search_enabled=True, catalog_enabled=False)
        payload = config.to_api(campaign_id=5)
        assert payload['advertId'] == 5
        params = payload['params']
        assert len(params) == 2
        search_place = next(p for p in params if p['place'] == 1)
        catalog_place = next(p for p in params if p['place'] == 2)
        assert search_place['active'] is True
        assert catalog_place['active'] is False
