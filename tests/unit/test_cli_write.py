"""Tests for Phase 2 write CLI commands."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.domain.models import MutationResult

runner = CliRunner()

CAMPAIGN_FACTORY = 'wb.services._factory.create_campaign_service'
BUDGET_FACTORY = 'wb.services._factory.create_budget_service'
BID_FACTORY = 'wb.services._factory.create_bid_service'
AUDIT_FACTORY = 'wb.services._factory.create_audit_logger'


def _ok_result(action: str = 'test', target_id: str = '1') -> MutationResult:
    """Build a successful MutationResult."""
    return MutationResult(
        success=True, action=action, target_id=target_id, message='Done',
    )


def _dry_result(action: str = 'test', target_id: str = '1') -> MutationResult:
    """Build a dry-run MutationResult."""
    return MutationResult(
        success=True, action=action, target_id=target_id,
        dry_run=True, message='Would do it',
    )


@pytest.fixture()
def mock_audit():
    """Patch audit logger so tests don't write to disk."""
    with patch(AUDIT_FACTORY) as mock:
        mock.return_value = MagicMock()
        yield mock


# ── Campaign write commands ───────────────────────────────────────────

class TestCampaignStart:
    """Tests for 'campaign start' command."""

    def test_help(self):
        result = runner.invoke(app, ['campaign', 'start', '--help'])
        assert result.exit_code == 0
        assert 'Start' in result.output

    @patch(CAMPAIGN_FACTORY)
    def test_start_with_yes_flag(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.start_campaign.return_value = _ok_result('start campaign 10', '10')
        mock_factory.return_value = svc

        result = runner.invoke(app, ['campaign', 'start', '10', '--yes'])
        assert result.exit_code == 0
        svc.start_campaign.assert_called_once_with(10, dry_run=False)

    @patch(CAMPAIGN_FACTORY)
    def test_start_dry_run(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.start_campaign.return_value = _dry_result()
        mock_factory.return_value = svc

        result = runner.invoke(app, ['campaign', 'start', '10', '--dry-run'])
        assert result.exit_code == 0
        assert 'DRY-RUN' in result.output
        svc.start_campaign.assert_called_once_with(10, dry_run=True)


class TestCampaignPause:
    """Tests for 'campaign pause' command."""

    @patch(CAMPAIGN_FACTORY)
    def test_pause_with_yes(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.pause_campaign.return_value = _ok_result()
        mock_factory.return_value = svc

        result = runner.invoke(app, ['campaign', 'pause', '5', '--yes'])
        assert result.exit_code == 0
        svc.pause_campaign.assert_called_once_with(5, dry_run=False)

    @patch(CAMPAIGN_FACTORY)
    def test_pause_dry_run(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.pause_campaign.return_value = _dry_result()
        mock_factory.return_value = svc

        result = runner.invoke(app, ['campaign', 'pause', '5', '--dry-run'])
        assert result.exit_code == 0
        assert 'DRY-RUN' in result.output


class TestCampaignStop:
    """Tests for 'campaign stop' command."""

    @patch(CAMPAIGN_FACTORY)
    def test_stop_with_yes(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.stop_campaign.return_value = _ok_result()
        mock_factory.return_value = svc

        result = runner.invoke(app, ['campaign', 'stop', '3', '--yes'])
        assert result.exit_code == 0

    @patch(CAMPAIGN_FACTORY)
    def test_stop_dry_run(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.stop_campaign.return_value = _dry_result()
        mock_factory.return_value = svc

        result = runner.invoke(app, ['campaign', 'stop', '3', '--dry-run'])
        assert 'DRY-RUN' in result.output


class TestCampaignRename:
    """Tests for 'campaign rename' command."""

    @patch(CAMPAIGN_FACTORY)
    def test_rename_with_yes(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.rename_campaign.return_value = _ok_result()
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['campaign', 'rename', '7', '--name', 'My Campaign', '--yes']
        )
        assert result.exit_code == 0
        svc.rename_campaign.assert_called_once_with(7, 'My Campaign', dry_run=False)

    def test_rename_requires_name(self):
        result = runner.invoke(app, ['campaign', 'rename', '7', '--yes'])
        assert result.exit_code != 0


class TestCampaignDelete:
    """Tests for 'campaign delete' command."""

    @patch(CAMPAIGN_FACTORY)
    def test_delete_with_yes(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.delete_campaign.return_value = _ok_result()
        mock_factory.return_value = svc

        result = runner.invoke(app, ['campaign', 'delete', '8', '--yes'])
        assert result.exit_code == 0
        svc.delete_campaign.assert_called_once_with(8, dry_run=False)

    @patch(CAMPAIGN_FACTORY)
    def test_delete_dry_run(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.delete_campaign.return_value = _dry_result()
        mock_factory.return_value = svc

        result = runner.invoke(app, ['campaign', 'delete', '8', '--dry-run'])
        assert 'DRY-RUN' in result.output


class TestCampaignCreate:
    """Tests for 'campaign create' command."""

    @patch(CAMPAIGN_FACTORY)
    def test_create_basic(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.create_campaign.return_value = _ok_result()
        mock_factory.return_value = svc

        result = runner.invoke(
            app,
            [
                'campaign', 'create',
                '--name', 'Test',
                '--nms', '100,200',
                '--yes',
            ],
        )
        assert result.exit_code == 0
        svc.create_campaign.assert_called_once()

    @patch(CAMPAIGN_FACTORY)
    def test_create_dry_run(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.create_campaign.return_value = _dry_result()
        mock_factory.return_value = svc

        result = runner.invoke(
            app,
            [
                'campaign', 'create',
                '--name', 'Test',
                '--nms', '100',
                '--dry-run',
            ],
        )
        assert 'DRY-RUN' in result.output

    def test_create_missing_name_fails(self):
        result = runner.invoke(
            app, ['campaign', 'create', '--nms', '1']
        )
        assert result.exit_code != 0


class TestCampaignAddItems:
    """Tests for 'campaign add-items' command."""

    @patch(CAMPAIGN_FACTORY)
    def test_add_items_with_yes(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.add_items.return_value = _ok_result()
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['campaign', 'add-items', '10', '--nms', '1,2,3', '--yes']
        )
        assert result.exit_code == 0
        svc.add_items.assert_called_once_with(10, [1, 2, 3], dry_run=False)

    @patch(CAMPAIGN_FACTORY)
    def test_add_items_dry_run(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.add_items.return_value = _dry_result()
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['campaign', 'add-items', '10', '--nms', '1', '--dry-run']
        )
        assert 'DRY-RUN' in result.output


class TestCampaignRemoveItems:
    """Tests for 'campaign remove-items' command."""

    @patch(CAMPAIGN_FACTORY)
    def test_remove_items_with_yes(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.remove_items.return_value = _ok_result()
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['campaign', 'remove-items', '10', '--nms', '5,6', '--yes']
        )
        assert result.exit_code == 0
        svc.remove_items.assert_called_once_with(10, [5, 6], dry_run=False)


class TestCampaignSetPlacements:
    """Tests for 'campaign set-placements' command."""

    @patch(CAMPAIGN_FACTORY)
    def test_set_placements_defaults(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.set_placements.return_value = _ok_result()
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['campaign', 'set-placements', '10', '--yes']
        )
        assert result.exit_code == 0
        svc.set_placements.assert_called_once()

    @patch(CAMPAIGN_FACTORY)
    def test_set_placements_no_catalog(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.set_placements.return_value = _ok_result()
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['campaign', 'set-placements', '10', '--no-catalog', '--yes']
        )
        assert result.exit_code == 0
        call_args = svc.set_placements.call_args
        config = call_args[0][1]
        assert config.recommendations_enabled is False


# ── Budget write commands ──────────────────────────────────────────────

class TestBudgetTopup:
    """Tests for 'budget topup' command."""

    def test_help(self):
        result = runner.invoke(app, ['budget', 'topup', '--help'])
        assert result.exit_code == 0
        assert 'Deposit' in result.output or 'deposit' in result.output.lower()

    @patch(BUDGET_FACTORY)
    def test_topup_with_yes(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.topup.return_value = _ok_result()
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['budget', 'topup', '--campaign', '5', '--sum', '3000', '--yes']
        )
        assert result.exit_code == 0
        svc.topup.assert_called_once_with(5, 3000, dry_run=False)

    @patch(BUDGET_FACTORY)
    def test_topup_dry_run(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.topup.return_value = _dry_result()
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['budget', 'topup', '--campaign', '5', '--sum', '1000', '--dry-run']
        )
        assert result.exit_code == 0
        assert 'DRY-RUN' in result.output


# ── Bid write commands ──────────────────────────────────────────────────

class TestBidSetItem:
    """Tests for 'bid set-item' command."""

    def test_help(self):
        result = runner.invoke(app, ['bid', 'set-item', '--help'])
        assert result.exit_code == 0

    @patch(BID_FACTORY)
    def test_set_item_with_yes(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.set_item_bid.return_value = _ok_result()
        mock_factory.return_value = svc

        result = runner.invoke(
            app,
            ['bid', 'set-item', '--campaign', '10', '--nm', '123', '--cpm', '400', '--yes'],
        )
        assert result.exit_code == 0
        svc.set_item_bid.assert_called_once()

    @patch(BID_FACTORY)
    def test_set_item_dry_run(self, mock_factory, mock_audit):
        svc = MagicMock()
        svc.set_item_bid.return_value = _dry_result()
        mock_factory.return_value = svc

        result = runner.invoke(
            app,
            ['bid', 'set-item', '--campaign', '10', '--nm', '1', '--cpm', '200', '--dry-run'],
        )
        assert 'DRY-RUN' in result.output


class TestBidSetItems:
    """Tests for 'bid set-items' command."""

    def test_help(self):
        result = runner.invoke(app, ['bid', 'set-items', '--help'])
        assert result.exit_code == 0

    @patch(BID_FACTORY)
    def test_set_items_from_file(self, mock_factory, mock_audit, tmp_path):
        svc = MagicMock()
        svc.set_item_bids.return_value = [_ok_result(), _ok_result()]
        mock_factory.return_value = svc

        bid_file = tmp_path / 'bids.json'
        bid_file.write_text(
            json.dumps([
                {'nm_id': 1, 'cpm': 100},
                {'nm_id': 2, 'cpm': 200},
            ])
        )

        result = runner.invoke(
            app,
            [
                'bid', 'set-items',
                '--campaign', '10',
                '--file', str(bid_file),
                '--yes',
            ],
        )
        assert result.exit_code == 0
        svc.set_item_bids.assert_called_once()

    def test_set_items_invalid_json(self, tmp_path):
        bad_file = tmp_path / 'bad.json'
        bad_file.write_text('not json')

        result = runner.invoke(
            app,
            ['bid', 'set-items', '--campaign', '10', '--file', str(bad_file)],
        )
        assert result.exit_code != 0
