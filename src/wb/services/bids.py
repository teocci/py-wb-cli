"""Bid-related read use-cases."""

from __future__ import annotations

from wb.client.promotion import PromotionClient
from wb.core.exceptions import ValidationError
from wb.domain.models import BidMutation, MutationResult, RecommendedBid

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

    def set_item_bid(
            self,
            campaign_id: int,
            mutation: BidMutation,
            dry_run: bool = False,
    ) -> MutationResult:
        """Set a CPM bid for a single item in a campaign.

        Args:
            campaign_id: Target campaign identifier.
            mutation: Bid change specification.
            dry_run: If True, plan without executing.

        Returns:
            MutationResult describing the outcome.

        Raises:
            ValidationError: If CPM is not positive.
        """
        if mutation.cpm <= 0:
            raise ValidationError(f'CPM must be positive, got {mutation.cpm}')
        action = (
            f'set cpm={mutation.cpm} for nm={mutation.nm_id} '
            f'in campaign {campaign_id}'
        )
        if dry_run:
            return MutationResult(
                success=True, action=action, target_id=str(campaign_id),
                dry_run=True, message=f'Would set CPM to {mutation.cpm}',
            )
        self._client.set_item_bid(mutation.to_api(campaign_id))
        return MutationResult(
            success=True, action=action, target_id=str(campaign_id),
            message=f'CPM set to {mutation.cpm} for nm={mutation.nm_id}',
        )

    def set_item_bids(
            self,
            campaign_id: int,
            mutations: list[BidMutation],
            dry_run: bool = False,
    ) -> list[MutationResult]:
        """Set CPM bids for multiple items in a campaign.

        Args:
            campaign_id: Target campaign identifier.
            mutations: List of bid change specifications.
            dry_run: If True, plan without executing.

        Returns:
            List of MutationResult objects, one per bid.
        """
        return [
            self.set_item_bid(campaign_id, m, dry_run=dry_run)
            for m in mutations
        ]
