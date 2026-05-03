"""Tests for wb.services.stats.StatsService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wb.core.exceptions import ValidationError
from wb.domain.models import CampaignStats
from wb.services.stats import StatsService


@pytest.fixture()
def mock_client() -> MagicMock:
    """Create a mock PromotionClient."""
    return MagicMock()


@pytest.fixture()
def service(mock_client: MagicMock) -> StatsService:
    """Create a StatsService with a mocked client."""
    return StatsService(client=mock_client)


RAW_CAMPAIGN_STATS: dict = {
    'advertId': 100,
    'views': 5000,
    'clicks': 250,
    'ctr': 5.0,
    'orders': 10,
    'sum': 75000,
    'cpc': 300.0,
    'cpm': 15000.0,
}

class TestGetCampaignStats:
    """Tests for StatsService.get_campaign_stats."""

    def test_returns_campaign_stats(
        self, service: StatsService, mock_client: MagicMock,
    ) -> None:
        """get_campaign_stats returns CampaignStats from API response."""
        mock_client.get_campaign_stats.return_value = [RAW_CAMPAIGN_STATS]

        result = service.get_campaign_stats(100, '2026-03-01', '2026-03-15')

        assert isinstance(result, CampaignStats)
        assert result.campaign_id == 100
        assert result.views == 5000
        assert result.clicks == 250
        assert result.ctr == 5.0
        assert result.orders == 10
        assert result.spend == 75000
        assert result.cpc == 300.0
        assert result.cr == 0.0
        mock_client.get_campaign_stats.assert_called_once_with(
            [100], '2026-03-01', '2026-03-15',
        )

    def test_empty_response_returns_default_stats(
        self, service: StatsService, mock_client: MagicMock,
    ) -> None:
        """get_campaign_stats with empty response returns default-valued CampaignStats."""
        mock_client.get_campaign_stats.return_value = []

        result = service.get_campaign_stats(100, '2026-03-01', '2026-03-15')

        assert isinstance(result, CampaignStats)
        assert result.campaign_id == 100
        assert result.views == 0
        assert result.clicks == 0
        assert result.spend == 0

    def test_invalid_date_raises_validation_error(
        self, service: StatsService, mock_client: MagicMock,
    ) -> None:
        """get_campaign_stats with invalid date format raises ValidationError."""
        with pytest.raises(ValidationError, match='YYYY-MM-DD'):
            service.get_campaign_stats(100, 'not-a-date', '2026-03-15')

    def test_invalid_end_date_raises_validation_error(
        self, service: StatsService, mock_client: MagicMock,
    ) -> None:
        """get_campaign_stats with invalid end date raises ValidationError."""
        with pytest.raises(ValidationError, match='YYYY-MM-DD'):
            service.get_campaign_stats(100, '2026-03-01', '15/03/2026')


class TestGetCampaignsStats:
    """Tests for StatsService.get_campaigns_stats."""

    def test_returns_list_of_stats(
        self, service: StatsService, mock_client: MagicMock,
    ) -> None:
        """get_campaigns_stats returns a list of CampaignStats."""
        second_stats = {**RAW_CAMPAIGN_STATS, 'advertId': 200}
        mock_client.get_campaign_stats.return_value = [
            RAW_CAMPAIGN_STATS, second_stats,
        ]

        result = service.get_campaigns_stats(
            [100, 200], '2026-03-01', '2026-03-15',
        )

        assert len(result) == 2
        assert all(isinstance(s, CampaignStats) for s in result)
        assert result[0].campaign_id == 100
        assert result[1].campaign_id == 200
        mock_client.get_campaign_stats.assert_called_once_with(
            [100, 200], '2026-03-01', '2026-03-15',
        )

    def test_returns_empty_list(
        self, service: StatsService, mock_client: MagicMock,
    ) -> None:
        """get_campaigns_stats returns empty list when API returns no data."""
        mock_client.get_campaign_stats.return_value = []

        result = service.get_campaigns_stats(
            [100], '2026-03-01', '2026-03-15',
        )

        assert result == []


class TestProductSpendStatusFilter:
    """Tests for status-filter branch in get_product_spend / _find_campaign_ids_for_nms."""

    _NM = 111111

    def _make_campaign(self, cid: int, status: int) -> dict:
        return {
            'id': cid,
            'status': status,
            'nm_settings': [{'nm_id': self._NM}],
        }

    def test_stopped_campaign_excluded_from_fullstats(
        self, service: StatsService, mock_client: MagicMock,
    ) -> None:
        """get_product_spend only sends running (9) and paused (11) campaigns to fullstats.

        A stopped campaign (status 7) sharing the same NM IDs must not be
        included — it contributes no spend and wastes a fullstats rate-limit
        slot on Base tokens.
        """
        running_id = 10
        paused_id = 11
        stopped_id = 99

        mock_client.list_campaigns.return_value = [
            self._make_campaign(running_id, 9),
            self._make_campaign(paused_id, 11),
            self._make_campaign(stopped_id, 7),
        ]
        mock_client.get_campaign_stats.return_value = []

        service.get_product_spend([self._NM], '2026-01-01', '2026-01-01')

        called_ids = mock_client.get_campaign_stats.call_args[0][0]
        assert stopped_id not in called_ids
        assert running_id in called_ids
        assert paused_id in called_ids

    def test_only_stopped_campaigns_returns_zeros(
        self, service: StatsService, mock_client: MagicMock,
    ) -> None:
        """get_product_spend returns zero-spend NmStats when all matching campaigns are stopped."""
        mock_client.list_campaigns.return_value = [
            self._make_campaign(99, 7),
        ]

        result = service.get_product_spend([self._NM], '2026-01-01', '2026-01-01')

        mock_client.get_campaign_stats.assert_not_called()
        assert len(result) == 1
        assert result[0].nm_id == self._NM
        assert result[0].spend == 0


