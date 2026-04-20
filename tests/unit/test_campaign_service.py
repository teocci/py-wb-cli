"""Tests for wb.services.campaigns.CampaignService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wb.core.exceptions import ValidationError
from wb.domain.enums import CampaignStatus, CampaignType, PaymentType
from wb.domain.models import Campaign, ProductCard
from wb.services.campaigns import CampaignService

RAW_CAMPAIGN: dict = {
    'id': 100,
    'status': 9,
    'bid_type': 'manual',
    'currency': 'RUB',
    'settings': {
        'name': 'Test Campaign',
        'payment_type': 'cpm',
    },
    'timestamps': {
        'created': '2026-03-01T00:00:00',
        'started': None,
        'updated': None,
        'deleted': None,
    },
}


@pytest.fixture()
def mock_client() -> MagicMock:
    """Create a mock PromotionClient."""
    return MagicMock()


@pytest.fixture()
def service(mock_client: MagicMock) -> CampaignService:
    """Create a CampaignService with a mocked client."""
    return CampaignService(client=mock_client)


class TestListCampaigns:
    """Tests for CampaignService.list_campaigns."""

    def test_returns_campaign_objects(
        self, service: CampaignService, mock_client: MagicMock,
    ) -> None:
        """list_campaigns returns list of Campaign domain objects from raw API dicts."""
        mock_client.list_campaigns.return_value = [RAW_CAMPAIGN]

        result = service.list_campaigns()

        assert len(result) == 1
        campaign = result[0]
        assert isinstance(campaign, Campaign)
        assert campaign.campaign_id == 100
        assert campaign.name == 'Test Campaign'
        assert campaign.status == CampaignStatus.RUNNING
        assert campaign.campaign_type == CampaignType.STANDARD
        assert campaign.payment_type == PaymentType.CPM
        assert campaign.create_time == '2026-03-01T00:00:00'
        mock_client.list_campaigns.assert_called_once_with(
            status=None, type_=None,
        )

    def test_with_status_filter(
        self, service: CampaignService, mock_client: MagicMock,
    ) -> None:
        """list_campaigns with status filter passes correct enum value."""
        mock_client.list_campaigns.return_value = [RAW_CAMPAIGN]

        service.list_campaigns(status=CampaignStatus.RUNNING)

        mock_client.list_campaigns.assert_called_once_with(
            status=[9], type_=None,
        )

    def test_returns_empty_list(
        self, service: CampaignService, mock_client: MagicMock,
    ) -> None:
        """list_campaigns returns empty list when API returns no campaigns."""
        mock_client.list_campaigns.return_value = []

        result = service.list_campaigns()

        assert result == []

    @pytest.mark.parametrize('payment_type_value', ['', None])
    def test_empty_payment_type_defaults_to_cpm(
        self,
        service: CampaignService,
        mock_client: MagicMock,
        payment_type_value: str | None,
    ) -> None:
        """Empty or null payment_type from API defaults to CPM without crashing."""
        raw = {**RAW_CAMPAIGN, 'settings': {**RAW_CAMPAIGN['settings'], 'payment_type': payment_type_value}}
        mock_client.list_campaigns.return_value = [raw]

        result = service.list_campaigns()

        assert result[0].payment_type == PaymentType.CPM


class TestGetCampaign:
    """Tests for CampaignService.get_campaign."""

    def test_success(
        self, service: CampaignService, mock_client: MagicMock,
    ) -> None:
        """get_campaign returns Campaign for a valid ID."""
        mock_client.get_campaign.return_value = RAW_CAMPAIGN

        result = service.get_campaign(100)

        assert isinstance(result, Campaign)
        assert result.campaign_id == 100
        assert result.name == 'Test Campaign'
        mock_client.get_campaign.assert_called_once_with(100)

    def test_not_found_raises_validation_error(
        self, service: CampaignService, mock_client: MagicMock,
    ) -> None:
        """get_campaign raises ValidationError when campaign not found."""
        mock_client.get_campaign.return_value = None

        with pytest.raises(ValidationError, match='Campaign 999 not found'):
            service.get_campaign(999)


class TestGetEligibleSubjects:
    """Tests for CampaignService.get_eligible_subjects."""

    def test_returns_raw_subject_list(
        self, service: CampaignService, mock_client: MagicMock,
    ) -> None:
        """get_eligible_subjects returns raw subject list from the client."""
        subjects = [
            {'id': 1, 'name': 'Electronics'},
            {'id': 2, 'name': 'Clothing'},
        ]
        mock_client.get_eligible_subjects.return_value = subjects

        result = service.get_eligible_subjects()

        assert result == subjects
        mock_client.get_eligible_subjects.assert_called_once()


class TestGetEligibleItems:
    """Tests for CampaignService.get_eligible_items."""

    def test_returns_product_cards(
        self, service: CampaignService, mock_client: MagicMock,
    ) -> None:
        """get_eligible_items returns list of ProductCard domain objects."""
        raw_items = [
            {'nmId': 10, 'name': 'Widget', 'subjectId': 1, 'subjectName': 'Electronics'},
            {'nmId': 20, 'name': 'Gadget', 'subjectId': 2, 'subjectName': 'Clothing'},
        ]
        mock_client.get_eligible_items.return_value = raw_items

        result = service.get_eligible_items(subject_id=1)

        assert len(result) == 2
        assert all(isinstance(item, ProductCard) for item in result)
        assert result[0].nm_id == 10
        assert result[0].name == 'Widget'
        assert result[1].nm_id == 20
        mock_client.get_eligible_items.assert_called_once_with([1])
