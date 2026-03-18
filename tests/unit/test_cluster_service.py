"""Tests for wb.services.clusters.ClusterService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wb.domain.models import SearchCluster
from wb.services.clusters import ClusterService


RAW_CLUSTER_ACTIVE: dict = {
    'id': 1,
    'keyword': 'sneakers',
    'count': 120,
    'isActive': True,
    'bid': 500,
    'recommendedBid': 700,
}

RAW_CLUSTER_INACTIVE: dict = {
    'id': 2,
    'keyword': 'boots',
    'count': 80,
    'isActive': False,
    'bid': 0,
    'recommendedBid': 400,
}

RAW_CLUSTER_WITH_BID: dict = {
    'id': 3,
    'keyword': 'loafers',
    'count': 50,
    'isActive': True,
    'bid': 300,
    'recommendedBid': 500,
}


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

    def test_parses_words_with_is_active(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """list_clusters parses words list and respects isActive field."""
        mock_client.get_all_clusters.return_value = {
            'words': [RAW_CLUSTER_ACTIVE, RAW_CLUSTER_INACTIVE],
        }

        result = service.list_clusters(campaign_id=100)

        assert len(result) == 2
        assert all(isinstance(c, SearchCluster) for c in result)
        assert result[0].cluster_id == 1
        assert result[0].cluster_name == 'sneakers'
        assert result[0].is_active is True
        assert result[0].bid == 500
        assert result[1].cluster_id == 2
        assert result[1].is_active is False
        mock_client.get_all_clusters.assert_called_once_with(100)

    def test_empty_response(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """list_clusters returns empty list for empty response."""
        mock_client.get_all_clusters.return_value = {'words': []}

        result = service.list_clusters(campaign_id=100)

        assert result == []


class TestGetActiveClusters:
    """Tests for ClusterService.get_active_clusters."""

    def test_returns_active_clusters(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_active_clusters returns clusters from active-words response."""
        mock_client.get_active_clusters.return_value = {
            'words': [
                {'id': 1, 'keyword': 'sneakers', 'count': 120, 'bid': 500, 'recommendedBid': 700},
            ],
        }

        result = service.get_active_clusters(campaign_id=100)

        assert len(result) == 1
        assert result[0].is_active is True
        assert result[0].cluster_name == 'sneakers'
        mock_client.get_active_clusters.assert_called_once_with(100)

    def test_empty_response(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_active_clusters returns empty list when no active clusters."""
        mock_client.get_active_clusters.return_value = {'words': []}

        result = service.get_active_clusters(campaign_id=100)

        assert result == []


class TestGetInactiveClusters:
    """Tests for ClusterService.get_inactive_clusters."""

    def test_filters_inactive_from_all_clusters(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_inactive_clusters returns only inactive clusters."""
        mock_client.get_all_clusters.return_value = {
            'words': [RAW_CLUSTER_ACTIVE, RAW_CLUSTER_INACTIVE],
        }

        result = service.get_inactive_clusters(campaign_id=100)

        assert len(result) == 1
        assert result[0].cluster_id == 2
        assert result[0].is_active is False

    def test_empty_when_all_active(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_inactive_clusters returns empty when all clusters are active."""
        mock_client.get_all_clusters.return_value = {
            'words': [RAW_CLUSTER_ACTIVE],
        }

        result = service.get_inactive_clusters(campaign_id=100)

        assert result == []


class TestGetClusterBids:
    """Tests for ClusterService.get_cluster_bids."""

    def test_filters_clusters_with_bid(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_cluster_bids returns only clusters with bid > 0."""
        mock_client.get_all_clusters.return_value = {
            'words': [
                RAW_CLUSTER_ACTIVE,
                RAW_CLUSTER_INACTIVE,
                RAW_CLUSTER_WITH_BID,
            ],
        }

        result = service.get_cluster_bids(campaign_id=100)

        assert len(result) == 2
        bid_ids = {c.cluster_id for c in result}
        assert bid_ids == {1, 3}
        assert all(c.bid > 0 for c in result)

    def test_empty_when_no_bids(
        self, service: ClusterService, mock_client: MagicMock,
    ) -> None:
        """get_cluster_bids returns empty when no clusters have bids."""
        mock_client.get_all_clusters.return_value = {
            'words': [RAW_CLUSTER_INACTIVE],
        }

        result = service.get_cluster_bids(campaign_id=100)

        assert result == []
