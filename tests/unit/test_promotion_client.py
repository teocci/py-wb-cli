"""Tests for PromotionClient."""

from unittest.mock import MagicMock

import pytest

from wb.client.promotion import PromotionClient
from wb.core.constants import (
    EP_ACCOUNT_BALANCE,
    EP_CAMPAIGN_BUDGET,
    EP_CAMPAIGN_FULLSTATS,
    EP_CAMPAIGN_LIST,
    EP_CLUSTER_ACTIVE,
    EP_CLUSTER_ALL,
    EP_CLUSTER_STATS,
    EP_ELIGIBLE_ITEMS,
    EP_ELIGIBLE_SUBJECTS,
    EP_RECOMMENDED_BID,
)


@pytest.fixture()
def mock_http():
    """Create a mock WbHttpClient."""
    return MagicMock()


@pytest.fixture()
def client(mock_http):
    """Create a PromotionClient with mock HTTP."""
    return PromotionClient(mock_http)


class TestListCampaigns:
    """Tests for list_campaigns()."""

    def test_returns_list(self, client, mock_http):
        mock_http.get.return_value = [{'advertId': 1}, {'advertId': 2}]
        result = client.list_campaigns()
        assert len(result) == 2
        mock_http.get.assert_called_once_with(EP_CAMPAIGN_LIST, params={})

    def test_with_status_filter(self, client, mock_http):
        mock_http.get.return_value = []
        client.list_campaigns(status=[9])
        mock_http.get.assert_called_once_with(
            EP_CAMPAIGN_LIST, params={'status': [9]},
        )

    def test_with_type_filter(self, client, mock_http):
        mock_http.get.return_value = []
        client.list_campaigns(type_=[8])
        mock_http.get.assert_called_once_with(
            EP_CAMPAIGN_LIST, params={'type': [8]},
        )

    def test_returns_empty_on_none_response(self, client, mock_http):
        mock_http.get.return_value = None
        result = client.list_campaigns()
        assert result == []


class TestGetCampaign:
    """Tests for get_campaign()."""

    def test_found(self, client, mock_http):
        mock_http.get.return_value = [
            {'advertId': 10, 'name': 'Test'},
            {'advertId': 20, 'name': 'Other'},
        ]
        result = client.get_campaign(10)
        assert result == {'advertId': 10, 'name': 'Test'}

    def test_not_found(self, client, mock_http):
        mock_http.get.return_value = [{'advertId': 99}]
        result = client.get_campaign(1)
        assert result is None

    def test_empty_list(self, client, mock_http):
        mock_http.get.return_value = []
        result = client.get_campaign(1)
        assert result is None


class TestEligible:
    """Tests for eligible subjects and items."""

    def test_get_eligible_subjects(self, client, mock_http):
        mock_http.get.return_value = [{'id': 1, 'name': 'Perfume'}]
        result = client.get_eligible_subjects()
        assert len(result) == 1
        mock_http.get.assert_called_once_with(EP_ELIGIBLE_SUBJECTS)

    def test_get_eligible_items(self, client, mock_http):
        mock_http.get.return_value = [{'nmId': 555}]
        result = client.get_eligible_items(42)
        assert len(result) == 1
        mock_http.get.assert_called_once_with(
            EP_ELIGIBLE_ITEMS, params={'id': 42},
        )

    def test_subjects_none_response(self, client, mock_http):
        mock_http.get.return_value = None
        assert client.get_eligible_subjects() == []

    def test_items_none_response(self, client, mock_http):
        mock_http.get.return_value = None
        assert client.get_eligible_items(1) == []


class TestBalance:
    """Tests for balance and budget."""

    def test_get_balance(self, client, mock_http):
        mock_http.get.return_value = {'balance': 100}
        result = client.get_balance()
        assert result == {'balance': 100}
        mock_http.get.assert_called_once_with(EP_ACCOUNT_BALANCE)

    def test_get_balance_none(self, client, mock_http):
        mock_http.get.return_value = None
        assert client.get_balance() == {}

    def test_get_budget(self, client, mock_http):
        mock_http.get.return_value = {'total': 5000}
        result = client.get_budget(123)
        assert result == {'total': 5000}
        mock_http.get.assert_called_once_with(
            EP_CAMPAIGN_BUDGET, params={'id': 123},
        )

    def test_get_budget_none(self, client, mock_http):
        mock_http.get.return_value = None
        assert client.get_budget(1) == {}


class TestCampaignStats:
    """Tests for campaign statistics."""

    def test_get_campaign_stats(self, client, mock_http):
        mock_http.post.return_value = [{'advertId': 1, 'views': 100}]
        result = client.get_campaign_stats([1], '2026-03-01', '2026-03-07')
        assert len(result) == 1
        mock_http.post.assert_called_once_with(
            EP_CAMPAIGN_FULLSTATS,
            json_body=[{'id': 1, 'dates': ['2026-03-01', '2026-03-07']}],
        )

    def test_multiple_campaigns(self, client, mock_http):
        mock_http.post.return_value = [{'advertId': 1}, {'advertId': 2}]
        result = client.get_campaign_stats(
            [1, 2], '2026-03-01', '2026-03-07',
        )
        assert len(result) == 2

    def test_none_response(self, client, mock_http):
        mock_http.post.return_value = None
        assert client.get_campaign_stats([1], '2026-03-01', '2026-03-07') == []


class TestRecommendedBids:
    """Tests for recommended bids."""

    def test_get_recommended_bids(self, client, mock_http):
        mock_http.get.return_value = [{'nmId': 1, 'cpm': 200}]
        result = client.get_recommended_bids(42)
        assert len(result) == 1
        mock_http.get.assert_called_once_with(
            EP_RECOMMENDED_BID, params={'id': 42},
        )

    def test_none_response(self, client, mock_http):
        mock_http.get.return_value = None
        assert client.get_recommended_bids(1) == []


class TestClusters:
    """Tests for cluster endpoints."""

    def test_get_active_clusters(self, client, mock_http):
        mock_http.get.return_value = {'words': [{'id': 1}]}
        result = client.get_active_clusters(10)
        assert result == {'words': [{'id': 1}]}
        mock_http.get.assert_called_once_with(
            EP_CLUSTER_ACTIVE, params={'id': 10},
        )

    def test_get_all_clusters(self, client, mock_http):
        mock_http.get.return_value = {'words': []}
        result = client.get_all_clusters(10)
        assert result == {'words': []}
        mock_http.get.assert_called_once_with(
            EP_CLUSTER_ALL, params={'id': 10},
        )

    def test_get_cluster_stats(self, client, mock_http):
        mock_http.get.return_value = {'words': [{'id': 5}]}
        result = client.get_cluster_stats(10)
        assert result == {'words': [{'id': 5}]}
        mock_http.get.assert_called_once_with(
            EP_CLUSTER_STATS, params={'id': 10},
        )

    def test_active_none_response(self, client, mock_http):
        mock_http.get.return_value = None
        assert client.get_active_clusters(1) == {}

    def test_all_none_response(self, client, mock_http):
        mock_http.get.return_value = None
        assert client.get_all_clusters(1) == {}
