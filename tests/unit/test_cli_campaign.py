"""Tests for campaign CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.domain.enums import CampaignStatus, CampaignType, PaymentType
from wb.domain.models import Campaign

runner = CliRunner()

FACTORY_PATH = 'wb.services._factory.create_campaign_service'


def _make_campaign(
        campaign_id: int = 100,
        name: str = 'Test',
) -> Campaign:
    """Create a Campaign instance for testing."""
    return Campaign(
        campaign_id=campaign_id,
        name=name,
        status=CampaignStatus.RUNNING,
        campaign_type=CampaignType.STANDARD,
        payment_type=PaymentType.CPM,
        daily_budget=5000,
        create_time='2026-03-01',
    )


@pytest.fixture()
def mock_svc() -> MagicMock:
    """Return a MagicMock pretending to be CampaignService."""
    return MagicMock()


class TestCampaignList:
    """Tests for the 'campaign list' command."""

    def test_campaign_list_help(self) -> None:
        """Help flag exits cleanly with usage information."""
        result = runner.invoke(app, ['campaign', 'list', '--help'])
        assert result.exit_code == 0
        assert 'List all campaigns' in result.output

    @patch(FACTORY_PATH)
    def test_campaign_list_json(self, mock_factory: MagicMock) -> None:
        """JSON output contains campaign data when one campaign exists."""
        svc = MagicMock()
        svc.list_campaigns.return_value = [_make_campaign()]
        mock_factory.return_value = svc

        result = runner.invoke(app, ['--json', 'campaign', 'list'])
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]['campaign_id'] == 100
        assert parsed[0]['name'] == 'Test'

    @patch(FACTORY_PATH)
    def test_campaign_list_empty(self, mock_factory: MagicMock) -> None:
        """Empty campaign list shows success message."""
        svc = MagicMock()
        svc.list_campaigns.return_value = []
        mock_factory.return_value = svc

        result = runner.invoke(app, ['--json', 'campaign', 'list'])
        assert result.exit_code == 0
        assert 'No campaigns found' in result.output


class TestCampaignGet:
    """Tests for the 'campaign get' command."""

    @patch(FACTORY_PATH)
    def test_campaign_get_success(self, mock_factory: MagicMock) -> None:
        """Get command returns campaign details for a valid ID."""
        svc = MagicMock()
        svc.get_campaign.return_value = _make_campaign(campaign_id=100)
        mock_factory.return_value = svc

        result = runner.invoke(app, ['campaign', 'get', '100'])
        assert result.exit_code == 0

    @patch(FACTORY_PATH)
    def test_campaign_get_json(self, mock_factory: MagicMock) -> None:
        """JSON output contains full campaign detail."""
        svc = MagicMock()
        svc.get_campaign.return_value = _make_campaign(campaign_id=100)
        mock_factory.return_value = svc

        result = runner.invoke(app, ['--json', 'campaign', 'get', '100'])
        assert result.exit_code == 0

        parsed = json.loads(result.output)
        assert parsed['campaign_id'] == 100
        assert parsed['status'] == CampaignStatus.RUNNING


class TestCampaignEligible:
    """Tests for eligible-subjects and eligible-items commands."""

    def test_eligible_subjects_help(self) -> None:
        """Help flag for eligible-subjects exits cleanly."""
        result = runner.invoke(app, ['campaign', 'eligible-subjects', '--help'])
        assert result.exit_code == 0
        assert 'eligible' in result.output.lower()

    def test_eligible_items_requires_subject(self) -> None:
        """Eligible-items fails when --subject is not provided."""
        result = runner.invoke(app, ['campaign', 'eligible-items'])
        assert result.exit_code != 0
