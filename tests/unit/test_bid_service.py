"""Tests for wb.services.bids.BidService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wb.domain.models import RecommendedBid
from wb.services.bids import BidService


RAW_BIDS: list[dict] = [
    {'nmId': 10, 'cpm': 500, 'minCpm': 100},
    {'nmId': 20, 'cpm': 800, 'minCpm': 200},
]


@pytest.fixture()
def mock_client() -> MagicMock:
    """Create a mock PromotionClient."""
    return MagicMock()


@pytest.fixture()
def service(mock_client: MagicMock) -> BidService:
    """Create a BidService with a mocked client."""
    return BidService(client=mock_client)


class TestGetRecommendedBids:
    """Tests for BidService.get_recommended_bids."""

    def test_returns_recommended_bids(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """get_recommended_bids returns list of RecommendedBid objects."""
        mock_client.get_recommended_bids.return_value = RAW_BIDS

        result = service.get_recommended_bids(campaign_id=42)

        assert len(result) == 2
        assert all(isinstance(b, RecommendedBid) for b in result)
        assert result[0].campaign_id == 42
        assert result[0].nm_id == 10
        assert result[0].recommended == 500
        assert result[0].minimum == 100
        assert result[1].nm_id == 20
        assert result[1].recommended == 800
        mock_client.get_recommended_bids.assert_called_once_with(42)

    def test_empty_response(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """get_recommended_bids returns empty list when API returns no data."""
        mock_client.get_recommended_bids.return_value = []

        result = service.get_recommended_bids(campaign_id=42)

        assert result == []


class TestGetMinimumBids:
    """Tests for BidService.get_minimum_bids."""

    def test_returns_same_data_as_recommended(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """get_minimum_bids returns same RecommendedBid data."""
        mock_client.get_recommended_bids.return_value = RAW_BIDS

        result = service.get_minimum_bids(campaign_id=42)

        assert len(result) == 2
        assert all(isinstance(b, RecommendedBid) for b in result)
        assert result[0].minimum == 100
        assert result[1].minimum == 200


class TestGetItemBids:
    """Tests for BidService.get_item_bids."""

    def test_returns_bid_data(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """get_item_bids returns list of RecommendedBid objects."""
        mock_client.get_recommended_bids.return_value = RAW_BIDS

        result = service.get_item_bids(campaign_id=42)

        assert len(result) == 2
        assert all(isinstance(b, RecommendedBid) for b in result)
        assert result[0].campaign_id == 42
        assert result[0].nm_id == 10

    def test_empty_response(
        self, service: BidService, mock_client: MagicMock,
    ) -> None:
        """get_item_bids returns empty list when no data."""
        mock_client.get_recommended_bids.return_value = []

        result = service.get_item_bids(campaign_id=42)

        assert result == []
