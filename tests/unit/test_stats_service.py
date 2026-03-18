"""Tests for wb.services.stats.StatsService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wb.core.exceptions import ValidationError
from wb.domain.models import CampaignStats, ClusterStats
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

RAW_CLUSTER_STATS: list[dict] = [
    {
        'id': 1,
        'keyword': 'sneakers',
        'views': 2000,
        'clicks': 100,
        'ctr': 5.0,
        'orders': 5,
        'sum': 30000,
    },
    {
        'id': 2,
        'keyword': 'running shoes',
        'views': 1500,
        'clicks': 75,
        'ctr': 5.0,
        'orders': 3,
        'sum': 22500,
    },
]


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
        assert result.cpm == 15000.0
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


class TestGetClusterStats:
    """Tests for StatsService.get_cluster_stats."""

    def test_returns_cluster_stats_from_words(
        self, service: StatsService, mock_client: MagicMock,
    ) -> None:
        """get_cluster_stats returns list of ClusterStats from words response."""
        mock_client.get_cluster_stats.return_value = {
            'words': RAW_CLUSTER_STATS,
        }

        result = service.get_cluster_stats(100)

        assert len(result) == 2
        assert all(isinstance(s, ClusterStats) for s in result)
        assert result[0].cluster_id == 1
        assert result[0].cluster_name == 'sneakers'
        assert result[0].views == 2000
        assert result[0].spend == 30000
        assert result[1].cluster_id == 2
        assert result[1].cluster_name == 'running shoes'
        mock_client.get_cluster_stats.assert_called_once_with(100)

    def test_empty_words_returns_empty_list(
        self, service: StatsService, mock_client: MagicMock,
    ) -> None:
        """get_cluster_stats returns empty list when words key is empty."""
        mock_client.get_cluster_stats.return_value = {'words': []}

        result = service.get_cluster_stats(100)

        assert result == []
