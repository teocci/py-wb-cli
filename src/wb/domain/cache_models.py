"""Domain models for local SQLite cache.

Defines dataclasses for persisted snapshots of campaigns, stats,
clusters, and budget events captured from WB API responses.
"""

from __future__ import annotations

__all__ = [
    'CampaignSnapshot',
    'StatsRecord',
    'ClusterRecord',
    'BudgetEvent',
]

from dataclasses import dataclass, field


@dataclass(slots=True)
class CampaignSnapshot:
    """A point-in-time snapshot of a WB campaign.

    Attributes:
        id: Auto-increment row ID (0 = not yet persisted).
        campaign_id: WB campaign identifier.
        profile: Profile name used to capture snapshot.
        snapshot_time: ISO UTC timestamp of capture.
        name: Campaign display name.
        status: Campaign status value.
        campaign_type: Campaign type value.
        daily_budget: Daily budget in kopecks.
        payload_json: Full raw API payload serialized as JSON.
    """

    campaign_id: int
    profile: str
    snapshot_time: str
    name: str
    status: int
    campaign_type: int
    daily_budget: int
    payload_json: str
    id: int = 0


@dataclass(slots=True)
class StatsRecord:
    """One day of campaign performance statistics.

    Attributes:
        id: Auto-increment row ID (0 = not yet persisted).
        campaign_id: WB campaign identifier.
        profile: Profile name.
        date: Date string (YYYY-MM-DD).
        views: Impressions count.
        clicks: Clicks count.
        ctr: Click-through rate (%).
        spend: Total spend in kopecks.
        orders: Orders count.
        payload_json: Full raw stat payload as JSON.
    """

    campaign_id: int
    profile: str
    date: str
    views: int
    clicks: int
    ctr: float
    spend: int
    orders: int
    payload_json: str
    id: int = 0


@dataclass(slots=True)
class ClusterRecord:
    """A snapshot of a search cluster state.

    Attributes:
        id: Auto-increment row ID (0 = not yet persisted).
        campaign_id: WB campaign identifier.
        nm_id: Product nm_id.
        norm_query: Normalized search query string.
        profile: Profile name.
        snapshot_time: ISO UTC timestamp.
        bid: Current bid value in kopecks.
        views: Impressions at time of snapshot (0 if not available).
        clicks: Clicks at time of snapshot (0 if not available).
        spend: Spend at time of snapshot (0 if not available).
        orders: Orders at time of snapshot (0 if not available).
    """

    campaign_id: int
    nm_id: int
    norm_query: str
    profile: str
    snapshot_time: str
    bid: int
    views: int = 0
    clicks: int = 0
    spend: int = 0
    orders: int = 0
    id: int = 0


@dataclass(slots=True)
class BudgetEvent:
    """A recorded budget or balance event.

    Attributes:
        id: Auto-increment row ID (0 = not yet persisted).
        profile: Profile name.
        campaign_id: Target campaign (None for balance events).
        event_type: One of 'topup', 'balance_check', 'budget_check'.
        amount: Amount in kopecks (0 for read events).
        balance_after: Account balance after the event (kopecks).
        created_at: ISO UTC timestamp.
        payload_json: Supplemental data as JSON.
    """

    profile: str
    event_type: str
    created_at: str
    payload_json: str
    campaign_id: int | None = None
    amount: int = 0
    balance_after: int = 0
    id: int = 0
