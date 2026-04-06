"""Composite product-level use-cases that aggregate multiple data sources."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from wb.core.exceptions import WbCliError
from wb.domain.models import (
    CampaignOverview,
    CampaignStatus,
    NmStats,
    ProductSummary,
)
from wb.services.budgets import BudgetService
from wb.services.campaigns import CampaignService
from wb.services.clusters import ClusterService
from wb.services.stats import StatsService

__all__ = ['ProductService']

logger = logging.getLogger(__name__)


class ProductService:
    """Aggregates data from multiple services into composite product views.

    Analytics and prices sub-services are optional. When unavailable their
    data fields remain at default values rather than raising errors.

    Attributes:
        campaign_service: Campaign read/write service.
        budget_service: Budget and balance service.
        stats_service: Campaign statistics service.
        cluster_service: Search cluster service.
        analytics_service: Analytics funnel service (optional).
        prices_service: Prices and discounts service (optional).
    """

    def __init__(
            self,
            campaign_service: CampaignService,
            budget_service: BudgetService,
            stats_service: StatsService,
            cluster_service: ClusterService,
            analytics_service=None,
            prices_service=None,
    ) -> None:
        self._campaigns = campaign_service
        self._budget = budget_service
        self._stats = stats_service
        self._clusters = cluster_service
        self._analytics = analytics_service
        self._prices = prices_service

    def get_product_summary(
            self,
            nm_ids: list[int],
            date_from: str,
            date_to: str,
    ) -> list[ProductSummary]:
        """Build a composite summary per NM ID in one aggregated call.

        Data flow:
        1. StatsService.get_product_spend → per-NM ad metrics
        2. PricesService.get_prices → price and discount (best-effort)
        3. AnalyticsService.get_product_funnel → funnel metrics (best-effort)
        4. CampaignService.list_campaigns → campaigns containing each NM
        5. ClusterService.list_clusters → cluster counts per campaign/NM pair

        Args:
            nm_ids: Product NM IDs to summarise.
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).

        Returns:
            List of ProductSummary, one per requested NM ID.
        """
        if not nm_ids:
            return []

        spend_map = self._fetch_spend(nm_ids, date_from, date_to)
        price_map = self._fetch_prices(nm_ids)
        funnel_map = self._fetch_funnel(nm_ids, date_from, date_to)
        campaign_map, cluster_counts = self._fetch_campaigns_and_clusters(nm_ids)

        return [
            self._build_summary(
                nm_id, spend_map, price_map, funnel_map,
                campaign_map, cluster_counts,
            )
            for nm_id in nm_ids
        ]

    def get_campaign_overview(
            self,
            campaign_id: int,
            date_from: str,
            date_to: str,
    ) -> CampaignOverview:
        """Build a composite campaign snapshot in one aggregated call.

        Data flow:
        1. CampaignService.get_campaign → campaign details
        2. BudgetService.get_budget → budget (best-effort)
        3. StatsService.get_campaign_stats → stats (best-effort)
        4. ClusterService.list_clusters → cluster counts (best-effort)

        Args:
            campaign_id: Campaign identifier.
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).

        Returns:
            CampaignOverview domain object.
        """
        campaign = self._campaigns.get_campaign(campaign_id)
        budget = self._safe_get_budget(campaign_id)
        stats = self._safe_get_stats(campaign_id, date_from, date_to)
        cluster_count, active_count = self._safe_count_clusters(
            campaign_id, campaign.nm_ids,
        )

        return CampaignOverview(
            campaign_id=campaign_id,
            name=campaign.name,
            status=campaign.status,
            campaign_type=campaign.campaign_type,
            nm_ids=campaign.nm_ids,
            total_budget=budget.total,
            cash=budget.cash,
            netting=budget.netting,
            views=stats.views,
            clicks=stats.clicks,
            ctr=stats.ctr,
            orders=stats.orders,
            spend=stats.spend,
            cpc=stats.cpc,
            nm_stats=stats.nm_stats,
            cluster_count=cluster_count,
            active_cluster_count=active_count,
            currency=stats.currency or campaign.currency,
        )

    # ── Private helpers ────────────────────────────────────────────────

    def _fetch_spend(
            self,
            nm_ids: list[int],
            date_from: str,
            date_to: str,
    ) -> dict[int, NmStats]:
        """Return nm_id → NmStats mapping from StatsService."""
        rows = self._stats.get_product_spend(nm_ids, date_from, date_to)
        return {r.nm_id: r for r in rows}

    def _fetch_prices(self, nm_ids: list[int]) -> dict[int, object]:
        """Return nm_id → ProductPrice mapping (best-effort)."""
        if self._prices is None:
            return {}
        try:
            rows = self._prices.get_prices(nm_ids=nm_ids)
            return {r.nm_id: r for r in rows}
        except WbCliError as exc:
            logger.debug('prices unavailable for summary: %s', exc)
            return {}

    def _fetch_funnel(
            self,
            nm_ids: list[int],
            date_from: str,
            date_to: str,
    ) -> dict[int, object]:
        """Return nm_id → ProductFunnelStats mapping (best-effort)."""
        if self._analytics is None:
            return {}
        try:
            rows = self._analytics.get_product_funnel(
                date_from, date_to, nm_ids=nm_ids,
            )
            return {r.nm_id: r for r in rows}
        except WbCliError as exc:
            logger.debug('analytics unavailable for summary: %s', exc)
            return {}

    def _fetch_campaigns_and_clusters(
            self,
            nm_ids: list[int],
    ) -> tuple[dict[int, list[int]], dict[int, tuple[int, int]]]:
        """Return (campaign_map, cluster_counts).

        campaign_map: nm_id → list of campaign_ids containing that nm_id.
        cluster_counts: nm_id → (total_clusters, active_clusters).
        """
        nm_set = set(nm_ids)
        campaign_map: dict[int, list[int]] = {nm: [] for nm in nm_ids}
        cluster_counts: dict[int, tuple[int, int]] = {nm: (0, 0) for nm in nm_ids}

        try:
            campaigns = self._campaigns.list_campaigns()
        except WbCliError as exc:
            logger.debug('campaigns unavailable for summary: %s', exc)
            return campaign_map, cluster_counts

        for camp in campaigns:
            matched = nm_set & set(camp.nm_ids)
            if not matched:
                continue
            for nm_id in matched:
                campaign_map[nm_id].append(camp.campaign_id)
                total, active = self._safe_count_clusters_for_nm(
                    camp.campaign_id, nm_id,
                )
                t, a = cluster_counts[nm_id]
                cluster_counts[nm_id] = (t + total, a + active)

        return campaign_map, cluster_counts

    def _safe_count_clusters_for_nm(
            self, campaign_id: int, nm_id: int,
    ) -> tuple[int, int]:
        """Count (total, active) clusters for a (campaign, nm) pair."""
        try:
            clusters = self._clusters.list_clusters(campaign_id, nm_id)
            total = len(clusters)
            active = sum(1 for c in clusters if c.is_active)
            return total, active
        except WbCliError as exc:
            logger.debug(
                'cluster list failed (campaign=%s, nm=%s): %s',
                campaign_id, nm_id, exc,
            )
            return 0, 0

    def _safe_get_budget(self, campaign_id: int):
        """Get budget with fallback to zero-value snapshot."""
        from wb.domain.models import BudgetSnapshot
        try:
            return self._budget.get_budget(campaign_id)
        except WbCliError as exc:
            logger.debug('budget unavailable for overview: %s', exc)
            return BudgetSnapshot(campaign_id=campaign_id)

    def _safe_get_stats(
            self, campaign_id: int, date_from: str, date_to: str,
    ):
        """Get campaign stats with fallback to zero-value CampaignStats."""
        from wb.domain.models import CampaignStats
        try:
            return self._stats.get_campaign_stats(campaign_id, date_from, date_to)
        except WbCliError as exc:
            logger.debug('stats unavailable for overview: %s', exc)
            return CampaignStats(campaign_id=campaign_id)

    def _safe_count_clusters(
            self, campaign_id: int, nm_ids: list[int],
    ) -> tuple[int, int]:
        """Count total and active clusters across all NMs in a campaign."""
        total, active = 0, 0
        for nm_id in nm_ids:
            t, a = self._safe_count_clusters_for_nm(campaign_id, nm_id)
            total += t
            active += a
        return total, active

    def _build_summary(
            self,
            nm_id: int,
            spend_map: dict,
            price_map: dict,
            funnel_map: dict,
            campaign_map: dict,
            cluster_counts: dict,
    ) -> ProductSummary:
        """Assemble a ProductSummary from the four pre-fetched data maps."""
        nm_stats = spend_map.get(nm_id)
        price = price_map.get(nm_id)
        funnel = funnel_map.get(nm_id)
        campaign_ids = campaign_map.get(nm_id, [])
        total_clusters, active_clusters = cluster_counts.get(nm_id, (0, 0))

        return ProductSummary(
            nm_id=nm_id,
            vendor_code=price.vendor_code if price else '',
            base_price=price.base_price if price else 0.0,
            final_price=price.final_price if price else 0.0,
            discount=price.discount if price else 0,
            ad_spend=nm_stats.spend if nm_stats else 0.0,
            ad_views=nm_stats.views if nm_stats else 0,
            ad_clicks=nm_stats.clicks if nm_stats else 0,
            ad_orders=nm_stats.orders if nm_stats else 0,
            ad_avg_position=nm_stats.avg_position if nm_stats else 0.0,
            open_count=funnel.open_count if funnel else 0,
            cart_count=funnel.cart_count if funnel else 0,
            order_count=funnel.order_count if funnel else 0,
            order_sum=funnel.order_sum if funnel else 0,
            campaign_ids=campaign_ids,
            cluster_count=total_clusters,
            active_cluster_count=active_clusters,
        )
