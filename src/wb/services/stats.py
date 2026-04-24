"""Statistics use-cases for campaigns and clusters."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

from wb.client.promotion import PromotionClient
from wb.core.batching import chunk
from wb.core.constants import FULLSTATS_BATCH_SIZE
from wb.core.exceptions import ValidationError
from wb.domain.enums import CampaignStatus
from wb.domain.models import CampaignStats, DailyReportRow, NmStats
from wb.storage.response_cache import (
    ResponseCache,
    is_past_day_range,
    make_cache_key,
)

if TYPE_CHECKING:
    from wb.services.analytics import AnalyticsService

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
        response_cache: Optional read-through cache for idempotent
            past-day queries.
        cache_token: Token value used to fingerprint the response cache
            key; required whenever ``response_cache`` is set.
    """

    def __init__(
            self,
            client: PromotionClient,
            cache_store=None,
            profile_name: str = 'default',
            *,
            response_cache: ResponseCache | None = None,
            cache_token: str | None = None,
    ) -> None:
        self._client = client
        self._cache = cache_store
        self._profile = profile_name
        self._response_cache = response_cache
        self._cache_token = cache_token or ''

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

    def get_stats_by_status(
            self,
            statuses: list[int],
            date_from: str,
            date_to: str,
    ) -> list[CampaignStats]:
        """Retrieve stats for all campaigns matching the given status codes.

        Args:
            statuses: CampaignStatus integer values to include.
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).

        Returns:
            List of CampaignStats, empty if no matching campaigns exist.

        Raises:
            ValidationError: If date format is invalid.
        """
        _validate_date(date_from, '--from')
        _validate_date(date_to, '--to')
        matching = self._client.list_campaigns(status=statuses)
        ids = [c['id'] for c in matching if 'id' in c]
        if not ids:
            return []
        return self.get_campaigns_stats(ids, date_from, date_to)

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

        When a response cache is configured and the date range is
        strictly in the past, results are cached across invocations.

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
        return self._cached_or_fetch(
            method_name='stats.get_product_spend',
            cache_params={
                'nm_ids': list(nm_ids),
                'date_from': date_from,
                'date_to': date_to,
            },
            date_from=date_from,
            date_to=date_to,
            fetcher=lambda: self._get_product_spend_fresh(
                nm_ids, date_from, date_to,
            ),
            serialize=lambda result: [asdict(row) for row in result],
            deserialize=lambda raw: [NmStats(**row) for row in raw],
        )

    def _get_product_spend_fresh(
            self,
            nm_ids: list[int],
            date_from: str,
            date_to: str,
            *,
            raw_campaigns: list[dict] | None = None,
    ) -> list[NmStats]:
        """Fetch product spend from the API without cache lookup.

        When ``raw_campaigns`` is provided, reuses the pre-fetched list and
        skips the initial ``list_campaigns`` call — this is the path
        :meth:`_get_daily_report_fresh` takes to avoid a duplicate API hit.
        """
        nm_set = set(nm_ids)
        campaign_ids = self._find_campaign_ids_for_nms(
            nm_set, raw_campaigns=raw_campaigns,
        )
        if not campaign_ids:
            return [NmStats(nm_id=nm) for nm in nm_ids]
        stats_list = self.get_campaigns_stats(campaign_ids, date_from, date_to)
        totals = self._aggregate_nm_stats(stats_list, nm_set)
        result = [totals.get(nm, NmStats(nm_id=nm)) for nm in nm_ids]
        return sorted(result, key=lambda x: x.spend, reverse=True)

    def get_daily_report(
            self,
            date: str,
            *,
            statuses: list[int] | None = None,
            analytics_svc: AnalyticsService | None = None,
    ) -> list[DailyReportRow]:
        """Build a per-product daily report combining ad spend and total orders.

        Discovers products automatically from campaigns matching the given
        statuses, retrieves ad spend via the Promotion API, and enriches with
        total platform orders from the Analytics funnel API when available.

        When a response cache is configured and ``date`` is strictly in
        the past, results are cached across invocations.

        Args:
            date: Report date in YYYY-MM-DD format.
            statuses: CampaignStatus integer values to include (default: active
                = [9, 11]).
            analytics_svc: Optional AnalyticsService for total order counts.
                If None or if the call fails (e.g. 403 missing scope), total
                orders default to 0 for all rows.

        Returns:
            List of DailyReportRow sorted by ad_spend descending.

        Raises:
            ValidationError: If date format is invalid.
        """
        _validate_date(date, '--date')
        resolved_statuses = statuses if statuses is not None else [9, 11]
        return self._cached_or_fetch(
            method_name='stats.get_daily_report',
            cache_params={
                'date': date,
                'statuses': list(resolved_statuses),
                'with_analytics': analytics_svc is not None,
            },
            date_from=date,
            date_to=date,
            fetcher=lambda: self._get_daily_report_fresh(
                date, resolved_statuses, analytics_svc,
            ),
            serialize=lambda result: [asdict(row) for row in result],
            deserialize=lambda raw: [DailyReportRow(**row) for row in raw],
        )

    def _get_daily_report_fresh(
            self,
            date: str,
            statuses: list[int],
            analytics_svc: AnalyticsService | None,
    ) -> list[DailyReportRow]:
        """Fetch the daily report from the APIs without cache lookup.

        Calls ``list_campaigns`` exactly once and filters by status in
        memory, then threads the pre-fetched list through to the spend
        fetch so the second identical API call is eliminated (F-11).
        """
        raw_campaigns = self._client.list_campaigns()
        nm_ids = self._collect_nm_ids_from_campaigns(raw_campaigns, set(statuses))
        if not nm_ids:
            return []
        spend_rows = self._get_product_spend_fresh(
            nm_ids, date, date, raw_campaigns=raw_campaigns,
        )
        funnel_by_nm = self._fetch_funnel_orders(nm_ids, date, analytics_svc)
        rows = [
            DailyReportRow(
                nm_id=s.nm_id,
                name=s.name,
                ad_spend=s.spend,
                total_orders=funnel_by_nm.get(s.nm_id, 0),
            )
            for s in spend_rows
        ]
        return sorted(rows, key=lambda r: r.ad_spend, reverse=True)

    # ── Private helpers ────────────────────────────────────────────────

    def _find_campaign_ids_for_nms(
            self,
            nm_set: set[int],
            *,
            raw_campaigns: list[dict] | None = None,
    ) -> list[int]:
        """Return IDs of campaigns that contain at least one of the given NMs.

        Args:
            nm_set: Set of NM IDs to match against.
            raw_campaigns: Pre-fetched list of campaign dicts. When ``None``
                (default), fetches from the API; when provided, uses the
                pre-fetched list to avoid a duplicate ``list_campaigns`` call.

        Returns:
            List of matching campaign IDs.
        """
        if raw_campaigns is None:
            raw_campaigns = self._client.list_campaigns()
        result: list[int] = []
        for c in raw_campaigns:
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

    def _collect_nm_ids_from_campaigns(
            self,
            raw_campaigns: list[dict],
            status_set: set[int],
    ) -> list[int]:
        """Return unique NM IDs from campaigns whose status is in ``status_set``.

        Filters the pre-fetched campaign list in memory — the API call
        that produced ``raw_campaigns`` was status-unfiltered because
        :meth:`_get_daily_report_fresh` also needs the full list for the
        spend fetch, and filtering twice on the server would waste a
        second API call.

        Args:
            raw_campaigns: Pre-fetched list of campaign dicts.
            status_set: CampaignStatus integer codes to include.

        Returns:
            Deduplicated list of NM IDs from matching-status campaigns.
        """
        nm_set: set[int] = set()
        for c in raw_campaigns:
            if c.get('status') not in status_set:
                continue
            for item in (c.get('nm_settings') or []):
                if 'nm_id' in item:
                    nm_set.add(item['nm_id'])
        return list(nm_set)

    def _fetch_funnel_orders(
            self,
            nm_ids: list[int],
            date: str,
            analytics_svc: AnalyticsService | None,
    ) -> dict[int, int]:
        """Fetch total platform order counts from the analytics funnel.

        Returns an empty dict if analytics_svc is None or the call fails
        (e.g. missing analytics token → 403).

        Args:
            nm_ids: Product NM IDs to query.
            date: Report date (YYYY-MM-DD).
            analytics_svc: Analytics service instance, or None.

        Returns:
            Dict mapping nm_id → total order count (0 if unavailable).
        """
        if analytics_svc is None:
            return {}
        try:
            funnel_rows = analytics_svc.get_product_funnel(
                date, date, nm_ids=nm_ids,
            )
            return {r.nm_id: r.order_count for r in funnel_rows}
        except Exception:
            return {}

    def _cached_or_fetch(
            self,
            *,
            method_name: str,
            cache_params: dict,
            date_from: str,
            date_to: str,
            fetcher: Callable,
            serialize: Callable,
            deserialize: Callable,
    ):
        """Look up past-day queries in the response cache; else fetch.

        Args:
            method_name: Logical method identifier (cache key component).
            cache_params: Args hashed into the cache key.
            date_from: Start date (YYYY-MM-DD) — determines cacheability.
            date_to: End date (YYYY-MM-DD) — determines cacheability.
            fetcher: Zero-arg callable returning a fresh result.
            serialize: Callable to convert the fresh result to JSON-ish.
            deserialize: Callable to rebuild the result from cached data.

        Returns:
            The fresh or cached result.
        """
        if self._response_cache is None or not is_past_day_range(date_from, date_to):
            return fetcher()
        key = make_cache_key(method_name, self._cache_token, cache_params)
        cached = self._response_cache.get(key)
        if cached is not None:
            return deserialize(cached)
        result = fetcher()
        self._response_cache.put(key, serialize(result))
        return result

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
