"""Tests for stats CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.domain.models import CampaignStats

runner = CliRunner()

FACTORY_PATH = 'wb.services._factory.create_stats_service'


def _make_stats(campaign_id: int = 100) -> CampaignStats:
    """Create a CampaignStats instance for testing."""
    return CampaignStats(
        campaign_id=campaign_id,
        views=10000,
        clicks=500,
        ctr=5.0,
        orders=50,
        spend=25000,
    )


@pytest.fixture()
def mock_svc() -> MagicMock:
    """Return a MagicMock pretending to be StatsService."""
    return MagicMock()


class TestStatsCampaign:
    """Tests for the 'stats campaign' command."""

    def test_stats_campaign_help(self) -> None:
        """Help flag exits cleanly with usage information."""
        result = runner.invoke(app, ['stats', 'campaign', '--help'])
        assert result.exit_code == 0
        assert 'statistics' in result.output.lower() or 'campaign' in result.output.lower()

    @patch(FACTORY_PATH)
    def test_stats_campaign_json(self, mock_factory: MagicMock) -> None:
        """JSON output contains campaign statistics data."""
        svc = MagicMock()
        svc.get_campaign_stats.return_value = _make_stats()
        mock_factory.return_value = svc

        result = runner.invoke(
            app,
            [
                '--json', 'stats', 'campaign',
                '--id', '100',
                '--from', '2026-03-01',
                '--to', '2026-03-15',
            ],
        )
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert parsed['campaign_id'] == 100
        assert parsed['views'] == 10000
        assert parsed['clicks'] == 500
        assert parsed['ctr'] == 5.0
        assert parsed['orders'] == 50
        assert parsed['spend'] == 25000


class TestStatsCampaigns:
    """Tests for the 'stats campaigns' command."""

    @patch(FACTORY_PATH)
    def test_stats_campaigns_json(self, mock_factory: MagicMock) -> None:
        """JSON output contains a list of campaign statistics."""
        svc = MagicMock()
        svc.get_campaigns_stats.return_value = [
            _make_stats(campaign_id=100),
            _make_stats(campaign_id=200),
        ]
        mock_factory.return_value = svc

        result = runner.invoke(
            app,
            [
                '--json', 'stats', 'campaigns',
                '--ids', '100,200',
                '--from', '2026-03-01',
                '--to', '2026-03-15',
            ],
        )
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed[0]['campaign_id'] == 100
        assert parsed[1]['campaign_id'] == 200

    @patch(FACTORY_PATH)
    def test_stats_campaigns_empty(self, mock_factory: MagicMock) -> None:
        """Empty stats list shows success message."""
        svc = MagicMock()
        svc.get_campaigns_stats.return_value = []
        mock_factory.return_value = svc

        result = runner.invoke(
            app,
            [
                '--json', 'stats', 'campaigns',
                '--ids', '100',
                '--from', '2026-03-01',
                '--to', '2026-03-15',
            ],
        )
        assert result.exit_code == 0
        assert 'No statistics data' in result.output
