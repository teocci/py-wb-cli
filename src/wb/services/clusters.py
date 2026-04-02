"""Search cluster use-cases using normquery API."""

from __future__ import annotations

from wb.client.promotion import PromotionClient
from wb.core.exceptions import ValidationError
from wb.domain.models import (
    ClusterBidMutation,
    ClusterStats,
    MinusPhraseSet,
    MutationResult,
    SearchCluster,
)

__all__ = ['ClusterService']

_MAX_BIDS_PER_REQUEST = 100
_MAX_MINUS_PHRASES = 1000


class ClusterService:
    """Orchestrates search cluster operations via normquery API.

    All methods require both campaign_id and nm_id because
    the normquery API is scoped to (campaign, product) pairs.

    Attributes:
        client: Promotion API client.
    """

    def __init__(self, client: PromotionClient) -> None:
        self._client = client

    # ── Read operations ──────────────────────────────────────────────

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

    def get_cluster_stats_daily(
            self,
            campaign_id: int,
            nm_id: int,
            date_from: str,
            date_to: str,
    ) -> list[dict]:
        """Retrieve daily cluster stats for a campaign/product.

        Args:
            campaign_id: Target campaign identifier.
            nm_id: Product nomenclature ID.
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).

        Returns:
            List of daily stat dicts with date and stat fields.
        """
        raw = self._client.get_cluster_stats_daily(
            date_from, date_to,
            [{'advertId': campaign_id, 'nmId': nm_id}],
        )
        result: list[dict] = []
        for item in raw.get('items', []):
            for daily in item.get('dailyStats', []):
                result.append(daily)
        return result

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

    # ── Write operations ─────────────────────────────────────────────

    def set_cluster_bids(
            self,
            campaign_id: int,
            mutations: list[ClusterBidMutation],
            dry_run: bool = False,
    ) -> MutationResult:
        """Set bids for one or more search clusters.

        Args:
            campaign_id: Target campaign identifier.
            mutations: List of cluster bid mutations (max 100).
            dry_run: If True, plan without executing.

        Returns:
            MutationResult describing the outcome.

        Raises:
            ValidationError: If mutations list is empty, exceeds 100,
                            or any bid is not positive.
        """
        self._validate_bid_mutations(mutations)
        count = len(mutations)
        action = f'set {count} cluster bid(s) in campaign {campaign_id}'

        if dry_run:
            return MutationResult(
                success=True, action=action,
                target_id=str(campaign_id), dry_run=True,
                message=f'Would set {count} cluster bid(s)',
            )

        payloads = [m.to_api(campaign_id) for m in mutations]
        self._client.set_cluster_bids(payloads)
        return MutationResult(
            success=True, action=action,
            target_id=str(campaign_id),
            message=f'Set {count} cluster bid(s)',
        )

    def delete_cluster_bids(
            self,
            campaign_id: int,
            mutations: list[ClusterBidMutation],
            dry_run: bool = False,
    ) -> MutationResult:
        """Delete bids from one or more search clusters.

        Args:
            campaign_id: Target campaign identifier.
            mutations: List of cluster bid mutations to delete (max 100).
            dry_run: If True, plan without executing.

        Returns:
            MutationResult describing the outcome.

        Raises:
            ValidationError: If mutations list is empty or exceeds 100.
        """
        if not mutations:
            raise ValidationError(
                'At least one bid mutation is required'
            )
        if len(mutations) > _MAX_BIDS_PER_REQUEST:
            raise ValidationError(
                f'Maximum {_MAX_BIDS_PER_REQUEST} bids per request, '
                f'got {len(mutations)}'
            )

        count = len(mutations)
        action = (
            f'delete {count} cluster bid(s) '
            f'from campaign {campaign_id}'
        )

        if dry_run:
            return MutationResult(
                success=True, action=action,
                target_id=str(campaign_id), dry_run=True,
                message=f'Would delete {count} cluster bid(s)',
            )

        payloads = [m.to_api(campaign_id) for m in mutations]
        self._client.delete_cluster_bids(payloads)
        return MutationResult(
            success=True, action=action,
            target_id=str(campaign_id),
            message=f'Deleted {count} cluster bid(s)',
        )

    def set_minus_phrases(
            self,
            campaign_id: int,
            nm_id: int,
            phrases: list[str],
            dry_run: bool = False,
    ) -> MutationResult:
        """Set minus phrases for a campaign/product pair.

        Args:
            campaign_id: Target campaign identifier.
            nm_id: Product nomenclature ID.
            phrases: Phrases to exclude (max 1000). Empty list clears all.
            dry_run: If True, plan without executing.

        Returns:
            MutationResult describing the outcome.

        Raises:
            ValidationError: If phrases exceed 1000.
        """
        if len(phrases) > _MAX_MINUS_PHRASES:
            raise ValidationError(
                f'Maximum {_MAX_MINUS_PHRASES} minus phrases, '
                f'got {len(phrases)}'
            )

        action_verb = 'clear' if not phrases else f'set {len(phrases)}'
        action = (
            f'{action_verb} minus phrase(s) for '
            f'campaign {campaign_id} nm {nm_id}'
        )

        if dry_run:
            return MutationResult(
                success=True, action=action,
                target_id=str(campaign_id), dry_run=True,
                message=f'Would {action_verb} minus phrase(s)',
            )

        payload = MinusPhraseSet(
            campaign_id=campaign_id, nm_id=nm_id, phrases=phrases,
        ).to_api()
        self._client.set_minus_phrases(payload)
        return MutationResult(
            success=True, action=action,
            target_id=str(campaign_id),
            message=f'{action_verb.capitalize()} minus phrase(s)',
        )

    def clear_minus_phrases(
            self,
            campaign_id: int,
            nm_id: int,
            dry_run: bool = False,
    ) -> MutationResult:
        """Clear all minus phrases for a campaign/product pair.

        Args:
            campaign_id: Target campaign identifier.
            nm_id: Product nomenclature ID.
            dry_run: If True, plan without executing.

        Returns:
            MutationResult describing the outcome.
        """
        return self.set_minus_phrases(
            campaign_id, nm_id, [], dry_run=dry_run,
        )

    # ── Private helpers ──────────────────────────────────────────────

    def _validate_bid_mutations(
            self, mutations: list[ClusterBidMutation],
    ) -> None:
        """Validate a list of cluster bid mutations.

        Args:
            mutations: Bid mutations to validate.

        Raises:
            ValidationError: If list is empty, exceeds 100, or has
                            non-positive bids.
        """
        if not mutations:
            raise ValidationError(
                'At least one bid mutation is required'
            )
        if len(mutations) > _MAX_BIDS_PER_REQUEST:
            raise ValidationError(
                f'Maximum {_MAX_BIDS_PER_REQUEST} bids per request, '
                f'got {len(mutations)}'
            )
        for m in mutations:
            if m.bid <= 0:
                raise ValidationError(
                    f'Bid must be positive, got {m.bid} '
                    f'for "{m.norm_query}"'
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
