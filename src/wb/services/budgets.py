"""Budget and balance use-cases."""

from __future__ import annotations

from wb.client.promotion import PromotionClient
from wb.core.exceptions import ValidationError
from wb.domain.models import AccountBalance, BudgetSnapshot, MutationResult

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

    def topup(
            self,
            campaign_id: int,
            amount: int,
            dry_run: bool = False,
    ) -> MutationResult:
        """Deposit funds into a campaign budget.

        Args:
            campaign_id: Target campaign identifier.
            amount: Amount to deposit in kopecks (must be positive).
            dry_run: If True, plan without executing.

        Returns:
            MutationResult describing the outcome.

        Raises:
            ValidationError: If amount is not positive.
        """
        if amount <= 0:
            raise ValidationError(f'Deposit amount must be positive, got {amount}')
        action = f'deposit {amount} kopecks to campaign {campaign_id}'
        if dry_run:
            return MutationResult(
                success=True, action=action, target_id=str(campaign_id),
                dry_run=True, message=f'Would deposit {amount} kopecks',
            )
        self._client.deposit_budget(campaign_id, amount)
        return MutationResult(
            success=True, action=action, target_id=str(campaign_id),
            message=f'Deposited {amount} kopecks',
        )
