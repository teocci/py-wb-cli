"""Tests for PromotionClient."""

from unittest.mock import MagicMock

import pytest

from wb.client.promotion import PromotionClient
from wb.core.constants import (
    EP_ACCOUNT_BALANCE,
    EP_CAMPAIGN_BUDGET,
    EP_CAMPAIGN_FULLSTATS,
    EP_CAMPAIGN_INFO,
    EP_ELIGIBLE_ITEMS,
    EP_ELIGIBLE_SUBJECTS,
    EP_NQ_GET_BIDS,
    EP_NQ_GET_MINUS,
    EP_NQ_LIST,
    EP_NQ_STATS,
    EP_NQ_STATS_DAILY,
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
        mock_http.get.return_value = {
            'adverts': [{'id': 1}, {'id': 2}],
        }
        result = client.list_campaigns()
        assert len(result) == 2

    def test_with_status_filter(self, client, mock_http):
        mock_http.get.return_value = {'adverts': []}
        client.list_campaigns(status=[9, 11])
        mock_http.get.assert_called_once_with(
            EP_CAMPAIGN_INFO, params={'statuses': '9,11'},
        )

    def test_with_ids(self, client, mock_http):
        mock_http.get.return_value = {'adverts': [{'id': 42}]}
        result = client.list_campaigns(ids=[42])
        assert len(result) == 1
        mock_http.get.assert_called_once_with(
            EP_CAMPAIGN_INFO, params={'ids': '42'},
        )

    def test_returns_empty_on_none_response(self, client, mock_http):
        mock_http.get.return_value = None
        result = client.list_campaigns()
        assert result == []


class TestGetCampaign:
    """Tests for get_campaign()."""

    def test_found(self, client, mock_http):
        mock_http.get.return_value = {
            'adverts': [
                {'id': 10, 'settings': {'name': 'Test'}},
                {'id': 20, 'settings': {'name': 'Other'}},
            ],
        }
        result = client.get_campaign(10)
        assert result == {'id': 10, 'settings': {'name': 'Test'}}

    def test_not_found(self, client, mock_http):
        mock_http.get.return_value = {'adverts': [{'id': 99}]}
        result = client.get_campaign(1)
        assert result is None

    def test_empty_list(self, client, mock_http):
        mock_http.get.return_value = {'adverts': []}
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
        mock_http.post.return_value = [{'nm': 555, 'title': 'Test', 'subjectId': 42}]
        result = client.get_eligible_items([42])
        assert len(result) == 1
        mock_http.post.assert_called_once_with(
            EP_ELIGIBLE_ITEMS, json_body=[42],
        )

    def test_subjects_none_response(self, client, mock_http):
        mock_http.get.return_value = None
        assert client.get_eligible_subjects() == []

    def test_items_none_response(self, client, mock_http):
        mock_http.post.return_value = None
        assert client.get_eligible_items([1]) == []


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
    """Tests for campaign statistics (GET /adv/v3/fullstats)."""

    def test_get_campaign_stats(self, client, mock_http):
        mock_http.get.return_value = [{'advertId': 1, 'views': 100}]
        result = client.get_campaign_stats([1], '2026-03-01', '2026-03-07')
        assert len(result) == 1
        mock_http.get.assert_called_once_with(
            EP_CAMPAIGN_FULLSTATS,
            params={
                'ids': '1',
                'beginDate': '2026-03-01',
                'endDate': '2026-03-07',
            },
        )

    def test_multiple_campaigns(self, client, mock_http):
        mock_http.get.return_value = [{'advertId': 1}, {'advertId': 2}]
        result = client.get_campaign_stats(
            [1, 2], '2026-03-01', '2026-03-07',
        )
        assert len(result) == 2

    def test_none_response(self, client, mock_http):
        mock_http.get.return_value = None
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
    """Tests for normquery cluster endpoints."""

    def test_get_cluster_list(self, client, mock_http):
        mock_http.post.return_value = {'items': [{'advertId': 10}]}
        items = [{'advertId': 10, 'nmId': 20}]
        result = client.get_cluster_list(items)
        assert result == {'items': [{'advertId': 10}]}
        mock_http.post.assert_called_once_with(
            EP_NQ_LIST, json_body={'items': items},
        )

    def test_get_cluster_bids(self, client, mock_http):
        mock_http.post.return_value = {'bids': []}
        items = [{'advert_id': 10, 'nm_id': 20}]
        result = client.get_cluster_bids(items)
        assert result == {'bids': []}
        mock_http.post.assert_called_once_with(
            EP_NQ_GET_BIDS, json_body={'items': items},
        )

    def test_get_cluster_stats(self, client, mock_http):
        mock_http.post.return_value = {'stats': []}
        items = [{'advert_id': 10, 'nm_id': 20}]
        result = client.get_cluster_stats('2025-12-01', '2025-12-31', items)
        assert result == {'stats': []}
        mock_http.post.assert_called_once_with(
            EP_NQ_STATS,
            json_body={
                'from': '2025-12-01',
                'to': '2025-12-31',
                'items': items,
            },
        )

    def test_get_cluster_stats_daily(self, client, mock_http):
        mock_http.post.return_value = {'items': []}
        items = [{'advertId': 10, 'nmId': 20}]
        result = client.get_cluster_stats_daily(
            '2025-12-01', '2025-12-31', items,
        )
        assert result == {'items': []}
        mock_http.post.assert_called_once_with(
            EP_NQ_STATS_DAILY,
            json_body={
                'from': '2025-12-01',
                'to': '2025-12-31',
                'items': items,
            },
        )

    def test_get_minus_phrases(self, client, mock_http):
        mock_http.post.return_value = {'items': []}
        items = [{'advert_id': 10, 'nm_id': 20}]
        result = client.get_minus_phrases(items)
        assert result == {'items': []}
        mock_http.post.assert_called_once_with(
            EP_NQ_GET_MINUS, json_body={'items': items},
        )

    def test_cluster_list_none_response(self, client, mock_http):
        mock_http.post.return_value = None
        assert client.get_cluster_list([]) == {}

    def test_cluster_bids_none_response(self, client, mock_http):
        mock_http.post.return_value = None
        assert client.get_cluster_bids([]) == {}
