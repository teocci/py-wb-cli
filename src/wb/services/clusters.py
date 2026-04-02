"""Search cluster use-cases using normquery API."""

from __future__ import annotations

from wb.client.promotion import PromotionClient
from wb.domain.models import ClusterStats, MinusPhraseSet, SearchCluster

__all__ = ['ClusterService']


class ClusterService:
    """Orchestrates search cluster read operations via normquery API.

    All methods require both campaign_id and nm_id because
    the normquery API is scoped to (campaign, product) pairs.

    Attributes:
        client: Promotion API client.
    """

    def __init__(self, client: PromotionClient) -> None:
        self._client = client

    def list_clusters(
            self, campaign_id: int, nm_id: int,
    ) -> list[SearchCluster]:
        """List all clusters (active + excluded) for a campaign/product.

        Args:
            campaign_id: Target campaign identifier.
            nm_id: Product nomenclature ID.

        Returns:
            List of SearchCluster domain objects.
        """
        raw = self._client.get_cluster_list(
            [{'advertId': campaign_id, 'nmId': nm_id}]
        )
        return self._parse_normquery_list(raw)

    def get_active_clusters(
            self, campaign_id: int, nm_id: int,
    ) -> list[SearchCluster]:
        """List active clusters for a campaign/product.

        Args:
            campaign_id: Target campaign identifier.
            nm_id: Product nomenclature ID.

        Returns:
            List of active SearchCluster domain objects.
        """
        clusters = self.list_clusters(campaign_id, nm_id)
        return [c for c in clusters if c.is_active]

    def get_inactive_clusters(
            self, campaign_id: int, nm_id: int,
    ) -> list[SearchCluster]:
        """List inactive (excluded) clusters for a campaign/product.

        Args:
            campaign_id: Target campaign identifier.
            nm_id: Product nomenclature ID.

        Returns:
            List of inactive SearchCluster domain objects.
        """
        clusters = self.list_clusters(campaign_id, nm_id)
        return [c for c in clusters if not c.is_active]

    def get_cluster_bids(
            self, campaign_id: int, nm_id: int,
    ) -> list[SearchCluster]:
        """List clusters with bids set for a campaign/product.

        Args:
            campaign_id: Target campaign identifier.
            nm_id: Product nomenclature ID.

        Returns:
            List of SearchCluster domain objects that have bids.
        """
        raw = self._client.get_cluster_bids(
            [{'advert_id': campaign_id, 'nm_id': nm_id}]
        )
        bids = raw.get('bids', [])
        return [SearchCluster.from_bid_api(b) for b in bids]

    def get_cluster_stats(
            self,
            campaign_id: int,
            nm_id: int,
            date_from: str,
            date_to: str,
    ) -> list[ClusterStats]:
        """Retrieve aggregated cluster stats for a campaign/product.

        Args:
            campaign_id: Target campaign identifier.
            nm_id: Product nomenclature ID.
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).

        Returns:
            List of ClusterStats domain objects.
        """
        raw = self._client.get_cluster_stats(
            date_from, date_to,
            [{'advert_id': campaign_id, 'nm_id': nm_id}],
        )
        return self._parse_cluster_stats(raw)

    def get_minus_phrases(
            self, campaign_id: int, nm_id: int,
    ) -> MinusPhraseSet:
        """Retrieve minus phrases for a campaign/product.

        Args:
            campaign_id: Target campaign identifier.
            nm_id: Product nomenclature ID.

        Returns:
            MinusPhraseSet with the current minus phrases.
        """
        raw = self._client.get_minus_phrases(
            [{'advert_id': campaign_id, 'nm_id': nm_id}]
        )
        items = raw.get('items', [])
        if items:
            return MinusPhraseSet.from_api(items[0])
        return MinusPhraseSet(
            campaign_id=campaign_id, nm_id=nm_id,
        )

    def _parse_normquery_list(self, raw: dict) -> list[SearchCluster]:
        """Parse normquery/list response into SearchCluster objects.

        Args:
            raw: Raw API response dict.

        Returns:
            Combined list of active + excluded clusters.
        """
        result: list[SearchCluster] = []
        for item in raw.get('items', []):
            nq = item.get('normQueries', {}) or {}
            for phrase in (nq.get('active') or []):
                result.append(
                    SearchCluster.from_normquery_list(phrase, is_active=True)
                )
            for phrase in (nq.get('excluded') or []):
                result.append(
                    SearchCluster.from_normquery_list(phrase, is_active=False)
                )
        return result

    def _parse_cluster_stats(self, raw: dict) -> list[ClusterStats]:
        """Parse normquery/stats response into ClusterStats objects.

        Args:
            raw: Raw API response dict.

        Returns:
            List of ClusterStats domain objects.
        """
        result: list[ClusterStats] = []
        for item in raw.get('stats', []):
            for stat in item.get('stats', []):
                result.append(ClusterStats.from_api(stat))
        return result
