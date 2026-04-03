"""Cache service — orchestrates local snapshot collection and queries.

Snapshot methods pull live data from WB API services and persist it
to the local SQLite cache. All snapshots are explicit (user-triggered).
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import date, timedelta

from wb.domain.cache_models import (
    BudgetEvent,
    CampaignSnapshot,
    ClusterRecord,
    StatsRecord,
)
from wb.storage.cache import CacheStore

__all__ = ['CacheService']

logger = logging.getLogger(__name__)

_STATS_DAYS = 30


class CacheService:
    """Orchestrates snapshot collection and historical queries.

    Attributes:
        store: Local SQLite cache store.
        campaign_svc: Campaign service for API reads.
        stats_svc: Stats service for API reads.
        cluster_svc: Cluster service for API reads.
    """

    def __init__(
            self,
            store: CacheStore,
            campaign_svc,
            stats_svc,
            cluster_svc,
    ) -> None:
        self._store = store
        self._campaign_svc = campaign_svc
        self._stats_svc = stats_svc
        self._cluster_svc = cluster_svc

    # ── Snapshot operations ───────────────────────────────────────────

    def snapshot_campaign(
            self,
            campaign_id: int,
            profile: str,
            *,
            nm_id: int | None = None,
            with_stats: bool = True,
            with_clusters: bool = True,
    ) -> dict[str, int]:
        """Capture current WB API state for one campaign.

        Stores the campaign config snapshot, optionally today's stats
        (30-day window), and optionally cluster bids (requires nm_id).

        Args:
            campaign_id: Target campaign identifier.
            profile: Profile name for labelling stored rows.
            nm_id: Product ID required for cluster snapshots.
            with_stats: Whether to capture campaign stats.
            with_clusters: Whether to capture cluster bids (needs nm_id).

        Returns:
            Dict with counts: {'campaigns': 1, 'stats': N, 'clusters': N}.
        """
        counts: dict[str, int] = {'campaigns': 0, 'stats': 0, 'clusters': 0}
        now = _utc_now()

        campaign = self._campaign_svc.get_campaign(campaign_id)
        snap = _campaign_to_snapshot(campaign, profile, now)
        self._store.save_campaign(snap)
        counts['campaigns'] = 1

        if with_stats:
            counts['stats'] = self._snapshot_stats(campaign_id, profile, now)

        if with_clusters and nm_id is not None:
            counts['clusters'] = self._snapshot_clusters(
                campaign_id, nm_id, profile, now
            )

        return counts

    def snapshot_all(self, profile: str) -> dict[str, int]:
        """Capture configs for all campaigns (no stats, no clusters).

        Args:
            profile: Profile name for labelling stored rows.

        Returns:
            Dict with total counts across all campaigns.
        """
        from wb.domain.enums import CampaignStatus
        campaigns = self._campaign_svc.list_campaigns()
        active = [c for c in campaigns if c.status == CampaignStatus.RUNNING]
        totals: dict[str, int] = {'campaigns': 0, 'stats': 0, 'clusters': 0}
        now = _utc_now()
        for campaign in active:
            snap = _campaign_to_snapshot(campaign, profile, now)
            self._store.save_campaign(snap)
            totals['campaigns'] += 1
        return totals

    def _snapshot_stats(
            self, campaign_id: int, profile: str, now: str,
    ) -> int:
        """Capture today's 30-day aggregated stats for one campaign."""
        today = now[:10]
        thirty_ago = (date.fromisoformat(today) - timedelta(days=_STATS_DAYS)).isoformat()
        try:
            stats = self._stats_svc.get_campaign_stats(
                campaign_id, thirty_ago, today,
            )
        except Exception as exc:
            logger.warning('Could not fetch stats for %s: %s', campaign_id, exc)
            return 0
        rec = StatsRecord(
            campaign_id=campaign_id,
            profile=profile,
            date=today,
            views=stats.views,
            clicks=stats.clicks,
            ctr=stats.ctr,
            spend=int(stats.spend),
            orders=stats.orders,
            payload_json=json.dumps(asdict(stats)),
        )
        self._store.save_stats(rec)
        return 1

    def _snapshot_clusters(
            self,
            campaign_id: int,
            nm_id: int,
            profile: str,
            now: str,
    ) -> int:
        """Capture cluster bids for one (campaign, product) pair."""
        try:
            clusters = self._cluster_svc.list_clusters(campaign_id, nm_id)
        except Exception as exc:
            logger.warning('Could not fetch clusters for %s/%s: %s', campaign_id, nm_id, exc)
            return 0
        for cluster in clusters:
            rec = ClusterRecord(
                campaign_id=campaign_id,
                nm_id=nm_id,
                norm_query=cluster.norm_query,
                profile=profile,
                snapshot_time=now,
                bid=cluster.bid or 0,
            )
            self._store.save_cluster(rec)
        return len(clusters)

    # ── History queries ───────────────────────────────────────────────

    def history_campaigns(
            self,
            profile: str,
            campaign_id: int | None = None,
            limit: int = 50,
    ) -> list[CampaignSnapshot]:
        """Query stored campaign snapshots.

        Args:
            profile: Profile to filter by.
            campaign_id: Optional campaign ID filter.
            limit: Maximum rows to return.

        Returns:
            List of CampaignSnapshot ordered by snapshot_time desc.
        """
        return self._store.list_campaigns(profile, campaign_id, limit)

    def history_stats(
            self,
            profile: str,
            campaign_id: int,
            date_from: str | None = None,
            date_to: str | None = None,
            limit: int = 90,
    ) -> list[StatsRecord]:
        """Query stored stats records.

        Args:
            profile: Profile to filter by.
            campaign_id: Campaign to filter by.
            date_from: Optional start date (YYYY-MM-DD).
            date_to: Optional end date (YYYY-MM-DD).
            limit: Maximum rows to return.

        Returns:
            List of StatsRecord ordered by date asc.
        """
        return self._store.list_stats(profile, campaign_id, date_from, date_to, limit)

    def history_clusters(
            self,
            profile: str,
            campaign_id: int,
            nm_id: int | None = None,
            limit: int = 200,
    ) -> list[ClusterRecord]:
        """Query stored cluster snapshots.

        Args:
            profile: Profile to filter by.
            campaign_id: Campaign to filter by.
            nm_id: Optional product nm_id filter.
            limit: Maximum rows to return.

        Returns:
            List of ClusterRecord ordered by snapshot_time desc.
        """
        return self._store.list_clusters(profile, campaign_id, nm_id, limit)

    def history_budget(
            self,
            profile: str,
            campaign_id: int | None = None,
            limit: int = 100,
    ) -> list[BudgetEvent]:
        """Query stored budget events.

        Args:
            profile: Profile to filter by.
            campaign_id: Optional campaign ID filter.
            limit: Maximum rows to return.

        Returns:
            List of BudgetEvent ordered by created_at desc.
        """
        return self._store.list_budget_events(profile, campaign_id, limit)

    def clear(
            self,
            profile: str,
            campaign_id: int | None = None,
    ) -> dict[str, int]:
        """Clear cached rows for a profile (and optional campaign).

        Args:
            profile: Profile whose data to clear.
            campaign_id: Optional campaign ID filter.

        Returns:
            Dict with deleted row counts per table.
        """
        return self._store.clear(profile, campaign_id)

    def summary(self, profile: str) -> dict[str, int]:
        """Count cached rows per table for a profile.

        Args:
            profile: Profile to summarize.

        Returns:
            Dict mapping table name to row count.
        """
        return self._store.summary(profile)


# ── Helpers ───────────────────────────────────────────────────────────

def _utc_now() -> str:
    """Return current UTC time as ISO string."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _campaign_to_snapshot(campaign, profile: str, now: str) -> CampaignSnapshot:
    """Build a CampaignSnapshot from a Campaign domain object."""
    return CampaignSnapshot(
        campaign_id=campaign.campaign_id,
        profile=profile,
        snapshot_time=now,
        name=campaign.name,
        status=campaign.status.value,
        campaign_type=campaign.campaign_type.value,
        daily_budget=campaign.daily_budget,
        payload_json=json.dumps({
            'bid_type': campaign.bid_type,
            'currency': campaign.currency,
            'start_time': campaign.start_time,
            'updated_time': campaign.updated_time,
        }),
    )
