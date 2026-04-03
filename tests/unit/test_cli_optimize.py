"""Tests for optimization CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.domain.enums import OptimizationAction, TargetType
from wb.domain.models import MutationResult, OptimizationDecision

runner = CliRunner()

OPTIMIZER_FACTORY = 'wb.services._factory.create_optimizer_service'


def _make_decision(
    action: OptimizationAction = OptimizationAction.RAISE_CLUSTER_BID,
    target_id: str = 'sneakers',
    nm_id: int = 100,
) -> OptimizationDecision:
    """Build a sample OptimizationDecision."""
    return OptimizationDecision(
        action=action,
        target_type=TargetType.CLUSTER,
        target_id=target_id,
        nm_id=nm_id,
        current_value='500',
        proposed_value='600',
        reason='Test reason',
        confidence=0.8,
    )


def _make_result() -> MutationResult:
    """Build a sample MutationResult."""
    return MutationResult(
        success=True, action='test', target_id='1', message='Done',
    )


class TestOptimizePlan:
    """Tests for 'optimize plan' command."""

    def test_help(self):
        result = runner.invoke(app, ['optimize', 'plan', '--help'])
        assert result.exit_code == 0
        assert 'plan' in result.output.lower()

    @patch(OPTIMIZER_FACTORY)
    def test_plan_json_output(self, mock_factory):
        svc = MagicMock()
        svc.plan_all.return_value = [_make_decision()]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'optimize', 'plan',
            '--campaign', '1', '--nm', '100',
            '--from', '2025-01-01', '--to', '2025-01-31',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]['action'] == 'raise_cluster_bid'

    @patch(OPTIMIZER_FACTORY)
    def test_plan_empty(self, mock_factory):
        svc = MagicMock()
        svc.plan_all.return_value = []
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'optimize', 'plan',
            '--campaign', '1', '--nm', '100',
            '--from', '2025-01-01', '--to', '2025-01-31',
        ])
        assert result.exit_code == 0
        assert 'No optimization' in result.output


class TestOptimizeRun:
    """Tests for 'optimize run' command."""

    @patch(OPTIMIZER_FACTORY)
    def test_run_without_apply_shows_plan_only(self, mock_factory):
        svc = MagicMock()
        svc.plan_all.return_value = [_make_decision()]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'optimize', 'run',
            '--campaign', '1', '--nm', '100',
            '--from', '2025-01-01', '--to', '2025-01-31',
        ])
        assert result.exit_code == 0
        svc.apply_all.assert_not_called()

    @patch(OPTIMIZER_FACTORY)
    def test_run_with_apply_and_yes(self, mock_factory):
        svc = MagicMock()
        svc.plan_all.return_value = [_make_decision()]
        svc.apply_all.return_value = [_make_result()]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'optimize', 'run',
            '--campaign', '1', '--nm', '100',
            '--from', '2025-01-01', '--to', '2025-01-31',
            '--apply', '--yes',
        ])
        assert result.exit_code == 0
        svc.apply_all.assert_called_once()


class TestOptimizeClusters:
    """Tests for 'optimize clusters' command."""

    def test_help(self):
        result = runner.invoke(app, ['optimize', 'clusters', '--help'])
        assert result.exit_code == 0

    @patch(OPTIMIZER_FACTORY)
    def test_clusters_json_output(self, mock_factory):
        svc = MagicMock()
        svc.plan_clusters.return_value = [_make_decision()]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'optimize', 'clusters',
            '--campaign', '1', '--nm', '100',
            '--from', '2025-01-01', '--to', '2025-01-31',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]['target_id'] == 'sneakers'


class TestOptimizeBudget:
    """Tests for 'optimize budget' command."""

    @patch(OPTIMIZER_FACTORY)
    def test_budget_json_output(self, mock_factory):
        svc = MagicMock()
        svc.plan_budget.return_value = [OptimizationDecision(
            action=OptimizationAction.TOPUP_BUDGET,
            target_type=TargetType.CAMPAIGN,
            target_id='1',
            proposed_value='5000',
            reason='Budget at risk',
            confidence=0.9,
        )]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'optimize', 'budget', '--campaign', '1',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]['action'] == 'topup_budget'


class TestOptimizeNegatives:
    """Tests for 'optimize negatives' command."""

    @patch(OPTIMIZER_FACTORY)
    def test_negatives_json_output(self, mock_factory):
        svc = MagicMock()
        svc.plan_negatives.return_value = [OptimizationDecision(
            action=OptimizationAction.ADD_MINUS_PHRASE,
            target_type=TargetType.CLUSTER,
            target_id='bad shoes',
            nm_id=100,
            reason='Waste cluster',
            confidence=0.7,
        )]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'optimize', 'negatives',
            '--campaign', '1', '--nm', '100',
            '--from', '2025-01-01', '--to', '2025-01-31',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]['target_id'] == 'bad shoes'


class TestOptimizePortfolio:
    """Tests for 'optimize portfolio' command."""

    @patch(OPTIMIZER_FACTORY)
    def test_portfolio_empty(self, mock_factory):
        svc = MagicMock()
        svc.plan_portfolio.return_value = []
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'optimize', 'portfolio',
            '--campaign', '1',
            '--from', '2025-01-01', '--to', '2025-01-31',
        ])
        assert result.exit_code == 0
        assert 'No optimization' in result.output
