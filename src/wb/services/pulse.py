"""PulseService — intraday health check using real-time endpoints only."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from wb.core.exceptions import WbCliError
from wb.domain.assess_models import CampaignPulse, PulseBaseline, PulseReport
from wb.services.bids import BidService
from wb.services.budgets import BudgetService
from wb.services.campaigns import CampaignService

__all__ = ['PulseService']

logger = logging.getLogger(__name__)

# Alert thresholds
_BID_SURGE_THRESHOLD_PCT = 15.0   # bid recommend jumped this much → competitor_surge
_BID_FLOOR_THRESHOLD_PCT = 10.0   # minimum bid up this much → bid_floor_rising
_BUDGET_LOW_RUB = 500.0           # absolute low budget threshold
_BUDGET_LOW_PCT = 20.0            # % of baseline budget remaining → budget_low


class PulseService:
    """Captures real-time intraday signals for running campaigns.

    Uses only real-time endpoints (bid recommendations, budget, campaign status).
    No analytics calls — those have hourly/30-min lag and belong in AssessService.

    Attributes:
        campaign_service: Campaign read service.
        budget_service: Budget and balance service.
        bid_service: Bid recommendation service.
        config_dir: Path to ``~/.wb-cli/`` for reading pulse_baseline.json.
    """

    def __init__(
            self,
            campaign_service: CampaignService,
            budget_service: BudgetService,
            bid_service: BidService,
            config_dir: Path,
    ) -> None:
        self._campaigns = campaign_service
        self._budget = budget_service
        self._bids = bid_service
        self._config_dir = config_dir

    def get_pulse(self, campaign_ids: list[int]) -> PulseReport:
        """Check intraday health for the given campaigns.

        Sequentially fetches bid recommendations, budget, and status for each
        campaign. Rate limits are respected because all calls share the same
        HTTP client and its per-path rate limiter.

        Args:
            campaign_ids: Campaign IDs to check.

        Returns:
            PulseReport with per-campaign health data and action_needed flag.
        """
        from datetime import datetime, timezone

        baseline = self._load_baseline()
        results = [
            self._check_campaign(cid, baseline)
            for cid in campaign_ids
        ]
        return PulseReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            campaigns=results,
            action_needed=any(r.alerts for r in results),
        )

    def save_baseline(self, campaign_ids: list[int]) -> PulseBaseline:
        """Fetch and save current bid recommendations as a morning baseline.

        Called by ``wb assess`` at the end of its run. Subsequent ``wb pulse``
        calls compare live bid recommendations against this baseline to detect
        intraday drift.

        Args:
            campaign_ids: Campaign IDs to collect baselines for.

        Returns:
            The saved PulseBaseline.
        """
        from datetime import datetime, timezone

        baseline_data: dict[str, dict] = {}
        for cid in campaign_ids:
            campaign = self._safe_get_campaign(cid)
            nm_id = campaign.nm_ids[0] if campaign and campaign.nm_ids else None
            bids = self._safe_get_recommended_bids(cid, nm_id)
            recommend = bids[0].competitive if bids else 0
            budget = self._safe_get_budget(cid)
            baseline_data[str(cid)] = {
                'recommend_kopecks': recommend,
                # Minimum bid floor lives on a separate endpoint (/v1/bids/min)
                # that pulse does not call to keep run time bounded; baseline
                # always records 0 here. Re-add when intraday floor tracking
                # is implemented.
                'minimum_kopecks': 0,
                'budget_rub': budget.total,
            }

        baseline = PulseBaseline(
            saved_at=datetime.now(timezone.utc).isoformat(),
            campaigns=baseline_data,
        )
        self._save_baseline(baseline)
        return baseline

    # ── Private helpers ────────────────────────────────────────────────

    def _check_campaign(
            self, campaign_id: int, baseline: PulseBaseline,
    ) -> CampaignPulse:
        """Fetch live data and compute alerts for a single campaign."""
        campaign = self._safe_get_campaign(campaign_id)
        budget = self._safe_get_budget(campaign_id)
        nm_id = campaign.nm_ids[0] if campaign and campaign.nm_ids else 0
        bids = self._safe_get_recommended_bids(
            campaign_id, nm_id if nm_id else None,
        )

        status = campaign.status.name.lower() if campaign else 'unknown'
        budget_rub = float(budget.total) if budget else 0.0

        recommend_rub = bids[0].competitive / 100.0 if bids else 0.0
        # /v0/bids/recommendations does not return a minimum bid; the floor
        # tracker stays at zero until a separate /v1/bids/min poll is wired
        # into pulse. Keeping the field preserves the JSON schema.
        minimum_rub = 0.0

        base = baseline.campaigns.get(str(campaign_id), {})
        drift_pct = _compute_drift(
            recommend_rub * 100.0,
            base.get('recommend_kopecks', 0),
        )
        floor_drift_pct = 0.0
        alerts = _compute_alerts(
            status=status,
            budget_rub=budget_rub,
            baseline_budget_rub=base.get('budget_rub', 0),
            bid_drift_pct=drift_pct,
            floor_drift_pct=floor_drift_pct,
        )

        return CampaignPulse(
            campaign_id=campaign_id,
            nm_id=nm_id,
            status=status,
            budget_remaining_rub=round(budget_rub, 2),
            bid_recommend_rub=round(recommend_rub, 2),
            bid_minimum_rub=round(minimum_rub, 2),
            bid_recommend_drift_pct=round(drift_pct, 1),
            bid_floor_drift_pct=round(floor_drift_pct, 1),
            alerts=alerts,
        )

    def _safe_get_campaign(self, campaign_id: int):
        """Get campaign; return None on failure."""
        try:
            return self._campaigns.get_campaign(campaign_id)
        except WbCliError as exc:
            logger.debug('campaign %s unavailable: %s', campaign_id, exc)
            return None

    def _safe_get_budget(self, campaign_id: int):
        """Get budget; return zero-value on failure."""
        from wb.domain.models import BudgetSnapshot
        try:
            return self._budget.get_budget(campaign_id)
        except WbCliError as exc:
            logger.debug('budget %s unavailable: %s', campaign_id, exc)
            return BudgetSnapshot(campaign_id=campaign_id)

    def _safe_get_recommended_bids(
            self, campaign_id: int, nm_id: int | None = None,
    ) -> list:
        """Get recommended bids; return empty list on failure.

        Passes ``nm_id`` through to the bid service so the underlying call
        is a single per-item lookup instead of a multi-NM loop. Pulse only
        needs one bid value per campaign for drift detection, and the
        per-item endpoint is rate-limited to 5/min — looping every campaign
        per pulse cycle would blow the budget.
        """
        try:
            return self._bids.get_recommended_bids(campaign_id, nm_id=nm_id)
        except WbCliError as exc:
            logger.debug('bids %s unavailable: %s', campaign_id, exc)
            return []

    def _load_baseline(self) -> PulseBaseline:
        """Load pulse_baseline.json from config_dir; return empty on missing."""
        from datetime import datetime, timezone
        path = self._config_dir / 'pulse_baseline.json'
        if not path.exists():
            return PulseBaseline(
                saved_at=datetime.now(timezone.utc).isoformat(),
            )
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return PulseBaseline(
                saved_at=data.get('saved_at', ''),
                campaigns=data.get('campaigns', {}),
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug('failed to load pulse baseline: %s', exc)
            return PulseBaseline(saved_at='')

    def _save_baseline(self, baseline: PulseBaseline) -> None:
        """Write pulse_baseline.json to config_dir."""
        path = self._config_dir / 'pulse_baseline.json'
        try:
            path.write_text(
                json.dumps(
                    {'saved_at': baseline.saved_at, 'campaigns': baseline.campaigns},
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding='utf-8',
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning('failed to save pulse baseline: %s', exc)


# ── Pure functions ─────────────────────────────────────────────────────────────


def _compute_drift(current: float, baseline: float) -> float:
    """Compute percentage drift from baseline; 0.0 when baseline is zero."""
    if baseline == 0:
        return 0.0
    return ((current - baseline) / baseline) * 100.0


def _compute_alerts(
        *,
        status: str,
        budget_rub: float,
        baseline_budget_rub: float,
        bid_drift_pct: float,
        floor_drift_pct: float,
) -> list[str]:
    """Compute alert codes for a campaign based on live vs baseline data."""
    alerts: list[str] = []
    if status == 'paused':
        alerts.append('campaign_paused')
    if budget_rub < _BUDGET_LOW_RUB:
        alerts.append('budget_low')
    elif baseline_budget_rub > 0:
        if (budget_rub / baseline_budget_rub) * 100 < _BUDGET_LOW_PCT:
            alerts.append('budget_low')
    if bid_drift_pct >= _BID_SURGE_THRESHOLD_PCT:
        alerts.append('competitor_surge')
    if floor_drift_pct >= _BID_FLOOR_THRESHOLD_PCT:
        alerts.append('bid_floor_rising')
    return alerts
