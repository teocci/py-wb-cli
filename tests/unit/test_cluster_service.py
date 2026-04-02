"""Tests for wb.services.clusters.ClusterService (normquery API)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wb.domain.models import ClusterStats, MinusPhraseSet, SearchCluster
from wb.services.clusters import ClusterService


@pytest.fixture()
def mock_client() -> MagicMock:
    """Create a mock PromotionClient."""
    return MagicMock()


@pytest.fixture()
def service(mock_client: MagicMock) -> ClusterService:
    """Create a ClusterService with a mocked client."""
    return ClusterService(client=mock_client)


class TestListClusters:
    """Tests for ClusterService.list_clusters."""

    def test_parses_normquery_list_response(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """list_clusters parses active + excluded from normquery/list."""
        mock_client.get_cluster_list.return_value = {
            'items': [{
                'advertId': 100,
                'nmId': 200,
                'normQueries': {
                    'active': ['sneakers', 'boots'],
                    'excluded': ['sandals'],
                },
            }],
        }

        result = service.list_clusters(campaign_id=100, nm_id=200)

        assert len(result) == 3
        assert all(isinstance(c, SearchCluster) for c in result)
        assert result[0].norm_query == 'sneakers'
        assert result[0].is_active is True
        assert result[1].norm_query == 'boots'
        assert result[1].is_active is True
        assert result[2].norm_query == 'sandals'
        assert result[2].is_active is False
        mock_client.get_cluster_list.assert_called_once_with(
            [{'advertId': 100, 'nmId': 200}]
        )

    def test_empty_response(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """list_clusters returns empty list for empty response."""
        mock_client.get_cluster_list.return_value = {'items': []}

        result = service.list_clusters(campaign_id=100, nm_id=200)

        assert result == []

    def test_null_active_and_excluded(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """list_clusters handles null active/excluded arrays."""
        mock_client.get_cluster_list.return_value = {
            'items': [{
                'advertId': 100,
                'nmId': 200,
                'normQueries': {'active': None, 'excluded': None},
            }],
        }

        result = service.list_clusters(campaign_id=100, nm_id=200)

        assert result == []


class TestGetActiveClusters:
    """Tests for ClusterService.get_active_clusters."""

    def test_filters_active_only(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_active_clusters returns only active clusters."""
        mock_client.get_cluster_list.return_value = {
            'items': [{
                'advertId': 100,
                'nmId': 200,
                'normQueries': {
                    'active': ['sneakers'],
                    'excluded': ['boots'],
                },
            }],
        }

        result = service.get_active_clusters(campaign_id=100, nm_id=200)

        assert len(result) == 1
        assert result[0].norm_query == 'sneakers'
        assert result[0].is_active is True


class TestGetInactiveClusters:
    """Tests for ClusterService.get_inactive_clusters."""

    def test_filters_inactive_only(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_inactive_clusters returns only excluded clusters."""
        mock_client.get_cluster_list.return_value = {
            'items': [{
                'advertId': 100,
                'nmId': 200,
                'normQueries': {
                    'active': ['sneakers'],
                    'excluded': ['boots'],
                },
            }],
        }

        result = service.get_inactive_clusters(campaign_id=100, nm_id=200)

        assert len(result) == 1
        assert result[0].norm_query == 'boots'
        assert result[0].is_active is False


class TestGetClusterBids:
    """Tests for ClusterService.get_cluster_bids."""

    def test_parses_bids_response(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_cluster_bids returns clusters from get-bids response."""
        mock_client.get_cluster_bids.return_value = {
            'bids': [
                {'advert_id': 100, 'nm_id': 200, 'norm_query': 'sneakers', 'bid': 500},
                {'advert_id': 100, 'nm_id': 200, 'norm_query': 'boots', 'bid': 300},
            ],
        }

        result = service.get_cluster_bids(campaign_id=100, nm_id=200)

        assert len(result) == 2
        assert result[0].norm_query == 'sneakers'
        assert result[0].bid == 500
        mock_client.get_cluster_bids.assert_called_once_with(
            [{'advert_id': 100, 'nm_id': 200}]
        )

    def test_empty_bids(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_cluster_bids returns empty when no bids."""
        mock_client.get_cluster_bids.return_value = {'bids': []}

        result = service.get_cluster_bids(campaign_id=100, nm_id=200)

        assert result == []


class TestGetClusterStats:
    """Tests for ClusterService.get_cluster_stats."""

    def test_parses_stats_response(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_cluster_stats returns ClusterStats from normquery/stats."""
        mock_client.get_cluster_stats.return_value = {
            'stats': [{
                'advert_id': 100,
                'nm_id': 200,
                'stats': [
                    {
                        'norm_query': 'sneakers',
                        'views': 1000,
                        'clicks': 50,
                        'ctr': 5.0,
                        'orders': 5,
                        'spend': 250,
                        'avg_pos': 3.2,
                    },
                ],
            }],
        }

        result = service.get_cluster_stats(100, 200, '2025-12-01', '2025-12-31')

        assert len(result) == 1
        assert isinstance(result[0], ClusterStats)
        assert result[0].norm_query == 'sneakers'
        assert result[0].views == 1000


class TestGetMinusPhrases:
    """Tests for ClusterService.get_minus_phrases."""

    def test_parses_minus_response(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_minus_phrases returns MinusPhraseSet from get-minus."""
        mock_client.get_minus_phrases.return_value = {
            'items': [{
                'advert_id': 100,
                'nm_id': 200,
                'norm_queries': ['boots', 'sandals'],
            }],
        }

        result = service.get_minus_phrases(campaign_id=100, nm_id=200)

        assert isinstance(result, MinusPhraseSet)
        assert result.campaign_id == 100
        assert result.nm_id == 200
        assert result.phrases == ['boots', 'sandals']

    def test_empty_response(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_minus_phrases returns empty set when no data."""
        mock_client.get_minus_phrases.return_value = {'items': []}

        result = service.get_minus_phrases(campaign_id=100, nm_id=200)

        assert result.phrases == []
