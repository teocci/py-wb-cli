"""Tests for wb.cli.snapshot — snapshot CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.domain.cache_models import CampaignSnapshot, ClusterRecord, StatsRecord

runner = CliRunner()

SVC_PATH = 'wb.services._factory.create_cache_service'
STORE_PATH = 'wb.services._factory.create_cache_store'


def _make_svc() -> MagicMock:
    svc = MagicMock()
    svc.summary.return_value = {
        'campaigns': 2,
        'campaign_stats': 10,
        'cluster_snapshots': 30,
        'budget_events': 5,
    }
    svc.snapshot_campaign.return_value = {
        'campaigns': 1, 'stats': 1, 'clusters': 3,
    }
    svc.snapshot_all.return_value = {'campaigns': 2, 'stats': 0, 'clusters': 0}
    svc.history_campaigns.return_value = []
    svc.history_stats.return_value = []
    svc.history_clusters.return_value = []
    svc.clear.return_value = {
        'campaigns': 1,
        'campaign_stats': 0,
        'cluster_snapshots': 0,
        'budget_events': 0,
    }
    return svc


# ── cache list ────────────────────────────────────────────────────────

class TestSnapshotList:

    @patch(SVC_PATH)
    def test_list_help(self, _) -> None:
        result = runner.invoke(app, ['snapshot', 'list', '--help'])
        assert result.exit_code == 0

    @patch(SVC_PATH)
    def test_list_summary(self, mock_factory: MagicMock) -> None:
        """Without --campaign, shows summary table."""
        mock_factory.return_value = _make_svc()
        result = runner.invoke(app, ['snapshot', 'list'])
        assert result.exit_code == 0

    @patch(SVC_PATH)
    def test_list_summary_table_renders_full_table_names(
            self, mock_factory: MagicMock,
    ) -> None:
        """Summary rows must contain full table names, not per-character columns.

        Regression for F-17: passing the dict instead of the rows list to
        renderer.display() made Rich unpack each table-name string into
        single-character cells (c | a | m | p | a | i | g | n | s).
        """
        mock_factory.return_value = _make_svc()
        result = runner.invoke(app, ['snapshot', 'list'])
        assert result.exit_code == 0
        assert 'campaign_stats' in result.output
        assert 'cluster_snapshots' in result.output
        assert 'budget_events' in result.output

    @patch(SVC_PATH)
    def test_list_summary_json(self, mock_factory: MagicMock) -> None:
        """JSON output preserves the dict shape."""
        mock_factory.return_value = _make_svc()
        result = runner.invoke(app, ['--json', 'snapshot', 'list'])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload == {
            'campaigns': 2,
            'campaign_stats': 10,
            'cluster_snapshots': 30,
            'budget_events': 5,
        }

    @patch(SVC_PATH)
    def test_list_with_campaign(self, mock_factory: MagicMock) -> None:
        svc = _make_svc()
        svc.history_campaigns.return_value = [
            CampaignSnapshot(
                campaign_id=111, profile='test',
                snapshot_time='2026-04-01T12:00:00+00:00',
                name='Shoes', status=9, campaign_type=9,
                daily_budget=0, payload_json='{}',
            )
        ]
        mock_factory.return_value = svc
        result = runner.invoke(app, ['snapshot', 'list', '--campaign', '111'])
        assert result.exit_code == 0


# ── cache snapshot ────────────────────────────────────────────────────

class TestSnapshotCapture:

    @patch(SVC_PATH)
    def test_snapshot_calls_service(self, mock_factory: MagicMock) -> None:
        svc = _make_svc()
        mock_factory.return_value = svc
        result = runner.invoke(app, ['snapshot', 'capture', '--campaign', '123'])
        assert result.exit_code == 0
        svc.snapshot_campaign.assert_called_once()
        call_args = svc.snapshot_campaign.call_args
        assert call_args.args[0] == 123

    @patch(SVC_PATH)
    def test_snapshot_with_nm(self, mock_factory: MagicMock) -> None:
        svc = _make_svc()
        mock_factory.return_value = svc
        result = runner.invoke(
            app, ['snapshot', 'capture', '--campaign', '123', '--nm', '456']
        )
        assert result.exit_code == 0
        call_kwargs = svc.snapshot_campaign.call_args.kwargs
        assert call_kwargs['nm_id'] == 456

    @patch(SVC_PATH)
    def test_snapshot_no_stats(self, mock_factory: MagicMock) -> None:
        svc = _make_svc()
        mock_factory.return_value = svc
        runner.invoke(app, ['snapshot', 'capture', '--campaign', '123', '--no-stats'])
        call_kwargs = svc.snapshot_campaign.call_args.kwargs
        assert call_kwargs['with_stats'] is False

    @patch(SVC_PATH)
    def test_snapshot_no_clusters(self, mock_factory: MagicMock) -> None:
        svc = _make_svc()
        mock_factory.return_value = svc
        runner.invoke(app, ['snapshot', 'capture', '--campaign', '123', '--no-clusters'])
        call_kwargs = svc.snapshot_campaign.call_args.kwargs
        assert call_kwargs['with_clusters'] is False


# ── cache snapshot-all ────────────────────────────────────────────────

class TestSnapshotCaptureAll:

    @patch(SVC_PATH)
    def test_snapshot_all_calls_service(self, mock_factory: MagicMock) -> None:
        svc = _make_svc()
        mock_factory.return_value = svc
        result = runner.invoke(app, ['snapshot', 'capture-all'])
        assert result.exit_code == 0
        svc.snapshot_all.assert_called_once()


# ── cache clear ───────────────────────────────────────────────────────

class TestSnapshotClear:

    @patch(SVC_PATH)
    def test_clear_with_yes(self, mock_factory: MagicMock) -> None:
        svc = _make_svc()
        mock_factory.return_value = svc
        result = runner.invoke(app, ['snapshot', 'clear', '--yes'])
        assert result.exit_code == 0
        svc.clear.assert_called_once()

    @patch(SVC_PATH)
    def test_clear_with_campaign(self, mock_factory: MagicMock) -> None:
        svc = _make_svc()
        mock_factory.return_value = svc
        runner.invoke(app, ['snapshot', 'clear', '--campaign', '99', '--yes'])
        call_args = svc.clear.call_args
        assert call_args.args[1] == 99

    @patch(SVC_PATH)
    def test_clear_requires_confirmation(self, mock_factory: MagicMock) -> None:
        """Without --yes, aborts when user declines."""
        svc = _make_svc()
        mock_factory.return_value = svc
        result = runner.invoke(app, ['snapshot', 'clear'], input='n\n')
        svc.clear.assert_not_called()


# ── cache history ─────────────────────────────────────────────────────

class TestSnapshotHistory:

    @patch(SVC_PATH)
    def test_history_campaigns(self, mock_factory: MagicMock) -> None:
        mock_factory.return_value = _make_svc()
        result = runner.invoke(app, ['snapshot', 'history', 'campaigns'])
        assert result.exit_code == 0

    @patch(SVC_PATH)
    def test_history_campaigns_with_filter(self, mock_factory: MagicMock) -> None:
        svc = _make_svc()
        mock_factory.return_value = svc
        runner.invoke(app, ['snapshot', 'history', 'campaigns', '--campaign', '111'])
        svc.history_campaigns.assert_called_once()
        assert svc.history_campaigns.call_args.args[1] == 111

    @patch(SVC_PATH)
    def test_history_stats_requires_campaign(self, mock_factory: MagicMock) -> None:
        result = runner.invoke(app, ['snapshot', 'history', 'stats'])
        assert result.exit_code != 0

    @patch(SVC_PATH)
    def test_history_stats_passes_dates(self, mock_factory: MagicMock) -> None:
        svc = _make_svc()
        mock_factory.return_value = svc
        runner.invoke(app, [
            'snapshot', 'history', 'stats',
            '--campaign', '123',
            '--from', '2026-01-01',
            '--to', '2026-03-31',
        ])
        call_kwargs = svc.history_stats.call_args
        assert call_kwargs.args[2] == '2026-01-01'
        assert call_kwargs.args[3] == '2026-03-31'

    @patch(SVC_PATH)
    def test_history_clusters(self, mock_factory: MagicMock) -> None:
        svc = _make_svc()
        mock_factory.return_value = svc
        result = runner.invoke(
            app, ['snapshot', 'history', 'clusters', '--campaign', '123', '--nm', '456']
        )
        assert result.exit_code == 0
        svc.history_clusters.assert_called_once()
        assert svc.history_clusters.call_args.args[2] == 456

    @patch(SVC_PATH)
    def test_json_output(self, mock_factory: MagicMock) -> None:
        svc = _make_svc()
        svc.history_campaigns.return_value = [
            CampaignSnapshot(
                campaign_id=1, profile='test',
                snapshot_time='2026-04-01T00:00:00+00:00',
                name='Test', status=9, campaign_type=9,
                daily_budget=0, payload_json='{}',
            )
        ]
        mock_factory.return_value = svc
        result = runner.invoke(app, ['--json', 'snapshot', 'history', 'campaigns'])
        assert result.exit_code == 0
