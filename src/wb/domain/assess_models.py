"""Domain models for wb assess and wb pulse commands."""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    'CampaignAssessSummary',
    'AssessSnapshot',
    'CampaignPulse',
    'PulseReport',
    'PulseBaseline',
]


@dataclass(slots=True)
class CampaignAssessSummary:
    """Per-campaign data within an assess snapshot.

    Attributes:
        campaign_id: WB campaign identifier.
        name: Campaign display name.
        status: Campaign status string (running/paused/ready/archived).
        nm_id: First product NM ID (convention: one product per campaign).
        spend_7d_rub: Ad spend in the last 7 days (rubles).
    """

    campaign_id: int
    name: str
    status: str
    nm_id: int = 0
    spend_7d_rub: float = 0.0


@dataclass(slots=True)
class AssessSnapshot:
    """Morning snapshot aggregating account state across all campaigns.

    Attributes:
        data_as_of: ISO timestamp when snapshot was generated.
        balance_rub: Account balance in rubles.
        running: Running campaign summaries.
        paused: Paused campaign summaries.
        ready: Ready-to-start campaign summaries.
        product_spend_7d: Per-NM ad spend for the last 7 days.
    """

    data_as_of: str
    balance_rub: float = 0.0
    running: list[CampaignAssessSummary] = field(default_factory=list)
    paused: list[CampaignAssessSummary] = field(default_factory=list)
    ready: list[CampaignAssessSummary] = field(default_factory=list)
    product_spend_7d: list[dict] = field(default_factory=list)


@dataclass(slots=True)
class CampaignPulse:
    """Intraday health data for a single campaign.

    Attributes:
        campaign_id: WB campaign identifier.
        nm_id: Product NM ID.
        status: Current campaign status string.
        budget_remaining_rub: Remaining campaign budget in rubles.
        bid_recommend_rub: Current recommended bid in rubles.
        bid_minimum_rub: Current minimum bid in rubles.
        bid_recommend_drift_pct: Change vs morning baseline (percent).
        bid_floor_drift_pct: Change in minimum bid vs morning baseline.
        alerts: List of alert codes for this campaign.
    """

    campaign_id: int
    nm_id: int = 0
    status: str = 'unknown'
    budget_remaining_rub: float = 0.0
    bid_recommend_rub: float = 0.0
    bid_minimum_rub: float = 0.0
    bid_recommend_drift_pct: float = 0.0
    bid_floor_drift_pct: float = 0.0
    alerts: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PulseReport:
    """Intraday pulse report for a set of campaigns.

    Attributes:
        timestamp: ISO timestamp when pulse was captured.
        campaigns: Per-campaign pulse data.
        action_needed: True if any campaign has alerts.
    """

    timestamp: str
    campaigns: list[CampaignPulse] = field(default_factory=list)
    action_needed: bool = False


@dataclass(slots=True)
class PulseBaseline:
    """Morning bid baseline saved by wb assess for drift comparison.

    Attributes:
        saved_at: ISO timestamp when baseline was saved.
        campaigns: Per-campaign baseline data keyed by campaign_id.
    """

    saved_at: str
    campaigns: dict[str, dict] = field(default_factory=dict)
