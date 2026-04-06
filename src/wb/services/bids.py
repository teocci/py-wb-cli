"""Bid-related read use-cases."""

from __future__ import annotations

from wb.client.promotion import PromotionClient
from wb.core.batching import chunk
from wb.core.constants import BID_BATCH_SIZE
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
        if mutation.bid_kopecks <= 0:
            raise ValidationError(
                f'Bid must be positive, got {mutation.bid_kopecks}'
            )
        action = (
            f'set bid={mutation.bid_kopecks} for nm={mutation.nm_id} '
            f'in campaign {campaign_id}'
        )
        if dry_run:
            return MutationResult(
                success=True, action=action, target_id=str(campaign_id),
                dry_run=True,
                message=f'Would set bid to {mutation.bid_kopecks}',
            )
        self._client.set_item_bid(mutation.to_api(campaign_id))
        return MutationResult(
            success=True, action=action, target_id=str(campaign_id),
            message=(
                f'Bid set to {mutation.bid_kopecks} '
                f'for nm={mutation.nm_id}'
            ),
        )

    def set_item_bids(
            self,
            campaign_id: int,
            mutations: list[BidMutation],
            dry_run: bool = False,
    ) -> list[MutationResult]:
        """Set CPM bids for multiple items using batch PATCH calls.

        Pre-validates all mutations; invalid ones get success=False in the
        result without aborting the remaining valid mutations. Valid mutations
        are sent in chunks of BID_BATCH_SIZE (one PATCH call per chunk).

        Args:
            campaign_id: Target campaign identifier.
            mutations: List of bid change specifications.
            dry_run: If True, plan without executing.

        Returns:
            List of MutationResult, one per input mutation.
        """
        if not mutations:
            return []
        results: list[MutationResult] = []
        valid: list[BidMutation] = []
        for m in mutations:
            action = (
                f'set bid={m.bid_kopecks} for nm={m.nm_id} '
                f'in campaign {campaign_id}'
            )
            if m.bid_kopecks <= 0:
                results.append(MutationResult(
                    success=False, action=action, target_id=str(campaign_id),
                    message=f'Skipped: bid must be positive, got {m.bid_kopecks}',
                ))
            else:
                results.append(MutationResult(
                    success=True, action=action, target_id=str(campaign_id),
                    dry_run=dry_run,
                ))
                valid.append(m)
        if dry_run or not valid:
            return results
        for batch in chunk(valid, BID_BATCH_SIZE):
            self._client.set_item_bids_batch(
                [m.to_api(campaign_id) for m in batch]
            )
        return results
