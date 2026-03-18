"""Campaign-related use-cases."""

from __future__ import annotations

from wb.client.promotion import PromotionClient
from wb.core.exceptions import ValidationError
from wb.domain.enums import CampaignStatus, CampaignType
from wb.domain.models import Campaign, ProductCard

__all__ = ['CampaignService']


class CampaignService:
    """Orchestrates campaign read operations.

    Attributes:
        client: Promotion API client.
    """

    def __init__(self, client: PromotionClient) -> None:
        self._client = client

    def list_campaigns(
            self,
            status: CampaignStatus | None = None,
            type_: CampaignType | None = None,
    ) -> list[Campaign]:
        """List campaigns with optional filtering.

        Args:
            status: Filter by campaign status.
            type_: Filter by campaign type.

        Returns:
            List of Campaign domain objects.
        """
        status_filter = [status.value] if status else None
        type_filter = [type_.value] if type_ else None
        raw = self._client.list_campaigns(
            status=status_filter, type_=type_filter,
        )
        return [Campaign.from_api(c) for c in raw]

    def get_campaign(self, campaign_id: int) -> Campaign:
        """Retrieve a single campaign by ID.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            Campaign domain object.

        Raises:
            ValidationError: If campaign not found.
        """
        raw = self._client.get_campaign(campaign_id)
        if raw is None:
            raise ValidationError(f'Campaign {campaign_id} not found')
        return Campaign.from_api(raw)

    def get_eligible_subjects(self) -> list[dict]:
        """Retrieve subjects eligible for campaign creation.

        Returns:
            List of subject dicts (id, name).
        """
        return self._client.get_eligible_subjects()

    def get_eligible_items(self, subject_id: int) -> list[ProductCard]:
        """Retrieve product cards eligible for a given subject.

        Args:
            subject_id: Subject category ID.

        Returns:
            List of ProductCard domain objects.
        """
        raw = self._client.get_eligible_items(subject_id)
        return [ProductCard.from_api(item) for item in raw]
