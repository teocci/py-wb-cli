"""Tests for PromotionClient write methods."""

from unittest.mock import MagicMock

import pytest

from wb.client.promotion import PromotionClient
from wb.core.constants import (
    EP_BID_SET,
    EP_BUDGET_DEPOSIT,
    EP_CAMPAIGN_CREATE,
    EP_CAMPAIGN_ITEMS,
    EP_CAMPAIGN_LIST,
    EP_CAMPAIGN_PAUSE,
    EP_CAMPAIGN_PLACEMENTS,
    EP_CAMPAIGN_RENAME,
    EP_CAMPAIGN_START,
    EP_CAMPAIGN_STOP,
)


@pytest.fixture()
def mock_http():
    """Create a mock WbHttpClient."""
    return MagicMock()


@pytest.fixture()
def client(mock_http):
    """Create a PromotionClient with mock HTTP."""
    return PromotionClient(mock_http)


class TestStartCampaign:
    """Tests for start_campaign()."""

    def test_calls_get_with_id(self, client, mock_http):
        client.start_campaign(12345)
        mock_http.get.assert_called_once_with(EP_CAMPAIGN_START, params={'id': 12345})

    def test_returns_none(self, client, mock_http):
        mock_http.get.return_value = None
        result = client.start_campaign(1)
        assert result is None


class TestPauseCampaign:
    """Tests for pause_campaign()."""

    def test_calls_get_with_id(self, client, mock_http):
        client.pause_campaign(99)
        mock_http.get.assert_called_once_with(EP_CAMPAIGN_PAUSE, params={'id': 99})


class TestStopCampaign:
    """Tests for stop_campaign()."""

    def test_calls_get_with_id(self, client, mock_http):
        client.stop_campaign(77)
        mock_http.get.assert_called_once_with(EP_CAMPAIGN_STOP, params={'id': 77})


class TestRenameCampaign:
    """Tests for rename_campaign()."""

    def test_posts_correct_payload(self, client, mock_http):
        client.rename_campaign(42, 'New Name')
        mock_http.post.assert_called_once_with(
            EP_CAMPAIGN_RENAME,
            json_body={'advertId': 42, 'name': 'New Name'},
        )


class TestDeleteCampaign:
    """Tests for delete_campaign()."""

    def test_deletes_with_ids_param(self, client, mock_http):
        client.delete_campaign(55)
        mock_http.delete.assert_called_once_with(
            EP_CAMPAIGN_LIST, params={'ids': [55]}
        )


class TestCreateCampaign:
    """Tests for create_campaign()."""

    def test_posts_payload_and_returns_dict(self, client, mock_http):
        mock_http.post.return_value = {'advertId': 999}
        result = client.create_campaign({'name': 'Test', 'type': 8})
        assert result == {'advertId': 999}
        mock_http.post.assert_called_once_with(
            EP_CAMPAIGN_CREATE, json_body={'name': 'Test', 'type': 8}
        )

    def test_returns_empty_dict_on_none(self, client, mock_http):
        mock_http.post.return_value = None
        result = client.create_campaign({})
        assert result == {}


class TestAddItems:
    """Tests for add_items()."""

    def test_posts_correct_payload(self, client, mock_http):
        client.add_items(10, [100, 200])
        mock_http.post.assert_called_once_with(
            EP_CAMPAIGN_ITEMS,
            json_body={'advertId': 10, 'nms': [100, 200]},
        )


class TestRemoveItems:
    """Tests for remove_items()."""

    def test_deletes_with_correct_body(self, client, mock_http):
        client.remove_items(10, [300])
        mock_http.delete.assert_called_once_with(
            EP_CAMPAIGN_ITEMS,
            json_body={'advertId': 10, 'nms': [300]},
        )


class TestSetPlacements:
    """Tests for set_placements()."""

    def test_posts_payload(self, client, mock_http):
        payload = {'advertId': 1, 'params': []}
        client.set_placements(1, payload)
        mock_http.post.assert_called_once_with(
            EP_CAMPAIGN_PLACEMENTS, json_body=payload
        )


class TestDepositBudget:
    """Tests for deposit_budget()."""

    def test_posts_deposit_payload(self, client, mock_http):
        client.deposit_budget(20, 5000)
        mock_http.post.assert_called_once_with(
            EP_BUDGET_DEPOSIT,
            json_body={'sum': 5000, 'advertId': 20, 'type': 1},
        )


class TestSetItemBid:
    """Tests for set_item_bid()."""

    def test_posts_bid_payload(self, client, mock_http):
        payload = {'advertId': 5, 'type': 8, 'cpm': 300, 'param': 0}
        client.set_item_bid(payload)
        mock_http.post.assert_called_once_with(EP_BID_SET, json_body=payload)
