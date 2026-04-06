"""Statistics use-cases for campaigns and clusters."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from wb.client.promotion import PromotionClient
from wb.core.batching import chunk
from wb.core.constants import FULLSTATS_BATCH_SIZE
from wb.core.exceptions import ValidationError
from wb.domain.models import CampaignStats, NmStats

__all__ = ['StatsService']

_DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _validate_date(value: str, label: str) -> None:
    """Validate a date string is YYYY-MM-DD format.

    Args:
        value: Date string to validate.
        label: Label for error messages.

    Raises:
        ValidationError: If format is invalid.
    """
    if not _DATE_PATTERN.match(value):
        raise ValidationError(
            f'{label} must be YYYY-MM-DD format, got {value!r}'
        )


class StatsService:
    """Orchestrates statistics read operations.

    Attributes:
        client: Promotion API client.
        cache_store: Optional SQLite cache for write-through.
        profile_name: Profile name used as cache isolation key.
    """

    def __init__(
            self,
            client: PromotionClient,
            cache_store=None,
            profile_name: str = 'default',
    ) -> None:
        self._client = client
        self._cache = cache_store
        self._profile = profile_name

    def get_campaign_stats(
            self,
            campaign_id: int,
            date_from: str,
            date_to: str,
    ) -> CampaignStats:
        """Retrieve aggregated stats for a single campaign.

        Args:
            campaign_id: Target campaign identifier.
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).

        Returns:
            CampaignStats domain object.

        Raises:
            ValidationError: If date format is invalid or no data returned.
        """
        _validate_date(date_from, '--from')
        _validate_date(date_to, '--to')
        raw = self._client.get_campaign_stats(
            [campaign_id], date_from, date_to,
        )
        if not raw:
            return CampaignStats(campaign_id=campaign_id)
        stats = CampaignStats.from_api(raw[0])
        self._maybe_cache_stats(stats)
        return stats

    def get_campaigns_stats(
            self,
            campaign_ids: list[int],
            date_from: str,
            date_to: str,
    ) -> list[CampaignStats]:
        """Retrieve aggregated stats for multiple campaigns.

        Campaign IDs are automatically chunked into batches of
        FULLSTATS_BATCH_SIZE (50) to respect the API limit.

        Args:
            campaign_ids: List of campaign identifiers.
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).

        Returns:
            List of CampaignStats domain objects.

        Raises:
            ValidationError: If date format is invalid.
        """
        _validate_date(date_from, '--from')
        _validate_date(date_to, '--to')
        raw: list[dict] = []
        for batch in chunk(campaign_ids, FULLSTATS_BATCH_SIZE):
            raw.extend(self._client.get_campaign_stats(batch, date_from, date_to))
        result = [CampaignStats.from_api(item) for item in raw]
        for stats in result:
            self._maybe_cache_stats(stats)
        return result

    def get_product_spend(
            self,
            nm_ids: list[int],
            date_from: str,
            date_to: str,
    ) -> list[NmStats]:
        """Aggregate ad spend per NM ID across all campaigns.

        Fetches all campaigns, filters to those containing any of the
        requested NM IDs, retrieves their stats, and sums spend (and
        other metrics) per product. NMs not found in any campaign are
        included with zero values.

        Args:
            nm_ids: List of product NM IDs to summarise.
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).

        Returns:
            List of NmStats sorted by spend descending, one row per NM ID.

        Raises:
            ValidationError: If date format is invalid.
        """
        _validate_date(date_from, '--from')
        _validate_date(date_to, '--to')
        nm_set = set(nm_ids)
        campaign_ids = self._find_campaign_ids_for_nms(nm_set)
        if not campaign_ids:
            return [NmStats(nm_id=nm) for nm in nm_ids]
        stats_list = self.get_campaigns_stats(campaign_ids, date_from, date_to)
        totals = self._aggregate_nm_stats(stats_list, nm_set)
        result = [totals.get(nm, NmStats(nm_id=nm)) for nm in nm_ids]
        return sorted(result, key=lambda x: x.spend, reverse=True)

    # ── Private helpers ────────────────────────────────────────────────

    def _find_campaign_ids_for_nms(self, nm_set: set[int]) -> list[int]:
        """Return IDs of campaigns that contain at least one of the given NMs.

        Args:
            nm_set: Set of NM IDs to match against.

        Returns:
            List of matching campaign IDs.
        """
        all_raw = self._client.list_campaigns()
        result: list[int] = []
        for c in all_raw:
            campaign_nms = {
                item['nm_id']
                for item in (c.get('nm_settings') or [])
                if 'nm_id' in item
            }
            if nm_set & campaign_nms:
                result.append(c['id'])
        return result

    def _aggregate_nm_stats(
            self,
            stats_list: list[CampaignStats],
            nm_set: set[int],
    ) -> dict[int, NmStats]:
        """Sum NmStats per nm_id across multiple campaigns.

        Only includes NMs present in nm_set.

        Args:
            stats_list: Campaign stats objects to aggregate over.
            nm_set: Set of NM IDs to include.

        Returns:
            Dict mapping nm_id → aggregated NmStats.
        """
        totals: dict[int, NmStats] = {}
        for stats in stats_list:
            for nm in stats.nm_stats:
                if nm.nm_id not in nm_set:
                    continue
                if nm.nm_id in totals:
                    t = totals[nm.nm_id]
                    t.views += nm.views
                    t.clicks += nm.clicks
                    t.orders += nm.orders
                    t.spend += nm.spend
                    t.atbs += nm.atbs
                    t.shks += nm.shks
                else:
                    totals[nm.nm_id] = NmStats(
                        nm_id=nm.nm_id, name=nm.name,
                        views=nm.views, clicks=nm.clicks,
                        orders=nm.orders, spend=nm.spend,
                        atbs=nm.atbs, shks=nm.shks,
                        avg_position=nm.avg_position,
                    )
        return totals

    def _maybe_cache_stats(self, stats: CampaignStats) -> None:
        """Write per-day stats to cache if a CacheStore is configured.

        Args:
            stats: Campaign stats to persist day-by-day.
        """
        if not self._cache:
            return
        from wb.domain.cache_models import StatsRecord
        now = datetime.now(timezone.utc).isoformat()
        for day in stats.days:
            rec = StatsRecord(
                campaign_id=stats.campaign_id,
                profile=self._profile,
                date=day.date,
                views=day.views,
                clicks=day.clicks,
                ctr=0.0,
                spend=int(day.spend),
                orders=day.orders,
                payload_json=json.dumps({'nm_count': len(day.nm_stats)}),
            )
            self._cache.save_stats(rec)
