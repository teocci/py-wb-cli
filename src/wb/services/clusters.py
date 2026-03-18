"""Search cluster use-cases."""

from __future__ import annotations

from wb.client.promotion import PromotionClient
from wb.domain.models import SearchCluster

__all__ = ['ClusterService']


class ClusterService:
    """Orchestrates search cluster read operations.

    Attributes:
        client: Promotion API client.
    """

    def __init__(self, client: PromotionClient) -> None:
        self._client = client

    def list_clusters(self, campaign_id: int) -> list[SearchCluster]:
        """List all clusters for a campaign.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            List of SearchCluster domain objects.
        """
        raw = self._client.get_all_clusters(campaign_id)
        return self._parse_clusters(raw)

    def get_active_clusters(
            self, campaign_id: int,
    ) -> list[SearchCluster]:
        """List active clusters for a campaign.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            List of active SearchCluster domain objects.
        """
        raw = self._client.get_active_clusters(campaign_id)
        words = raw.get('words', [])
        return [
            SearchCluster.from_api(w, is_active=True) for w in words
        ]

    def get_inactive_clusters(
            self, campaign_id: int,
    ) -> list[SearchCluster]:
        """List inactive clusters for a campaign.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            List of inactive SearchCluster domain objects.
        """
        all_clusters = self.list_clusters(campaign_id)
        return [c for c in all_clusters if not c.is_active]

    def get_cluster_bids(
            self, campaign_id: int,
    ) -> list[SearchCluster]:
        """List clusters with non-zero bids for a campaign.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            List of SearchCluster domain objects that have bids set.
        """
        all_clusters = self.list_clusters(campaign_id)
        return [c for c in all_clusters if c.bid > 0]

    def _parse_clusters(self, raw: dict) -> list[SearchCluster]:
        """Parse cluster data from the all-clusters API response.

        Args:
            raw: Raw API response dict.

        Returns:
            List of SearchCluster domain objects.
        """
        result: list[SearchCluster] = []
        for word in raw.get('words', []):
            is_active = word.get('isActive', True)
            result.append(
                SearchCluster.from_api(word, is_active=is_active)
            )
        return result
