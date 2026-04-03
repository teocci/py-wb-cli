"""Python SDK facade for WB CLI operations.

Thin importable layer that lets scripts and AI agents call operations as
typed Python functions without subprocess or Typer involvement. Each function
wraps a factory call + service method and returns typed domain objects.
"""

from __future__ import annotations

from wb.domain.models import (
    CampaignCreate,
    ClusterBidMutation,
    MutationResult,
    OptimizationDecision,
)
from wb.services._factory import (
    create_campaign_service,
    create_budget_service,
    create_cluster_service,
    create_optimizer_service,
    create_bid_service,
)

__all__ = [
    'list_campaigns',
    'get_campaign',
    'create_campaign',
    'clone_campaign',
    'start_campaign',
    'pause_campaign',
    'stop_campaign',
    'get_balance',
    'get_budget',
    'topup_budget',
    'get_recommended_bids',
    'set_item_bid',
    'list_clusters',
    'set_cluster_bids',
    'set_minus_phrases',
    'plan_clusters',
    'plan_budget',
    'plan_negatives',
    'plan_all',
    'apply_clusters',
    'apply_all',
]


# ── Campaign operations ──────────────────────────────────────────────────

def list_campaigns(profile: str | None = None):
    """List all campaigns.

    Args:
        profile: Profile name, or None for active profile.

    Returns:
        List of Campaign objects.
    """
    svc = create_campaign_service(profile)
    return svc.list_campaigns()


def get_campaign(campaign_id: int, profile: str | None = None):
    """Get details for a single campaign.

    Args:
        campaign_id: Campaign identifier.
        profile: Profile name, or None for active profile.

    Returns:
        Campaign object.
    """
    svc = create_campaign_service(profile)
    return svc.get_campaign(campaign_id)


def create_campaign(
        name: str,
        nm_ids: list[int],
        bid_type: str = 'manual',
        placement_types: list[str] | None = None,
        dry_run: bool = False,
        profile: str | None = None,
) -> MutationResult:
    """Create a new campaign.

    Args:
        name: Campaign name.
        nm_ids: List of product NM IDs.
        bid_type: Bid type (default: 'manual').
        placement_types: Placement types (default: ['search']).
        dry_run: If True, simulate without executing.
        profile: Profile name, or None for active profile.

    Returns:
        MutationResult with success status and message.
    """
    placement_types = placement_types or ['search']
    params = CampaignCreate(
        name=name,
        nm_ids=nm_ids,
        bid_type=bid_type,
        placement_types=placement_types,
    )
    svc = create_campaign_service(profile)
    return svc.create_campaign(params, dry_run=dry_run)


def clone_campaign(
        campaign_id: int,
        name: str | None = None,
        nm_ids: list[int] | None = None,
        dry_run: bool = False,
        profile: str | None = None,
) -> MutationResult:
    """Clone an existing campaign.

    Args:
        campaign_id: Source campaign identifier.
        name: New campaign name (default: original + " (copy)").
        nm_ids: Product NM IDs for new campaign (required).
        dry_run: If True, simulate without executing.
        profile: Profile name, or None for active profile.

    Returns:
        MutationResult with success status and message.

    Raises:
        ValueError: If nm_ids is None or empty.
    """
    if not nm_ids:
        raise ValueError('nm_ids is required for clone')
    svc = create_campaign_service(profile)
    source = svc.get_campaign(campaign_id)
    new_name = name or f'{source.name} (copy)'
    params = CampaignCreate(
        name=new_name,
        nm_ids=nm_ids,
        bid_type=source.bid_type,
        placement_types=['search'],
    )
    return svc.create_campaign(params, dry_run=dry_run)


def start_campaign(
        campaign_id: int,
        dry_run: bool = False,
        profile: str | None = None,
) -> MutationResult:
    """Start a campaign.

    Args:
        campaign_id: Campaign identifier.
        dry_run: If True, simulate without executing.
        profile: Profile name, or None for active profile.

    Returns:
        MutationResult with success status and message.
    """
    svc = create_campaign_service(profile)
    return svc.start_campaign(campaign_id, dry_run=dry_run)


def pause_campaign(
        campaign_id: int,
        dry_run: bool = False,
        profile: str | None = None,
) -> MutationResult:
    """Pause a campaign.

    Args:
        campaign_id: Campaign identifier.
        dry_run: If True, simulate without executing.
        profile: Profile name, or None for active profile.

    Returns:
        MutationResult with success status and message.
    """
    svc = create_campaign_service(profile)
    return svc.pause_campaign(campaign_id, dry_run=dry_run)


def stop_campaign(
        campaign_id: int,
        dry_run: bool = False,
        profile: str | None = None,
) -> MutationResult:
    """Stop (archive) a campaign.

    Args:
        campaign_id: Campaign identifier.
        dry_run: If True, simulate without executing.
        profile: Profile name, or None for active profile.

    Returns:
        MutationResult with success status and message.
    """
    svc = create_campaign_service(profile)
    return svc.stop_campaign(campaign_id, dry_run=dry_run)


# ── Budget operations ────────────────────────────────────────────────────

def get_balance(profile: str | None = None):
    """Get account balance.

    Args:
        profile: Profile name, or None for active profile.

    Returns:
        AccountBalance object.
    """
    svc = create_budget_service(profile)
    return svc.get_balance()


def get_budget(campaign_id: int, profile: str | None = None):
    """Get campaign budget.

    Args:
        campaign_id: Campaign identifier.
        profile: Profile name, or None for active profile.

    Returns:
        BudgetSnapshot object.
    """
    svc = create_budget_service(profile)
    return svc.get_budget(campaign_id)


def topup_budget(
        campaign_id: int,
        amount: int,
        dry_run: bool = False,
        profile: str | None = None,
) -> MutationResult:
    """Top up campaign budget.

    Args:
        campaign_id: Campaign identifier.
        amount: Amount to deposit in kopecks.
        dry_run: If True, simulate without executing.
        profile: Profile name, or None for active profile.

    Returns:
        MutationResult with success status and message.
    """
    svc = create_budget_service(profile)
    return svc.topup(campaign_id, amount, dry_run=dry_run)


# ── Bid operations ───────────────────────────────────────────────────────

def get_recommended_bids(
        campaign_id: int,
        nm_id: int,
        subject_id: int | None = None,
        profile: str | None = None,
):
    """Get recommended bids for a product.

    Args:
        campaign_id: Campaign identifier.
        nm_id: Product NM ID.
        subject_id: Subject ID (optional).
        profile: Profile name, or None for active profile.

    Returns:
        List of RecommendedBid objects.
    """
    svc = create_bid_service(profile)
    return svc.get_recommended_bids(campaign_id, nm_id, subject_id)


def set_item_bid(
        campaign_id: int,
        nm_id: int,
        cpm: int,
        subject_id: int | None = None,
        dry_run: bool = False,
        profile: str | None = None,
) -> MutationResult:
    """Set bid for a single item.

    Args:
        campaign_id: Campaign identifier.
        nm_id: Product NM ID.
        cpm: Bid amount in kopecks.
        subject_id: Subject ID (optional).
        dry_run: If True, simulate without executing.
        profile: Profile name, or None for active profile.

    Returns:
        MutationResult with success status and message.
    """
    svc = create_bid_service(profile)
    return svc.set_item_bid(campaign_id, nm_id, cpm, subject_id, dry_run=dry_run)


# ── Cluster operations ───────────────────────────────────────────────────

def list_clusters(
        campaign_id: int,
        nm_id: int,
        profile: str | None = None,
):
    """List search clusters for a product.

    Args:
        campaign_id: Campaign identifier.
        nm_id: Product NM ID.
        profile: Profile name, or None for active profile.

    Returns:
        List of SearchCluster objects.
    """
    svc = create_cluster_service(profile)
    return svc.list_clusters(campaign_id, nm_id)


def set_cluster_bids(
        campaign_id: int,
        mutations: list[ClusterBidMutation],
        dry_run: bool = False,
        profile: str | None = None,
) -> MutationResult:
    """Set bids for search clusters.

    Args:
        campaign_id: Campaign identifier.
        mutations: List of ClusterBidMutation objects.
        dry_run: If True, simulate without executing.
        profile: Profile name, or None for active profile.

    Returns:
        MutationResult with success status and message.
    """
    svc = create_cluster_service(profile)
    return svc.set_cluster_bids(campaign_id, mutations, dry_run=dry_run)


def set_minus_phrases(
        campaign_id: int,
        nm_id: int,
        phrases: list[str],
        dry_run: bool = False,
        profile: str | None = None,
) -> MutationResult:
    """Set minus phrases for a product.

    Args:
        campaign_id: Campaign identifier.
        nm_id: Product NM ID.
        phrases: List of phrases to exclude.
        dry_run: If True, simulate without executing.
        profile: Profile name, or None for active profile.

    Returns:
        MutationResult with success status and message.
    """
    svc = create_cluster_service(profile)
    return svc.set_minus_phrases(campaign_id, nm_id, phrases, dry_run=dry_run)


# ── Optimizer operations ─────────────────────────────────────────────────

def plan_clusters(
        campaign_id: int,
        nm_id: int,
        date_from: str,
        date_to: str,
        profile: str | None = None,
) -> list[OptimizationDecision]:
    """Generate cluster bid optimization decisions.

    Args:
        campaign_id: Campaign identifier.
        nm_id: Product NM ID.
        date_from: Stats period start (YYYY-MM-DD).
        date_to: Stats period end (YYYY-MM-DD).
        profile: Profile name, or None for active profile.

    Returns:
        List of OptimizationDecision objects.
    """
    svc = create_optimizer_service(profile)
    return svc.plan_clusters(campaign_id, nm_id, date_from, date_to)


def plan_budget(
        campaign_id: int,
        profile: str | None = None,
) -> list[OptimizationDecision]:
    """Generate budget optimization decisions.

    Args:
        campaign_id: Campaign identifier.
        profile: Profile name, or None for active profile.

    Returns:
        List of OptimizationDecision objects (at most one).
    """
    svc = create_optimizer_service(profile)
    return svc.plan_budget(campaign_id)


def plan_negatives(
        campaign_id: int,
        nm_id: int,
        date_from: str,
        date_to: str,
        profile: str | None = None,
) -> list[OptimizationDecision]:
    """Generate minus phrase recommendations.

    Args:
        campaign_id: Campaign identifier.
        nm_id: Product NM ID.
        date_from: Stats period start (YYYY-MM-DD).
        date_to: Stats period end (YYYY-MM-DD).
        profile: Profile name, or None for active profile.

    Returns:
        List of OptimizationDecision objects.
    """
    svc = create_optimizer_service(profile)
    return svc.plan_negatives(campaign_id, nm_id, date_from, date_to)


def plan_all(
        campaign_id: int,
        nm_id: int,
        date_from: str,
        date_to: str,
        profile: str | None = None,
) -> list[OptimizationDecision]:
    """Generate full optimization plan.

    Args:
        campaign_id: Campaign identifier.
        nm_id: Product NM ID.
        date_from: Stats period start (YYYY-MM-DD).
        date_to: Stats period end (YYYY-MM-DD).
        profile: Profile name, or None for active profile.

    Returns:
        List of all OptimizationDecision objects.
    """
    svc = create_optimizer_service(profile)
    return svc.plan_all(campaign_id, nm_id, date_from, date_to)


def apply_clusters(
        campaign_id: int,
        nm_id: int,
        date_from: str,
        date_to: str,
        dry_run: bool = False,
        profile: str | None = None,
) -> list[MutationResult]:
    """Plan and apply cluster bid optimizations.

    Args:
        campaign_id: Campaign identifier.
        nm_id: Product NM ID.
        date_from: Stats period start (YYYY-MM-DD).
        date_to: Stats period end (YYYY-MM-DD).
        dry_run: If True, simulate without executing.
        profile: Profile name, or None for active profile.

    Returns:
        List of MutationResult objects.
    """
    svc = create_optimizer_service(profile)
    return svc.apply_clusters(campaign_id, nm_id, date_from, date_to, dry_run=dry_run)


def apply_all(
        campaign_id: int,
        nm_id: int,
        date_from: str,
        date_to: str,
        dry_run: bool = False,
        profile: str | None = None,
) -> list[MutationResult]:
    """Plan and apply all optimizations.

    Args:
        campaign_id: Campaign identifier.
        nm_id: Product NM ID.
        date_from: Stats period start (YYYY-MM-DD).
        date_to: Stats period end (YYYY-MM-DD).
        dry_run: If True, simulate without executing.
        profile: Profile name, or None for active profile.

    Returns:
        List of MutationResult objects.
    """
    svc = create_optimizer_service(profile)
    return svc.apply_all(campaign_id, nm_id, date_from, date_to, dry_run=dry_run)
