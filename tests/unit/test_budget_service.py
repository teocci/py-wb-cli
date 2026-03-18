"""Tests for wb.services.budgets.BudgetService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wb.domain.models import AccountBalance, BudgetSnapshot
from wb.services.budgets import BudgetService


@pytest.fixture()
def mock_client() -> MagicMock:
    """Create a mock PromotionClient."""
    return MagicMock()


@pytest.fixture()
def service(mock_client: MagicMock) -> BudgetService:
    """Create a BudgetService with a mocked client."""
    return BudgetService(client=mock_client)


class TestGetBalance:
    """Tests for BudgetService.get_balance."""

    def test_returns_account_balance(
        self, service: BudgetService, mock_client: MagicMock,
    ) -> None:
        """get_balance returns an AccountBalance domain object."""
        mock_client.get_balance.return_value = {
            'balance': 150000,
            'net': 120000,
            'bonus': 30000,
        }

        result = service.get_balance()

        assert isinstance(result, AccountBalance)
        assert result.balance == 150000
        assert result.net == 120000
        assert result.bonus == 30000
        mock_client.get_balance.assert_called_once()


class TestGetBudget:
    """Tests for BudgetService.get_budget."""

    def test_returns_budget_snapshot(
        self, service: BudgetService, mock_client: MagicMock,
    ) -> None:
        """get_budget returns BudgetSnapshot with correct campaign_id."""
        mock_client.get_budget.return_value = {
            'total': 500000,
            'dailyBudget': 10000,
            'balance': 350000,
        }

        result = service.get_budget(campaign_id=42)

        assert isinstance(result, BudgetSnapshot)
        assert result.campaign_id == 42
        assert result.total == 500000
        assert result.daily == 10000
        assert result.balance == 350000
        mock_client.get_budget.assert_called_once_with(42)

    def test_returns_budget_snapshot_with_zero_values(
        self, service: BudgetService, mock_client: MagicMock,
    ) -> None:
        """get_budget handles zero values gracefully."""
        mock_client.get_budget.return_value = {
            'total': 0,
            'dailyBudget': 0,
            'balance': 0,
        }

        result = service.get_budget(campaign_id=99)

        assert isinstance(result, BudgetSnapshot)
        assert result.campaign_id == 99
        assert result.total == 0
        assert result.daily == 0
        assert result.balance == 0
