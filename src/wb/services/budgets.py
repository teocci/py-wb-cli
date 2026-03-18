"""Budget and balance use-cases."""

from __future__ import annotations

from wb.client.promotion import PromotionClient
from wb.domain.models import AccountBalance, BudgetSnapshot

__all__ = ['BudgetService']


class BudgetService:
    """Orchestrates budget and balance read operations.

    Attributes:
        client: Promotion API client.
    """

    def __init__(self, client: PromotionClient) -> None:
        self._client = client

    def get_balance(self) -> AccountBalance:
        """Retrieve account-level financial balance.

        Returns:
            AccountBalance domain object.
        """
        raw = self._client.get_balance()
        return AccountBalance.from_api(raw)

    def get_budget(self, campaign_id: int) -> BudgetSnapshot:
        """Retrieve budget for a specific campaign.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            BudgetSnapshot domain object.
        """
        raw = self._client.get_budget(campaign_id)
        return BudgetSnapshot.from_api(raw, campaign_id=campaign_id)
