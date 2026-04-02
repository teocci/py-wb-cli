"""Tests for cluster CLI commands (normquery API)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.domain.models import ClusterStats, MinusPhraseSet, MutationResult, SearchCluster

runner = CliRunner()

CLUSTER_FACTORY = 'wb.services._factory.create_cluster_service'
AUDIT_FACTORY = 'wb.services._factory.create_audit_logger'


def _make_cluster(
        is_active: bool = True,
        norm_query: str = 'perfume',
) -> SearchCluster:
    """Create a SearchCluster instance for testing."""
    return SearchCluster(
        norm_query=norm_query,
        is_active=is_active,
        bid=150,
        nm_id=100,
    )


def _make_cluster_stats(norm_query: str = 'perfume') -> ClusterStats:
    """Create a ClusterStats instance for testing."""
    return ClusterStats(
        norm_query=norm_query,
        views=5000,
        clicks=250,
        ctr=5.0,
        orders=25,
        spend=12000,
    )


@pytest.fixture()
def mock_svc() -> MagicMock:
    """Return a MagicMock pretending to be ClusterService."""
    return MagicMock()


class TestClusterList:
    """Tests for the 'cluster list' command."""

    def test_cluster_list_help(self) -> None:
        """Help flag exits cleanly with usage information."""
        result = runner.invoke(app, ['cluster', 'list', '--help'])
        assert result.exit_code == 0
        assert 'cluster' in result.output.lower()

    @patch(CLUSTER_FACTORY)
    def test_cluster_list_json(self, mock_factory: MagicMock) -> None:
        """JSON output contains cluster data."""
        svc = MagicMock()
        svc.list_clusters.return_value = [_make_cluster()]
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['--json', 'cluster', 'list', '--campaign', '42', '--nm', '100'],
        )
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]['norm_query'] == 'perfume'
        assert parsed[0]['is_active'] is True

    @patch(CLUSTER_FACTORY)
    def test_cluster_list_empty(self, mock_factory: MagicMock) -> None:
        """Empty cluster list shows success message."""
        svc = MagicMock()
        svc.list_clusters.return_value = []
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['--json', 'cluster', 'list', '--campaign', '42', '--nm', '100'],
        )
        assert result.exit_code == 0
        assert 'No clusters found' in result.output


class TestClusterActive:
    """Tests for the 'cluster active' command."""

    @patch(CLUSTER_FACTORY)
    def test_cluster_active_json(self, mock_factory: MagicMock) -> None:
        """JSON output contains only active clusters."""
        svc = MagicMock()
        svc.get_active_clusters.return_value = [_make_cluster(is_active=True)]
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['--json', 'cluster', 'active', '--campaign', '42', '--nm', '100'],
        )
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]['is_active'] is True


class TestClusterInactive:
    """Tests for the 'cluster inactive' command."""

    @patch(CLUSTER_FACTORY)
    def test_cluster_inactive_json(self, mock_factory: MagicMock) -> None:
        """JSON output contains only inactive clusters."""
        svc = MagicMock()
        svc.get_inactive_clusters.return_value = [
            _make_cluster(is_active=False),
        ]
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['--json', 'cluster', 'inactive', '--campaign', '42', '--nm', '100'],
        )
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]['is_active'] is False


class TestClusterBids:
    """Tests for the 'cluster bids' command."""

    @patch(CLUSTER_FACTORY)
    def test_cluster_bids_json(self, mock_factory: MagicMock) -> None:
        """JSON output contains cluster bid data."""
        svc = MagicMock()
        svc.get_cluster_bids.return_value = [_make_cluster()]
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['--json', 'cluster', 'bids', '--campaign', '42', '--nm', '100'],
        )
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]['bid'] == 150
        assert parsed[0]['nm_id'] == 100


class TestClusterStats:
    """Tests for the 'cluster stats' command."""

    @patch(CLUSTER_FACTORY)
    def test_cluster_stats_json(self, mock_factory: MagicMock) -> None:
        """JSON output contains cluster statistics."""
        svc = MagicMock()
        svc.get_cluster_stats.return_value = [_make_cluster_stats()]
        mock_factory.return_value = svc

        result = runner.invoke(
            app, [
                '--json', 'cluster', 'stats',
                '--campaign', '42', '--nm', '100',
                '--from', '2025-12-01', '--to', '2025-12-31',
            ],
        )
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]['norm_query'] == 'perfume'
        assert parsed[0]['views'] == 5000
        assert parsed[0]['spend'] == 12000


# ── Helpers for write tests ──────────────────────────────────────────


def _ok_result(action: str = 'test', target_id: str = '100') -> MutationResult:
    """Build a successful MutationResult."""
    return MutationResult(
        success=True, action=action, target_id=target_id, message='Done',
    )


def _dry_result(action: str = 'test', target_id: str = '100') -> MutationResult:
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


# ── Stats daily tests ────────────────────────────────────────────────


class TestClusterStatsDaily:
    """Tests for the 'cluster stats-daily' command."""

    def test_help(self) -> None:
        result = runner.invoke(app, ['cluster', 'stats-daily', '--help'])
        assert result.exit_code == 0
        assert 'daily' in result.output.lower()

    @patch(CLUSTER_FACTORY)
    def test_stats_daily_json(self, mock_factory: MagicMock) -> None:
        """JSON output contains daily stats."""
        svc = MagicMock()
        svc.get_cluster_stats_daily.return_value = [
            {'date': '2025-12-01', 'stat': {'normQuery': 'perfume', 'views': 100}},
        ]
        mock_factory.return_value = svc

        result = runner.invoke(
            app, [
                '--json', 'cluster', 'stats-daily',
                '--campaign', '42', '--nm', '100',
                '--from', '2025-12-01', '--to', '2025-12-02',
            ],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]['date'] == '2025-12-01'


# ── Set bids tests ───────────────────────────────────────────────────


class TestClusterSetBids:
    """Tests for the 'cluster set-bids' command."""

    def test_help(self) -> None:
        result = runner.invoke(app, ['cluster', 'set-bids', '--help'])
        assert result.exit_code == 0
        assert 'bid' in result.output.lower()

    @patch(CLUSTER_FACTORY)
    def test_set_bids_with_yes(self, mock_factory: MagicMock, mock_audit) -> None:
        svc = MagicMock()
        svc.set_cluster_bids.return_value = _ok_result()
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'cluster', 'set-bids',
            '--campaign', '42', '--nm', '100',
            '--query', 'sneakers', '--bid', '500', '--yes',
        ])
        assert result.exit_code == 0
        svc.set_cluster_bids.assert_called_once()

    @patch(CLUSTER_FACTORY)
    def test_set_bids_dry_run(self, mock_factory: MagicMock, mock_audit) -> None:
        svc = MagicMock()
        svc.set_cluster_bids.return_value = _dry_result()
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'cluster', 'set-bids',
            '--campaign', '42', '--nm', '100',
            '--query', 'sneakers', '--bid', '500', '--dry-run',
        ])
        assert result.exit_code == 0
        assert 'DRY-RUN' in result.output
        svc.set_cluster_bids.assert_called_once()


class TestClusterSetBidsFile:
    """Tests for the 'cluster set-bids-file' command."""

    @patch(CLUSTER_FACTORY)
    def test_set_bids_file_valid(
        self, mock_factory: MagicMock, mock_audit, tmp_path,
    ) -> None:
        svc = MagicMock()
        svc.set_cluster_bids.return_value = _ok_result()
        mock_factory.return_value = svc

        bid_file = tmp_path / 'bids.json'
        bid_file.write_text(json.dumps([
            {'nm_id': 100, 'norm_query': 'sneakers', 'bid': 500},
        ]))

        result = runner.invoke(app, [
            'cluster', 'set-bids-file',
            '--campaign', '42', '--file', str(bid_file), '--yes',
        ])
        assert result.exit_code == 0
        svc.set_cluster_bids.assert_called_once()

    @patch(CLUSTER_FACTORY)
    def test_set_bids_file_invalid_json(
        self, mock_factory: MagicMock, mock_audit, tmp_path,
    ) -> None:
        bid_file = tmp_path / 'bids.json'
        bid_file.write_text('not json')

        result = runner.invoke(app, [
            'cluster', 'set-bids-file',
            '--campaign', '42', '--file', str(bid_file), '--yes',
        ])
        assert result.exit_code == 2


# ── Delete bids tests ────────────────────────────────────────────────


class TestClusterDeleteBids:
    """Tests for the 'cluster delete-bids' command."""

    @patch(CLUSTER_FACTORY)
    def test_delete_bids_with_yes(self, mock_factory: MagicMock, mock_audit) -> None:
        svc = MagicMock()
        svc.delete_cluster_bids.return_value = _ok_result()
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'cluster', 'delete-bids',
            '--campaign', '42', '--nm', '100',
            '--query', 'sneakers', '--bid', '500', '--yes',
        ])
        assert result.exit_code == 0
        svc.delete_cluster_bids.assert_called_once()

    @patch(CLUSTER_FACTORY)
    def test_delete_bids_dry_run(self, mock_factory: MagicMock, mock_audit) -> None:
        svc = MagicMock()
        svc.delete_cluster_bids.return_value = _dry_result()
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'cluster', 'delete-bids',
            '--campaign', '42', '--nm', '100',
            '--query', 'sneakers', '--bid', '500', '--dry-run',
        ])
        assert result.exit_code == 0
        assert 'DRY-RUN' in result.output


# ── Minus phrase tests ───────────────────────────────────────────────


class TestMinusList:
    """Tests for the 'cluster minus list' command."""

    def test_help(self) -> None:
        result = runner.invoke(app, ['cluster', 'minus', 'list', '--help'])
        assert result.exit_code == 0

    @patch(CLUSTER_FACTORY)
    def test_minus_list_json(self, mock_factory: MagicMock) -> None:
        svc = MagicMock()
        svc.get_minus_phrases.return_value = MinusPhraseSet(
            campaign_id=42, nm_id=100, phrases=['boots', 'sandals'],
        )
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'cluster', 'minus', 'list',
            '--campaign', '42', '--nm', '100',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed['phrases'] == ['boots', 'sandals']

    @patch(CLUSTER_FACTORY)
    def test_minus_list_empty(self, mock_factory: MagicMock) -> None:
        svc = MagicMock()
        svc.get_minus_phrases.return_value = MinusPhraseSet(
            campaign_id=42, nm_id=100, phrases=[],
        )
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'cluster', 'minus', 'list',
            '--campaign', '42', '--nm', '100',
        ])
        assert result.exit_code == 0
        assert 'No minus phrases' in result.output


class TestMinusSet:
    """Tests for the 'cluster minus set' command."""

    @patch(CLUSTER_FACTORY)
    def test_minus_set_with_yes(self, mock_factory: MagicMock, mock_audit) -> None:
        svc = MagicMock()
        svc.set_minus_phrases.return_value = _ok_result()
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'cluster', 'minus', 'set',
            '--campaign', '42', '--nm', '100',
            '--phrases', 'boots,sandals', '--yes',
        ])
        assert result.exit_code == 0
        svc.set_minus_phrases.assert_called_once()

    @patch(CLUSTER_FACTORY)
    def test_minus_set_dry_run(self, mock_factory: MagicMock, mock_audit) -> None:
        svc = MagicMock()
        svc.set_minus_phrases.return_value = _dry_result()
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'cluster', 'minus', 'set',
            '--campaign', '42', '--nm', '100',
            '--phrases', 'boots', '--dry-run',
        ])
        assert result.exit_code == 0
        assert 'DRY-RUN' in result.output


class TestMinusClear:
    """Tests for the 'cluster minus clear' command."""

    @patch(CLUSTER_FACTORY)
    def test_minus_clear_with_yes(self, mock_factory: MagicMock, mock_audit) -> None:
        svc = MagicMock()
        svc.clear_minus_phrases.return_value = _ok_result()
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'cluster', 'minus', 'clear',
            '--campaign', '42', '--nm', '100', '--yes',
        ])
        assert result.exit_code == 0
        svc.clear_minus_phrases.assert_called_once()

    @patch(CLUSTER_FACTORY)
    def test_minus_clear_dry_run(self, mock_factory: MagicMock, mock_audit) -> None:
        svc = MagicMock()
        svc.clear_minus_phrases.return_value = _dry_result()
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            'cluster', 'minus', 'clear',
            '--campaign', '42', '--nm', '100', '--dry-run',
        ])
        assert result.exit_code == 0
        assert 'DRY-RUN' in result.output
