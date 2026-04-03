"""Optimization workflows — recommendation-first rule engine.

Produces explainable OptimizationDecision objects from campaign,
cluster, budget, and statistics data. Mutations are applied only
when explicitly requested via apply methods.
"""

from __future__ import annotations

from wb.domain.enums import ClusterClass, OptimizationAction, TargetType
from wb.domain.models import (
    ClusterBidMutation,
    MutationResult,
    OptimizationDecision,
)
from wb.services.bids import BidService
from wb.services.budgets import BudgetService
from wb.services.campaigns import CampaignService
from wb.services.clusters import ClusterService
from wb.services.stats import StatsService

__all__ = ['OptimizerService']

# ── Thresholds (V1 defaults) ────────────────────────────────────────
MIN_VIEWS = 50
LOW_CTR = 1.0
HIGH_CTR = 4.0
MAX_AVG_POS = 5.0
WASTE_SPEND = 500
BUDGET_ALERT = 0.85
BID_RAISE = 1.20
BID_LOWER = 0.80
MIN_CONFIDENCE_VIEWS = 200


class OptimizerService:
    """Recommendation-first optimization engine.

    All plan methods are read-only and return a list of
    OptimizationDecision objects. Apply methods re-run the plan
    and execute mutations through underlying services.

    Attributes:
        campaign_svc: Campaign lifecycle service.
        bid_svc: Bid management service.
        cluster_svc: Search cluster service.
        stats_svc: Campaign statistics service.
        budget_svc: Budget management service.
    """

    def __init__(
            self,
            campaign_svc: CampaignService,
            bid_svc: BidService,
            cluster_svc: ClusterService,
            stats_svc: StatsService,
            budget_svc: BudgetService,
    ) -> None:
        self._campaign_svc = campaign_svc
        self._bid_svc = bid_svc
        self._cluster_svc = cluster_svc
        self._stats_svc = stats_svc
        self._budget_svc = budget_svc

    # ── Plan methods (read-only) ─────────────────────────────────────

    def plan_all(
            self,
            campaign_id: int,
            nm_id: int,
            date_from: str,
            date_to: str,
    ) -> list[OptimizationDecision]:
        """Generate full optimization plan for a campaign.

        Args:
            campaign_id: Target campaign identifier.
            nm_id: Product nomenclature ID.
            date_from: Stats period start (YYYY-MM-DD).
            date_to: Stats period end (YYYY-MM-DD).

        Returns:
            Combined list of all optimization decisions.
        """
        decisions: list[OptimizationDecision] = []
        decisions.extend(
            self.plan_clusters(campaign_id, nm_id, date_from, date_to)
        )
        decisions.extend(self.plan_budget(campaign_id))
        return decisions

    def plan_clusters(
            self,
            campaign_id: int,
            nm_id: int,
            date_from: str,
            date_to: str,
    ) -> list[OptimizationDecision]:
        """Generate cluster bid optimization decisions.

        Args:
            campaign_id: Target campaign identifier.
            nm_id: Product nomenclature ID.
            date_from: Stats period start (YYYY-MM-DD).
            date_to: Stats period end (YYYY-MM-DD).

        Returns:
            List of cluster bid decisions.
        """
        stats = self._cluster_svc.get_cluster_stats(
            campaign_id, nm_id, date_from, date_to,
        )
        bids = self._cluster_svc.get_cluster_bids(campaign_id, nm_id)
        bid_map = {b.norm_query: b.bid for b in bids}

        decisions: list[OptimizationDecision] = []
        for s in stats:
            if s.views < MIN_VIEWS:
                continue
            current_bid = bid_map.get(s.norm_query, 0)
            confidence = _view_confidence(s.views)
            cluster_class = _classify_cluster(s)

            decision = _cluster_decision(
                cluster_class, s, current_bid, nm_id, confidence,
            )
            if decision:
                decisions.append(decision)

        return decisions

    def plan_budget(
            self, campaign_id: int,
    ) -> list[OptimizationDecision]:
        """Generate budget optimization decisions.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            List of budget decisions (at most one).
        """
        budget = self._budget_svc.get_budget(campaign_id)
        if budget.total <= 0:
            return []

        utilization = 1.0 - (budget.cash / budget.total) if budget.total else 0
        if utilization >= BUDGET_ALERT:
            topup = int(budget.total * 0.5)
            return [OptimizationDecision(
                action=OptimizationAction.TOPUP_BUDGET,
                target_type=TargetType.CAMPAIGN,
                target_id=str(campaign_id),
                current_value=f'{budget.cash}/{budget.total}',
                proposed_value=str(topup),
                reason=(
                    f'Budget {utilization:.0%} used '
                    f'({budget.cash} remaining of {budget.total}) — '
                    f'at risk of exhaustion'
                ),
                confidence=0.9,
            )]
        return []

    def plan_negatives(
            self,
            campaign_id: int,
            nm_id: int,
            date_from: str,
            date_to: str,
    ) -> list[OptimizationDecision]:
        """Generate minus phrase recommendations.

        Args:
            campaign_id: Target campaign identifier.
            nm_id: Product nomenclature ID.
            date_from: Stats period start (YYYY-MM-DD).
            date_to: Stats period end (YYYY-MM-DD).

        Returns:
            List of add_minus_phrase decisions.
        """
        stats = self._cluster_svc.get_cluster_stats(
            campaign_id, nm_id, date_from, date_to,
        )
        return [
            OptimizationDecision(
                action=OptimizationAction.ADD_MINUS_PHRASE,
                target_type=TargetType.CLUSTER,
                target_id=s.norm_query,
                nm_id=nm_id,
                current_value=f'spend={s.spend}, orders={s.orders}',
                reason=(
                    f'Cluster "{s.norm_query}" spent {s.spend} '
                    f'with {s.orders} orders — exclusion candidate'
                ),
                confidence=_view_confidence(s.views),
            )
            for s in stats
            if s.views >= MIN_VIEWS
            and s.spend >= WASTE_SPEND
            and s.orders == 0
        ]

    def plan_portfolio(
            self,
            campaign_id: int,
            date_from: str,
            date_to: str,
    ) -> list[OptimizationDecision]:
        """Generate product portfolio decisions.

        Args:
            campaign_id: Target campaign identifier.
            date_from: Stats period start (YYYY-MM-DD).
            date_to: Stats period end (YYYY-MM-DD).

        Returns:
            List of item-level decisions (remove, lower bid).
        """
        campaign_stats = self._stats_svc.get_campaign_stats(
            campaign_id, date_from, date_to,
        )
        decisions: list[OptimizationDecision] = []

        if campaign_stats.clicks > 0 and campaign_stats.orders == 0:
            decisions.append(OptimizationDecision(
                action=OptimizationAction.PAUSE_CAMPAIGN,
                target_type=TargetType.CAMPAIGN,
                target_id=str(campaign_id),
                current_value=(
                    f'clicks={campaign_stats.clicks}, '
                    f'orders={campaign_stats.orders}'
                ),
                reason=(
                    f'Campaign has {campaign_stats.clicks} clicks '
                    f'but 0 orders — may need product review'
                ),
                confidence=_view_confidence(campaign_stats.views),
            ))

        return decisions

    # ── Apply methods ────────────────────────────────────────────────

    def apply_clusters(
            self,
            campaign_id: int,
            nm_id: int,
            date_from: str,
            date_to: str,
            dry_run: bool = False,
    ) -> list[MutationResult]:
        """Run cluster plan and apply mutations.

        Args:
            campaign_id: Target campaign identifier.
            nm_id: Product nomenclature ID.
            date_from: Stats period start.
            date_to: Stats period end.
            dry_run: If True, simulate without executing.

        Returns:
            List of MutationResult objects.
        """
        decisions = self.plan_clusters(
            campaign_id, nm_id, date_from, date_to,
        )
        return [
            self._apply_decision(d, campaign_id, dry_run)
            for d in decisions
        ]

    def apply_budget(
            self,
            campaign_id: int,
            dry_run: bool = False,
    ) -> list[MutationResult]:
        """Run budget plan and apply mutations.

        Args:
            campaign_id: Target campaign identifier.
            dry_run: If True, simulate without executing.

        Returns:
            List of MutationResult objects.
        """
        decisions = self.plan_budget(campaign_id)
        return [
            self._apply_decision(d, campaign_id, dry_run)
            for d in decisions
        ]

    def apply_negatives(
            self,
            campaign_id: int,
            nm_id: int,
            date_from: str,
            date_to: str,
            dry_run: bool = False,
    ) -> list[MutationResult]:
        """Run negatives plan and apply mutations.

        Args:
            campaign_id: Target campaign identifier.
            nm_id: Product nomenclature ID.
            date_from: Stats period start.
            date_to: Stats period end.
            dry_run: If True, simulate without executing.

        Returns:
            List of MutationResult objects.
        """
        decisions = self.plan_negatives(
            campaign_id, nm_id, date_from, date_to,
        )
        if not decisions:
            return []

        phrases = [d.target_id for d in decisions]
        result = self._cluster_svc.set_minus_phrases(
            campaign_id, nm_id, phrases, dry_run=dry_run,
        )
        return [result]

    def apply_all(
            self,
            campaign_id: int,
            nm_id: int,
            date_from: str,
            date_to: str,
            dry_run: bool = False,
    ) -> list[MutationResult]:
        """Run full plan and apply all mutations.

        Args:
            campaign_id: Target campaign identifier.
            nm_id: Product nomenclature ID.
            date_from: Stats period start.
            date_to: Stats period end.
            dry_run: If True, simulate without executing.

        Returns:
            List of MutationResult objects.
        """
        results: list[MutationResult] = []
        results.extend(
            self.apply_clusters(
                campaign_id, nm_id, date_from, date_to, dry_run,
            )
        )
        results.extend(self.apply_budget(campaign_id, dry_run))
        return results

    # ── Private helpers ──────────────────────────────────────────────

    def _apply_decision(
            self,
            decision: OptimizationDecision,
            campaign_id: int,
            dry_run: bool,
    ) -> MutationResult:
        """Route a single decision to the appropriate service.

        Args:
            decision: The optimization decision to apply.
            campaign_id: Target campaign identifier.
            dry_run: If True, simulate without executing.

        Returns:
            MutationResult from the underlying service.
        """
        match decision.action:
            case (OptimizationAction.RAISE_CLUSTER_BID
                  | OptimizationAction.LOWER_CLUSTER_BID):
                bid = int(decision.proposed_value or '0')
                mutation = ClusterBidMutation(
                    nm_id=decision.nm_id,
                    norm_query=decision.target_id,
                    bid=bid,
                )
                return self._cluster_svc.set_cluster_bids(
                    campaign_id, [mutation], dry_run=dry_run,
                )
            case OptimizationAction.DELETE_CLUSTER_BID:
                bid = int(decision.current_value or '0')
                mutation = ClusterBidMutation(
                    nm_id=decision.nm_id,
                    norm_query=decision.target_id,
                    bid=bid,
                )
                return self._cluster_svc.delete_cluster_bids(
                    campaign_id, [mutation], dry_run=dry_run,
                )
            case OptimizationAction.TOPUP_BUDGET:
                amount = int(decision.proposed_value or '0')
                return self._budget_svc.topup(
                    campaign_id, amount, dry_run=dry_run,
                )
            case OptimizationAction.PAUSE_CAMPAIGN:
                return self._campaign_svc.pause_campaign(
                    campaign_id, dry_run=dry_run,
                )
            case _:
                return MutationResult(
                    success=False,
                    action=decision.action.value,
                    target_id=decision.target_id,
                    message=f'Action {decision.action.value} not yet supported',
                )


# ── Module-level helpers ─────────────────────────────────────────────


def _view_confidence(views: int) -> float:
    """Calculate confidence score based on view count.

    Args:
        views: Number of impressions.

    Returns:
        Confidence score between 0.0 and 1.0.
    """
    if views >= MIN_CONFIDENCE_VIEWS:
        return 1.0
    return round(views / MIN_CONFIDENCE_VIEWS, 2)


def _classify_cluster(stats) -> ClusterClass:
    """Classify a cluster based on its statistics.

    Args:
        stats: ClusterStats object.

    Returns:
        ClusterClass classification.
    """
    has_orders = stats.orders > 0
    high_ctr = stats.ctr >= HIGH_CTR
    low_ctr = stats.ctr < LOW_CTR
    poor_position = stats.avg_pos > MAX_AVG_POS
    is_wasteful = stats.spend >= WASTE_SPEND and not has_orders

    if has_orders and high_ctr and poor_position:
        return ClusterClass.EFFICIENT
    if has_orders and high_ctr:
        return ClusterClass.EFFICIENT
    if stats.views >= MIN_VIEWS and low_ctr:
        return ClusterClass.VISIBLE_WEAK
    if is_wasteful and low_ctr:
        return ClusterClass.NOISY_EXCLUSION
    if is_wasteful:
        return ClusterClass.EXPENSIVE_NON_CONVERTING

    return ClusterClass.INACTIVE_PROMISING


def _cluster_decision(
        cluster_class: ClusterClass,
        stats,
        current_bid: int,
        nm_id: int,
        confidence: float,
) -> OptimizationDecision | None:
    """Generate a decision for a classified cluster.

    Args:
        cluster_class: Classification result.
        stats: ClusterStats object.
        current_bid: Current bid in kopecks.
        nm_id: Product nomenclature ID.
        confidence: Data confidence score.

    Returns:
        An OptimizationDecision or None if no action needed.
    """
    match cluster_class:
        case ClusterClass.EFFICIENT:
            if current_bid <= 0:
                return None
            new_bid = max(1, int(current_bid * BID_RAISE))
            return OptimizationDecision(
                action=OptimizationAction.RAISE_CLUSTER_BID,
                target_type=TargetType.CLUSTER,
                target_id=stats.norm_query,
                nm_id=nm_id,
                current_value=str(current_bid),
                proposed_value=str(new_bid),
                reason=(
                    f'Cluster "{stats.norm_query}" has strong '
                    f'CTR {stats.ctr:.1f}% with {stats.orders} '
                    f'orders — raise bid for better position'
                ),
                confidence=confidence,
            )
        case ClusterClass.VISIBLE_WEAK:
            if current_bid <= 0:
                return None
            new_bid = max(1, int(current_bid * BID_LOWER))
            return OptimizationDecision(
                action=OptimizationAction.LOWER_CLUSTER_BID,
                target_type=TargetType.CLUSTER,
                target_id=stats.norm_query,
                nm_id=nm_id,
                current_value=str(current_bid),
                proposed_value=str(new_bid),
                reason=(
                    f'Cluster "{stats.norm_query}" has '
                    f'{stats.views} views but CTR only '
                    f'{stats.ctr:.1f}% — reduce bid'
                ),
                confidence=confidence,
            )
        case ClusterClass.EXPENSIVE_NON_CONVERTING:
            return OptimizationDecision(
                action=OptimizationAction.DELETE_CLUSTER_BID,
                target_type=TargetType.CLUSTER,
                target_id=stats.norm_query,
                nm_id=nm_id,
                current_value=str(current_bid),
                reason=(
                    f'Cluster "{stats.norm_query}" spent '
                    f'{stats.spend} with 0 orders — remove bid'
                ),
                confidence=confidence,
            )
        case ClusterClass.NOISY_EXCLUSION:
            return OptimizationDecision(
                action=OptimizationAction.ADD_MINUS_PHRASE,
                target_type=TargetType.CLUSTER,
                target_id=stats.norm_query,
                nm_id=nm_id,
                current_value=f'spend={stats.spend}',
                reason=(
                    f'Cluster "{stats.norm_query}" is noisy — '
                    f'low CTR {stats.ctr:.1f}% with spend '
                    f'{stats.spend} — exclude'
                ),
                confidence=confidence,
            )
        case _:
            return None
