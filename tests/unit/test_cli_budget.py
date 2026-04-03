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


STORE_PATH = 'wb.services._factory.create_cache_store'


class TestBudgetHistory:
    """Tests for the 'budget history' command."""

    def test_budget_history_help(self) -> None:
        result = runner.invoke(app, ['budget', 'history', '--help'])
        assert result.exit_code == 0

    @patch(STORE_PATH)
    def test_budget_history_empty(self, mock_store_factory: MagicMock) -> None:
        """Shows empty result when no events are stored."""
        store = MagicMock()
        store.list_budget_events.return_value = []
        mock_store_factory.return_value = store
        result = runner.invoke(app, ['budget', 'history'])
        assert result.exit_code == 0
        store.list_budget_events.assert_called_once()

    @patch(STORE_PATH)
    def test_budget_history_campaign_filter(self, mock_store_factory: MagicMock) -> None:
        """--campaign passes campaign_id to store."""
        store = MagicMock()
        store.list_budget_events.return_value = []
        mock_store_factory.return_value = store
        runner.invoke(app, ['budget', 'history', '--campaign', '123'])
        call_args = store.list_budget_events.call_args
        assert call_args.args[1] == 123

    @patch(STORE_PATH)
    def test_budget_topup_records_event(self, mock_store_factory: MagicMock) -> None:
        """Successful topup saves a budget event to the cache."""
        store = MagicMock()
        mock_store_factory.return_value = store
        with patch(FACTORY_PATH) as mock_svc_factory:
            from wb.domain.models import MutationResult
            svc = MagicMock()
            svc.topup.return_value = MutationResult(
                success=True,
                action='deposit 500',
                target_id='42',
                message='Deposited 500 kopecks',
            )
            mock_svc_factory.return_value = svc
            result = runner.invoke(
                app, ['budget', 'topup', '--campaign', '42', '--sum', '500', '--yes'],
            )
        assert result.exit_code == 0
        store.save_budget_event.assert_called_once()
        saved_evt = store.save_budget_event.call_args.args[0]
        assert saved_evt.event_type == 'topup'
        assert saved_evt.amount == 500
        assert saved_evt.campaign_id == 42
