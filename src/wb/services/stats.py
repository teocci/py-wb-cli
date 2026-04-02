"""Statistics use-cases for campaigns and clusters."""

from __future__ import annotations

import re

from wb.client.promotion import PromotionClient
from wb.core.exceptions import ValidationError
from wb.domain.models import CampaignStats

__all__ = ['StatsService']

_DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _validate_date(value: str, label: str) -> None:
    """Validate a date string is YYYY-MM-DD format.

    Args:
        value: Date string to validate.
        label: Label for error messages.

    Raises:
        ValidationError: If format is invalid.
    """
    if not _DATE_PATTERN.match(value):
        raise ValidationError(
            f'{label} must be YYYY-MM-DD format, got {value!r}'
        )


class StatsService:
    """Orchestrates statistics read operations.

    Attributes:
        client: Promotion API client.
    """

    def __init__(self, client: PromotionClient) -> None:
        self._client = client

    def get_campaign_stats(
            self,
            campaign_id: int,
            date_from: str,
            date_to: str,
    ) -> CampaignStats:
        """Retrieve aggregated stats for a single campaign.

        Args:
            campaign_id: Target campaign identifier.
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).

        Returns:
            CampaignStats domain object.

        Raises:
            ValidationError: If date format is invalid or no data returned.
        """
        _validate_date(date_from, '--from')
        _validate_date(date_to, '--to')
        raw = self._client.get_campaign_stats(
            [campaign_id], date_from, date_to,
        )
        if not raw:
            return CampaignStats(campaign_id=campaign_id)
        return CampaignStats.from_api(raw[0])

    def get_campaigns_stats(
            self,
            campaign_ids: list[int],
            date_from: str,
            date_to: str,
    ) -> list[CampaignStats]:
        """Retrieve aggregated stats for multiple campaigns.

        Args:
            campaign_ids: List of campaign identifiers.
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).

        Returns:
            List of CampaignStats domain objects.

        Raises:
            ValidationError: If date format is invalid.
        """
        _validate_date(date_from, '--from')
        _validate_date(date_to, '--to')
        raw = self._client.get_campaign_stats(
            campaign_ids, date_from, date_to,
        )
        return [CampaignStats.from_api(item) for item in raw]

