"""Tests for cluster CLI commands (normquery API)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.domain.models import ClusterStats, SearchCluster

runner = CliRunner()

CLUSTER_FACTORY = 'wb.services._factory.create_cluster_service'


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
