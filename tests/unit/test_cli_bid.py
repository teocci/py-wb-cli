"""Tests for bid CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.domain.models import RecommendedBid

runner = CliRunner()

FACTORY_PATH = 'wb.services._factory.create_bid_service'


def _make_recommended_bid(
        campaign_id: int = 42,
        nm_id: int = 555,
) -> RecommendedBid:
    """Create a RecommendedBid instance for testing."""
    return RecommendedBid(
        campaign_id=campaign_id,
        nm_id=nm_id,
        recommended=300,
        minimum=100,
    )


@pytest.fixture()
def mock_svc() -> MagicMock:
    """Return a MagicMock pretending to be BidService."""
    return MagicMock()


class TestBidRecommend:
    """Tests for the 'bid recommend' command."""

    def test_bid_recommend_help(self) -> None:
        """Help flag exits cleanly with usage information."""
        result = runner.invoke(app, ['bid', 'recommend', '--help'])
        assert result.exit_code == 0
        assert 'recommended' in result.output.lower()

    @patch(FACTORY_PATH)
    def test_bid_recommend_json(self, mock_factory: MagicMock) -> None:
        """JSON output contains recommended bid data."""
        svc = MagicMock()
        svc.get_recommended_bids.return_value = [_make_recommended_bid()]
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['--json', 'bid', 'recommend', '--campaign', '42'],
        )
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]['nm_id'] == 555
        assert parsed[0]['recommended'] == 300

    @patch(FACTORY_PATH)
    def test_bid_recommend_empty(self, mock_factory: MagicMock) -> None:
        """Empty recommendations show success message."""
        svc = MagicMock()
        svc.get_recommended_bids.return_value = []
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['--json', 'bid', 'recommend', '--campaign', '42'],
        )
        assert result.exit_code == 0
        assert 'No bid recommendations' in result.output


class TestBidMinimum:
    """Tests for the 'bid minimum' command."""

    @patch(FACTORY_PATH)
    def test_bid_minimum_json(self, mock_factory: MagicMock) -> None:
        """JSON output contains minimum bid data."""
        svc = MagicMock()
        svc.get_minimum_bids.return_value = [_make_recommended_bid()]
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['--json', 'bid', 'minimum', '--campaign', '42'],
        )
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]['minimum'] == 100


class TestBidGetItems:
    """Tests for the 'bid get-items' command."""

    @patch(FACTORY_PATH)
    def test_bid_get_items_json(self, mock_factory: MagicMock) -> None:
        """JSON output contains per-item bid data."""
        svc = MagicMock()
        svc.get_item_bids.return_value = [_make_recommended_bid()]
        mock_factory.return_value = svc

        result = runner.invoke(
            app, ['--json', 'bid', 'get-items', '--campaign', '42'],
        )
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]['nm_id'] == 555
        assert parsed[0]['recommended'] == 300
