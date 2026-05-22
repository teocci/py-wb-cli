"""Bid-related read and write use-cases.

Three read flows map to three real WB endpoints:

- ``get_recommended_bids`` → ``GET /api/advert/v0/bids/recommendations``
  (per-item; CPM-only; one call per NM).
- ``get_minimum_bids`` → ``POST /api/advert/v1/bids/min`` (batched up to
  100 NMs per call).
- ``get_item_bids`` → reads ``nm_settings[].bids_kopecks`` from the
  ``/api/advert/v2/adverts`` response — zero extra API calls.
"""

from __future__ import annotations

import logging

from wb.client.promotion import PromotionClient
from wb.core.batching import chunk
from wb.core.constants import BID_BATCH_SIZE
from wb.core.exceptions import ApiError, ValidationError
from wb.domain.enums import CampaignStatus, PaymentType
from wb.domain.models import (
    BidMutation,
    CurrentBid,
    MinimumBid,
    MutationResult,
    RecommendedBid,
)

__all__ = ['BidService']

logger = logging.getLogger(__name__)

# WB /v1/bids/min accepts up to 100 NM IDs per call (swagger maxLength).
_MIN_BIDS_BATCH_SIZE = 100

# Terminal statuses that can never yield bid data — fail fast rather than
# hammer the per-item endpoint.
_TERMINAL_STATUSES = (
    CampaignStatus.DELETED,
    CampaignStatus.ARCHIVED,
    CampaignStatus.DECLINED,
)

# Placements requested when fetching minimum bids. We ask for all three so
# the response covers every placement type the campaign might run.
_DEFAULT_MIN_PLACEMENTS = ['combined', 'search', 'recommendation']


class BidService:
    """Orchestrates bid read and write operations.

    Attributes:
        client: Promotion API client.
    """

    def __init__(self, client: PromotionClient) -> None:
        self._client = client

    def get_recommended_bids(
            self,
            campaign_id: int,
            nm_id: int | None = None,
    ) -> list[RecommendedBid]:
        """Retrieve recommended CPM bids for one or all items in a campaign.

        Pre-validates the campaign: must exist, not be in a terminal state,
        and use CPM billing (the WB endpoint is CPM-only per the swagger).
        When ``nm_id`` is given, returns a single-element list (or empty
        when WB rejects the NM). When omitted, loops over the campaign's
        nm_ids — per-NM 400s become entries with the ``error`` field set,
        so partial results survive deleted or unsupported items.

        Args:
            campaign_id: Target campaign identifier.
            nm_id: Optional product NM to scope to a single recommendation.

        Returns:
            One ``RecommendedBid`` per queried NM.

        Raises:
            ValidationError: Campaign missing, terminal-state, or non-CPM.
        """
        campaign = self._fetch_campaign_or_raise(campaign_id)
        self._validate_for_recommend(campaign, campaign_id)
        targets = self._select_recommend_targets(campaign, campaign_id, nm_id)
        return [self._fetch_one_recommendation(campaign_id, n) for n in targets]

    def get_minimum_bids(
            self,
            campaign_id: int,
    ) -> list[MinimumBid]:
        """Retrieve minimum allowed bids for every item in a campaign.

        Reads the campaign's nm_ids and payment_type, then calls
        ``POST /api/advert/v1/bids/min`` in batches of 100 NMs.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            One ``MinimumBid`` per nm_id returned by WB. Empty when the
            campaign has no items.

        Raises:
            ValidationError: Campaign missing or in a terminal state.
        """
        campaign = self._fetch_campaign_or_raise(campaign_id)
        self._reject_terminal_status(campaign, campaign_id)
        nm_ids = _extract_nm_ids(campaign)
        if not nm_ids:
            return []
        payment_type = _extract_payment_type(campaign)
        results: list[MinimumBid] = []
        for batch in chunk(nm_ids, _MIN_BIDS_BATCH_SIZE):
            raw = self._client.get_minimum_bids(
                campaign_id, batch, payment_type, _DEFAULT_MIN_PLACEMENTS,
            )
            results.extend(MinimumBid.from_api(item, campaign_id) for item in raw)
        return results

    def get_item_bids(
            self,
            campaign_id: int,
    ) -> list[CurrentBid]:
        """Retrieve current per-item bids from campaign info.

        Reads ``nm_settings[].bids_kopecks`` directly from the
        ``/api/advert/v2/adverts`` response — no separate bid endpoint
        is needed.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            One ``CurrentBid`` per item in the campaign.

        Raises:
            ValidationError: Campaign not found.
        """
        campaign = self._fetch_campaign_or_raise(campaign_id)
        nm_settings = campaign.get('nm_settings') or []
        return [
            CurrentBid.from_nm_setting(nm, campaign_id)
            for nm in nm_settings
            if isinstance(nm, dict)
        ]

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

    # ── Private helpers ────────────────────────────────────────────────

    def _fetch_campaign_or_raise(self, campaign_id: int) -> dict:
        """Return the raw campaign dict or raise ValidationError."""
        campaign = self._client.get_campaign(campaign_id)
        if not isinstance(campaign, dict):
            raise ValidationError(f'Campaign {campaign_id} not found')
        return campaign

    def _validate_for_recommend(self, campaign: dict, campaign_id: int) -> None:
        """Pre-validate a campaign for /v0/bids/recommendations.

        WB requires CPM billing for this endpoint, and terminal statuses
        will never produce useful recommendations.
        """
        self._reject_terminal_status(campaign, campaign_id)
        payment_type = _extract_payment_type(campaign)
        if payment_type != PaymentType.CPM.value:
            raise ValidationError(
                f'`bid recommend` works only for CPM campaigns '
                f'(campaign {campaign_id} uses {payment_type})'
            )

    @staticmethod
    def _reject_terminal_status(campaign: dict, campaign_id: int) -> None:
        """Raise when the campaign is in a deleted/archived/declined state."""
        raw_status = campaign.get('status')
        try:
            status = CampaignStatus(raw_status)
        except ValueError:
            return
        if status in _TERMINAL_STATUSES:
            raise ValidationError(
                f'Campaign {campaign_id} is in terminal state '
                f'{status.name.lower()}; bid endpoints are unavailable'
            )

    @staticmethod
    def _select_recommend_targets(
            campaign: dict,
            campaign_id: int,
            nm_id: int | None,
    ) -> list[int]:
        """Return the list of NMs to query for recommendations.

        When ``nm_id`` is provided, that NM is used as-is (no membership
        check — the caller may intentionally probe an NM not yet in the
        campaign). When absent, returns every nm_id in ``nm_settings``.
        """
        if nm_id is not None:
            return [nm_id]
        nm_ids = _extract_nm_ids(campaign)
        if not nm_ids:
            raise ValidationError(
                f'Campaign {campaign_id} has no items; nothing to query'
            )
        return nm_ids

    def _fetch_one_recommendation(
            self, campaign_id: int, nm_id: int,
    ) -> RecommendedBid:
        """Wrap a single get_recommended_bid call into a RecommendedBid.

        Soft-fails on WB 400 (logged + ``error`` field set) so the caller
        loop reports a partial result instead of aborting.
        """
        try:
            raw = self._client.get_recommended_bid(campaign_id, nm_id)
        except ApiError as exc:
            logger.warning(
                'bid recommend failed for campaign=%s nm=%s: %s',
                campaign_id, nm_id, exc,
            )
            return RecommendedBid(
                campaign_id=campaign_id, nm_id=nm_id,
                error=f'HTTP {exc.status_code}',
            )
        if raw is None:
            return RecommendedBid(
                campaign_id=campaign_id, nm_id=nm_id,
                error='HTTP 400 — WB rejected this NM',
            )
        return RecommendedBid.from_api(raw, campaign_id=campaign_id)


def _extract_nm_ids(campaign: dict) -> list[int]:
    """Pull nm_ids from a raw /api/advert/v2/adverts entry."""
    nm_settings = campaign.get('nm_settings') or []
    return [
        nm['nm_id'] for nm in nm_settings
        if isinstance(nm, dict) and 'nm_id' in nm
    ]


def _extract_payment_type(campaign: dict) -> str:
    """Return lowercase payment_type string from a raw campaign dict."""
    settings = campaign.get('settings') or {}
    payment_type = settings.get('payment_type') or 'cpm'
    return str(payment_type).lower()
