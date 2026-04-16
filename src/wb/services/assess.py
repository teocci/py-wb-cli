"""AssessService — morning snapshot aggregating account and campaign state."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from wb.core.exceptions import WbCliError
from wb.domain.assess_models import AssessSnapshot, CampaignAssessSummary
from wb.domain.enums import CampaignStatus
from wb.services.budgets import BudgetService
from wb.services.campaigns import CampaignService
from wb.services.stats import StatsService

__all__ = ['AssessService']

logger = logging.getLogger(__name__)


class AssessService:
    """Aggregates balance, campaign status, and spend into a morning snapshot.

    All sub-calls are best-effort: failures are logged and return zero-value
    defaults rather than raising, so a partial outage doesn't block the user's
    daily check.

    Attributes:
        campaign_service: Campaign read service.
        budget_service: Balance and budget service.
        stats_service: Campaign statistics service.
    """

    def __init__(
            self,
            campaign_service: CampaignService,
            budget_service: BudgetService,
            stats_service: StatsService,
    ) -> None:
        self._campaigns = campaign_service
        self._budget = budget_service
        self._stats = stats_service

    def get_snapshot(
            self,
            date_from: str,
            date_to: str,
            quick: bool = False,
    ) -> AssessSnapshot:
        """Build a morning snapshot of account and campaign state.

        Data gathered (all best-effort):
        1. Account balance
        2. Running campaigns
        3. Paused campaigns
        4. Ready (not-yet-started) campaigns
        5. 7-day product spend per NM in running campaigns (skipped in quick mode)

        Args:
            date_from: Start of stats window (YYYY-MM-DD).
            date_to: End of stats window (YYYY-MM-DD).
            quick: When True, skip stats calls (no rate-limit wait).

        Returns:
            AssessSnapshot with all available data.
        """
        from datetime import datetime, timezone

        balance = self._safe_get_balance()
        running = self._safe_list_campaigns(CampaignStatus.RUNNING)
        paused = self._safe_list_campaigns(CampaignStatus.PAUSED)
        ready = self._safe_list_campaigns(CampaignStatus.READY)

        running_summaries = [_campaign_to_summary(c) for c in running]
        paused_summaries = [_campaign_to_summary(c) for c in paused]
        ready_summaries = [_campaign_to_summary(c) for c in ready]

        product_spend: list[dict] = []
        if not quick and running:
            nm_ids = [c.nm_ids[0] for c in running if c.nm_ids]
            if nm_ids:
                product_spend = self._safe_get_product_spend(
                    nm_ids, date_from, date_to,
                )

        return AssessSnapshot(
            data_as_of=datetime.now(timezone.utc).isoformat(),
            balance_rub=round(balance.balance / 100.0, 2),
            running=running_summaries,
            paused=paused_summaries,
            ready=ready_summaries,
            product_spend_7d=product_spend,
        )

    # ── Private helpers ────────────────────────────────────────────────

    def _safe_get_balance(self):
        """Get account balance; return zero-value on failure."""
        from wb.domain.models import AccountBalance
        try:
            return self._budget.get_balance()
        except WbCliError as exc:
            logger.debug('balance unavailable: %s', exc)
            return AccountBalance()

    def _safe_list_campaigns(self, status: CampaignStatus) -> list:
        """List campaigns by status; return empty list on failure."""
        try:
            return self._campaigns.list_campaigns(status=status)
        except WbCliError as exc:
            logger.debug('campaign list (%s) unavailable: %s', status, exc)
            return []

    def _safe_get_product_spend(
            self,
            nm_ids: list[int],
            date_from: str,
            date_to: str,
    ) -> list[dict]:
        """Get per-NM spend; return empty list on failure.

        Converts NmStats to plain dicts for JSON serialization.
        """
        from dataclasses import asdict
        try:
            rows = self._stats.get_product_spend(nm_ids, date_from, date_to)
            return [asdict(r) for r in rows]
        except WbCliError as exc:
            logger.debug('product spend unavailable: %s', exc)
            return []


def _campaign_to_summary(campaign) -> CampaignAssessSummary:
    """Convert a Campaign domain object to an AssessSnapshot summary entry."""
    nm_id = campaign.nm_ids[0] if campaign.nm_ids else 0
    return CampaignAssessSummary(
        campaign_id=campaign.campaign_id,
        name=campaign.name,
        status=campaign.status.name.lower(),
        nm_id=nm_id,
    )


def default_date_window(days: int = 7) -> tuple[str, str]:
    """Return (date_from, date_to) for the last N days ending today.

    Args:
        days: Number of days to look back.

    Returns:
        Tuple of (date_from, date_to) as YYYY-MM-DD strings.
    """
    today = date.today()
    date_from = (today - timedelta(days=days)).strftime('%Y-%m-%d')
    date_to = today.strftime('%Y-%m-%d')
    return date_from, date_to
