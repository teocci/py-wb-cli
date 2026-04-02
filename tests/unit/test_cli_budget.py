"""Tests for budget CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.domain.models import AccountBalance, BudgetSnapshot

runner = CliRunner()

FACTORY_PATH = 'wb.services._factory.create_budget_service'


def _make_balance() -> AccountBalance:
    """Create an AccountBalance instance for testing."""
    return AccountBalance(
        balance=100000,
        net=85000,
        bonus=15000,
    )


def _make_budget(campaign_id: int = 100) -> BudgetSnapshot:
    """Create a BudgetSnapshot instance for testing."""
    return BudgetSnapshot(
        campaign_id=campaign_id,
        total=50000,
        cash=30000,
        netting=20000,
    )


@pytest.fixture()
def mock_svc() -> MagicMock:
    """Return a MagicMock pretending to be BudgetService."""
    return MagicMock()


class TestBudgetBalance:
    """Tests for the 'budget balance' command."""

    def test_budget_balance_help(self) -> None:
        """Help flag exits cleanly with usage information."""
        result = runner.invoke(app, ['budget', 'balance', '--help'])
        assert result.exit_code == 0
        assert 'balance' in result.output.lower()

    @patch(FACTORY_PATH)
    def test_budget_balance_json(self, mock_factory: MagicMock) -> None:
        """JSON output contains account balance data."""
        svc = MagicMock()
        svc.get_balance.return_value = _make_balance()
        mock_factory.return_value = svc

        result = runner.invoke(app, ['--json', 'budget', 'balance'])
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert parsed['balance'] == 100000
        assert parsed['net'] == 85000
        assert parsed['bonus'] == 15000


class TestBudgetGet:
    """Tests for the 'budget get' command."""

    @patch(FACTORY_PATH)
    def test_budget_get_json(self, mock_factory: MagicMock) -> None:
        """JSON output contains budget snapshot data."""
        svc = MagicMock()
        svc.get_budget.return_value = _make_budget()
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['--json', 'budget', 'get', '--campaign', '100'],
        )
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert parsed['campaign_id'] == 100
        assert parsed['total'] == 50000
        assert parsed['cash'] == 30000
        assert parsed['netting'] == 20000
