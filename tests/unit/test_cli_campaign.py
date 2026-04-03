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


class TestCampaignClone:
    """Tests for the 'campaign clone' command."""

    def test_campaign_clone_help(self) -> None:
        """Help flag exits cleanly with usage information."""
        result = runner.invoke(app, ['campaign', 'clone', '--help'])
        assert result.exit_code == 0
        assert 'clone' in result.output.lower()

    @patch(FACTORY_PATH)
    def test_campaign_clone_requires_nms(self, mock_factory: MagicMock) -> None:
        """Clone command fails when --nms is not provided."""
        svc = MagicMock()
        svc.get_campaign.return_value = _make_campaign()
        mock_factory.return_value = svc

        result = runner.invoke(app, ['campaign', 'clone', '100', '--yes'])
        assert result.exit_code != 0
        assert '--nms is required' in result.output

    @patch(FACTORY_PATH)
    def test_campaign_clone_success(self, mock_factory: MagicMock) -> None:
        """Clone command creates a copy with default name."""
        from wb.domain.models import MutationResult

        svc = MagicMock()
        svc.get_campaign.return_value = _make_campaign(campaign_id=100, name='Original')
        svc.create_campaign.return_value = MutationResult(
            success=True,
            action='create',
            target_id='200',
            message='Campaign 200 created',
        )
        mock_factory.return_value = svc

        result = runner.invoke(
            app,
            ['campaign', 'clone', '100', '--nms', '10,20', '--yes'],
        )
        assert result.exit_code == 0
        assert 'created' in result.output.lower()

    @patch(FACTORY_PATH)
    def test_campaign_clone_custom_name(self, mock_factory: MagicMock) -> None:
        """Clone command uses custom name when provided."""
        from wb.domain.models import MutationResult

        svc = MagicMock()
        svc.get_campaign.return_value = _make_campaign(campaign_id=100, name='Original')
        svc.create_campaign.return_value = MutationResult(
            success=True,
            action='create',
            target_id='200',
            message='Campaign 200 created',
        )
        mock_factory.return_value = svc

        result = runner.invoke(
            app,
            ['campaign', 'clone', '100', '--name', 'MyClone', '--nms', '10,20', '--yes'],
        )
        assert result.exit_code == 0
        # Verify get_campaign was called
        svc.get_campaign.assert_called_once_with(100)
        # Verify create_campaign was called with correct params
        create_call = svc.create_campaign.call_args
        params = create_call[0][0]
        assert params.name == 'MyClone'
        assert params.nm_ids == [10, 20]

    @patch(FACTORY_PATH)
    def test_campaign_clone_dry_run(self, mock_factory: MagicMock) -> None:
        """Clone command respects --dry-run flag."""
        from wb.domain.models import MutationResult

        svc = MagicMock()
        svc.get_campaign.return_value = _make_campaign()
        svc.create_campaign.return_value = MutationResult(
            success=True,
            action='create',
            target_id='200',
            message='Campaign 200 created',
            dry_run=True,
        )
        mock_factory.return_value = svc

        result = runner.invoke(
            app,
            ['campaign', 'clone', '100', '--nms', '10', '--dry-run'],
        )
        assert result.exit_code == 0
        assert 'DRY-RUN' in result.output


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
