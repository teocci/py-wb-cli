"""Bid-related read use-cases."""

from __future__ import annotations

from wb.client.promotion import PromotionClient
from wb.domain.models import RecommendedBid

__all__ = ['BidService']


class BidService:
    """Orchestrates bid read operations.

    Attributes:
        client: Promotion API client.
    """

    def __init__(self, client: PromotionClient) -> None:
        self._client = client

    def get_recommended_bids(
            self, campaign_id: int,
    ) -> list[RecommendedBid]:
        """Retrieve recommended CPM bids for a campaign.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            List of RecommendedBid domain objects.
        """
        raw = self._client.get_recommended_bids(campaign_id)
        return [
            RecommendedBid.from_api(item, campaign_id=campaign_id)
            for item in raw
        ]

    def get_minimum_bids(
            self, campaign_id: int,
    ) -> list[RecommendedBid]:
        """Retrieve minimum bids for a campaign.

        Same data source as recommended; minimum is a field on RecommendedBid.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            List of RecommendedBid domain objects.
        """
        return self.get_recommended_bids(campaign_id)

    def get_item_bids(
            self, campaign_id: int,
    ) -> list[RecommendedBid]:
        """Retrieve per-item bid info for a campaign.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            List of RecommendedBid domain objects with bid details.
        """
        return self.get_recommended_bids(campaign_id)
