"""Domain models for WB CLI - normalized representations of WB API objects."""

from __future__ import annotations

from dataclasses import dataclass, field

from wb.domain.enums import (
    CampaignStatus,
    CampaignType,
    OptimizationAction,
    PaymentType,
    TargetType,
)

__all__ = [
    'Campaign',
    'ProductCard',
    'ItemBid',
    'SearchCluster',
    'ClusterBidMutation',
    'BudgetSnapshot',
    'NmStats',
    'DayStats',
    'CampaignStats',
    'ClusterStats',
    'MinusPhraseSet',
    'OptimizationDecision',
    'AccountBalance',
    'RecommendedBid',
    'MinimumBid',
    'CurrentBid',
    'MutationResult',
    'CampaignCreate',
    'BidMutation',
    'PlacementConfig',
    'ProductPriceSize',
    'ProductPrice',
    'ProductSummary',
    'CampaignOverview',
    'DailyReportRow',
    'PortalProductCard',
    'ReachTier',
    'PortalBidRecommendation',
    'parse_portal_bids_response',
]


@dataclass(slots=True)
class Campaign:
    """Normalized campaign representation.

    Attributes:
        campaign_id: WB campaign identifier.
        name: Campaign display name.
        status: Current campaign lifecycle status.
        campaign_type: Type of campaign.
        payment_type: Billing model (CPM/CPC).
        bid_type: Bid strategy ('manual' or 'unified').
        currency: Currency code.
        daily_budget: Daily budget in kopecks.
        nm_ids: Product NM IDs included in this campaign.
        start_time: ISO timestamp of campaign start.
        updated_time: ISO timestamp of last update.
        create_time: ISO timestamp of creation.
    """

    campaign_id: int
    name: str
    status: CampaignStatus
    campaign_type: CampaignType
    payment_type: PaymentType
    bid_type: str = 'manual'
    currency: str = 'RUB'
    daily_budget: int = 0
    nm_ids: list[int] = field(default_factory=list)
    start_time: str | None = None
    updated_time: str | None = None
    create_time: str | None = None

    @classmethod
    def from_api(cls, data: dict) -> Campaign:
        """Create from WB /api/advert/v2/adverts response payload."""
        settings = data.get('settings', {})
        timestamps = data.get('timestamps', {})
        nm_settings = data.get('nm_settings') or []
        nm_ids = [item['nm_id'] for item in nm_settings if 'nm_id' in item]
        return cls(
            campaign_id=data['id'],
            name=settings.get('name', ''),
            status=CampaignStatus(data['status']),
            campaign_type=CampaignType(data.get('type', 9)),
            payment_type=PaymentType(settings.get('payment_type') or 'cpm'),
            bid_type=data.get('bid_type', 'manual'),
            currency=data.get('currency', 'RUB'),
            nm_ids=nm_ids,
            start_time=timestamps.get('started'),
            updated_time=timestamps.get('updated'),
            create_time=timestamps.get('created'),
        )


@dataclass(slots=True)
class ProductCard:
    """A product card eligible for campaign inclusion.

    Attributes:
        nm_id: WB nomenclature (product) ID.
        name: Product display name.
        subject_id: Subject category ID.
        subject_name: Subject category name.
    """

    nm_id: int
    name: str
    subject_id: int = 0
    subject_name: str = ''

    @classmethod
    def from_api(cls, data: dict) -> ProductCard:
        """Create from WB API response payload."""
        return cls(
            nm_id=data['nmId'],
            name=data.get('name', ''),
            subject_id=data.get('subjectId', 0),
            subject_name=data.get('subjectName', ''),
        )


@dataclass(slots=True)
class ItemBid:
    """Bid setting for a product card within a campaign.

    Attributes:
        nm_id: Product nomenclature ID.
        bid: Current bid value.
        recommended_bid: Platform-recommended bid.
        minimum_bid: Platform minimum bid.
    """

    nm_id: int
    bid: int
    recommended_bid: int = 0
    minimum_bid: int = 0

    @classmethod
    def from_api(cls, data: dict) -> ItemBid:
        """Create from WB API response payload."""
        return cls(
            nm_id=data['nmId'],
            bid=data.get('bid', 0),
            recommended_bid=data.get('recommendedBid', 0),
            minimum_bid=data.get('minimumBid', 0),
        )


@dataclass(slots=True)
class SearchCluster:
    """A search cluster (normquery) attached to a campaign + product pair.

    Attributes:
        norm_query: Normalized query string (cluster identifier).
        cluster_id: Legacy cluster ID (kept for backward compat).
        is_active: Whether the cluster is currently active.
        bid: Current bid on this cluster in kopecks.
        nm_id: Product nomenclature ID associated with this cluster.
    """

    norm_query: str
    cluster_id: int = 0
    is_active: bool = True
    bid: int = 0
    nm_id: int = 0

    @classmethod
    def from_api(cls, data: dict, is_active: bool = True) -> SearchCluster:
        """Create from WB API normquery/list response payload.

        Args:
            data: Raw API dict for a cluster.
            is_active: Whether this cluster is active.
        """
        return cls(
            norm_query=data.get('norm_query', ''),
            cluster_id=data.get('id', 0),
            is_active=is_active,
            bid=data.get('bid', 0),
            nm_id=data.get('nm_id', 0),
        )

    @classmethod
    def from_normquery_list(
        cls, phrase: str, is_active: bool = True,
    ) -> SearchCluster:
        """Create from a plain phrase string in normquery list arrays.

        Args:
            phrase: The normalized query phrase string.
            is_active: Whether the phrase is in the active list.
        """
        return cls(norm_query=phrase, is_active=is_active)

    @classmethod
    def from_bid_api(cls, data: dict) -> SearchCluster:
        """Create from /adv/v0/normquery/get-bids response item.

        Args:
            data: Raw API dict with advert_id, bid, nm_id, norm_query.
        """
        return cls(
            norm_query=data.get('norm_query', ''),
            bid=data.get('bid', 0),
            nm_id=data.get('nm_id', 0),
        )


@dataclass(slots=True)
class ClusterBidMutation:
    """A bid change for a search cluster in a campaign.

    Attributes:
        nm_id: Product nomenclature ID.
        norm_query: Normalized query string (cluster identifier).
        bid: New bid value in kopecks.
    """

    nm_id: int
    norm_query: str
    bid: int

    def to_api(self, campaign_id: int) -> dict:
        """Serialize to WB API POST /adv/v0/normquery/bids payload item.

        Args:
            campaign_id: Campaign this bid belongs to.
        """
        return {
            'advert_id': campaign_id,
            'nm_id': self.nm_id,
            'norm_query': self.norm_query,
            'bid': self.bid,
        }


@dataclass(slots=True)
class BudgetSnapshot:
    """Campaign budget state at a point in time.

    Attributes:
        campaign_id: Campaign identifier.
        total: Total budget allocated.
        cash: Cash portion of the budget.
        netting: Netting portion of the budget.
        currency: Currency code.
    """

    campaign_id: int
    total: int = 0
    cash: int = 0
    netting: int = 0
    currency: str = ''

    @classmethod
    def from_api(cls, data: dict, campaign_id: int) -> BudgetSnapshot:
        """Create from WB API response payload.

        Args:
            data: Raw API dict for budget.
            campaign_id: Campaign this budget belongs to.
        """
        return cls(
            campaign_id=campaign_id,
            total=data.get('total', 0),
            cash=data.get('cash', 0),
            netting=data.get('netting', 0),
            currency=data.get('currency', ''),
        )


@dataclass(slots=True)
class NmStats:
    """Per-product (NM ID) statistics within a campaign.

    Attributes:
        nm_id: Product nomenclature ID.
        name: Product display name.
        views: Total impressions.
        clicks: Total clicks.
        ctr: Click-through rate.
        orders: Total orders.
        spend: Total ad spend (rubles).
        cpc: Cost per click.
        cr: Conversion rate.
        atbs: Add-to-basket count.
        shks: Units shipped.
        avg_position: Average search position from booster stats (0 = unknown).
    """

    nm_id: int
    name: str = ''
    views: int = 0
    clicks: int = 0
    ctr: float = 0.0
    orders: int = 0
    spend: float = 0.0
    cpc: float = 0.0
    cr: float = 0.0
    atbs: int = 0
    shks: int = 0
    avg_position: float = 0.0

    @classmethod
    def from_api(cls, data: dict) -> NmStats:
        """Create from a single NM entry in fullstats response."""
        return cls(
            nm_id=data.get('nmId', 0),
            name=data.get('name', ''),
            views=data.get('views', 0),
            clicks=data.get('clicks', 0),
            ctr=data.get('ctr', 0.0),
            orders=data.get('orders', 0),
            spend=data.get('sum', 0.0),
            cpc=data.get('cpc', 0.0),
            cr=data.get('cr', 0.0),
            atbs=data.get('atbs', 0),
            shks=data.get('shks', 0),
        )


@dataclass(slots=True)
class DayStats:
    """Per-day statistics with per-NM breakdown.

    Attributes:
        date: ISO date string for this day.
        views: Total views for the day.
        clicks: Total clicks for the day.
        orders: Total orders for the day.
        spend: Total spend for the day (rubles).
        nm_stats: Per-product breakdown for this day.
    """

    date: str
    views: int = 0
    clicks: int = 0
    orders: int = 0
    spend: float = 0.0
    nm_stats: list[NmStats] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> DayStats:
        """Create from a single day entry in fullstats response."""
        nm_map: dict[int, NmStats] = {}
        for app_entry in data.get('apps', []):
            for nm_data in app_entry.get('nms', []):
                nm_id = nm_data.get('nmId', 0)
                if nm_id in nm_map:
                    existing = nm_map[nm_id]
                    existing.views += nm_data.get('views', 0)
                    existing.clicks += nm_data.get('clicks', 0)
                    existing.orders += nm_data.get('orders', 0)
                    existing.spend += nm_data.get('sum', 0.0)
                    existing.atbs += nm_data.get('atbs', 0)
                    existing.shks += nm_data.get('shks', 0)
                else:
                    nm_map[nm_id] = NmStats.from_api(nm_data)
        return cls(
            date=data.get('date', ''),
            views=data.get('views', 0),
            clicks=data.get('clicks', 0),
            orders=data.get('orders', 0),
            spend=data.get('sum', 0.0),
            nm_stats=list(nm_map.values()),
        )


def _aggregate_nm_totals(days: list) -> dict:
    """Aggregate per-NM stats across all days in a fullstats response.

    Args:
        days: List of DayStats objects already parsed from API response.

    Returns:
        Dict mapping nm_id → NmStats with totals summed across all days.
    """
    nm_totals: dict[int, NmStats] = {}
    for day in days:
        for nm in day.nm_stats:
            if nm.nm_id in nm_totals:
                t = nm_totals[nm.nm_id]
                t.views += nm.views
                t.clicks += nm.clicks
                t.orders += nm.orders
                t.spend += nm.spend
                t.atbs += nm.atbs
                t.shks += nm.shks
            else:
                nm_totals[nm.nm_id] = NmStats(
                    nm_id=nm.nm_id, name=nm.name,
                    views=nm.views, clicks=nm.clicks,
                    orders=nm.orders, spend=nm.spend,
                    atbs=nm.atbs, shks=nm.shks,
                )
    return nm_totals


def _apply_booster_stats(
        nm_totals: dict,
        booster_raw: list[dict],
) -> None:
    """Inject avg_position from boosterStats[] into the NmStats map.

    WB API uses 'nm' as the NM key in boosterStats entries.

    Args:
        nm_totals: Dict mapping nm_id → NmStats (mutated in-place).
        booster_raw: Raw boosterStats list from fullstats API response.
    """
    for entry in booster_raw:
        nm_id = entry.get('nm', entry.get('nm_id', 0))
        if nm_id and nm_id in nm_totals:
            nm_totals[nm_id].avg_position = float(
                entry.get('avg_position', 0.0)
            )


@dataclass(slots=True)
class CampaignStats:
    """Aggregated campaign statistics for a date range.

    Attributes:
        campaign_id: Campaign identifier.
        views: Total impressions/views.
        clicks: Total clicks.
        ctr: Click-through rate.
        orders: Total orders attributed.
        spend: Total spend in rubles.
        cpc: Cost per click.
        cr: Conversion rate.
        atbs: Add-to-basket count.
        shks: Units shipped.
        currency: Currency code.
        days: Per-day breakdown with per-NM stats.
        nm_stats: Aggregated per-NM stats across all days.
    """

    campaign_id: int
    views: int = 0
    clicks: int = 0
    ctr: float = 0.0
    orders: int = 0
    spend: float = 0.0
    cpc: float = 0.0
    cr: float = 0.0
    atbs: int = 0
    shks: int = 0
    currency: str = 'RUB'
    days: list[DayStats] = field(default_factory=list)
    nm_stats: list[NmStats] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> CampaignStats:
        """Create from WB API /adv/v3/fullstats response payload.

        Parses the nested days[].apps[].nms[] structure, aggregates
        per-NM totals across all days, and applies boosterStats positions.
        """
        days = [DayStats.from_api(d) for d in data.get('days', [])]
        nm_totals = _aggregate_nm_totals(days)
        _apply_booster_stats(nm_totals, data.get('boosterStats', []))
        return cls(
            campaign_id=data.get('advertId', 0),
            views=data.get('views', 0),
            clicks=data.get('clicks', 0),
            ctr=data.get('ctr', 0.0),
            orders=data.get('orders', 0),
            spend=data.get('sum', 0.0),
            cpc=data.get('cpc', 0.0),
            cr=data.get('cr', 0.0),
            atbs=data.get('atbs', 0),
            shks=data.get('shks', 0),
            currency=data.get('currency', 'RUB'),
            days=days,
            nm_stats=list(nm_totals.values()),
        )


@dataclass(slots=True)
class ClusterStats:
    """Statistics for a single search cluster (normquery).

    Attributes:
        norm_query: Normalized query string.
        views: Impressions.
        clicks: Clicks.
        ctr: Click-through rate.
        cpc: Cost per click.
        cpm: Cost per mille.
        orders: Orders.
        spend: Spend in kopecks.
        avg_pos: Average position.
        atbs: Add-to-basket count.
        shks: Units shipped.
        currency: Currency code.
    """

    norm_query: str = ''
    views: int = 0
    clicks: int = 0
    ctr: float = 0.0
    cpc: float = 0.0
    cpm: float = 0.0
    orders: int = 0
    spend: int = 0
    avg_pos: float = 0.0
    atbs: int = 0
    shks: int = 0
    currency: str = 'RUB'

    @classmethod
    def from_api(cls, data: dict) -> ClusterStats:
        """Create from WB API normquery stats response payload."""
        return cls(
            norm_query=data.get('norm_query', ''),
            views=data.get('views', 0),
            clicks=data.get('clicks', 0),
            ctr=data.get('ctr', 0.0),
            cpc=data.get('cpc', 0.0),
            cpm=data.get('cpm', 0.0),
            orders=data.get('orders', 0),
            spend=data.get('spend', 0),
            avg_pos=data.get('avg_pos', 0.0),
            atbs=data.get('atbs', 0),
            shks=data.get('shks', 0),
            currency=data.get('currency', 'RUB'),
        )


@dataclass(slots=True)
class MinusPhraseSet:
    """Set of minus phrases for a campaign + product pair.

    Attributes:
        campaign_id: Campaign identifier.
        nm_id: Product nomenclature ID.
        phrases: List of excluded phrases (norm_queries).
    """

    campaign_id: int
    nm_id: int
    phrases: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> MinusPhraseSet:
        """Create from WB API get-minus response payload.

        Args:
            data: Raw API dict with advert_id, nm_id, norm_queries.
        """
        return cls(
            campaign_id=data.get('advert_id', 0),
            nm_id=data.get('nm_id', 0),
            phrases=data.get('norm_queries', []),
        )

    def to_api(self) -> dict:
        """Serialize to WB API set-minus request payload."""
        return {
            'advert_id': self.campaign_id,
            'nm_id': self.nm_id,
            'norm_queries': self.phrases,
        }


@dataclass(slots=True)
class OptimizationDecision:
    """A recommended optimization action.

    Attributes:
        action: Type of action (raise_bid, lower_bid, add_minus, etc.).
        target_type: What the action targets (campaign, item, cluster).
        target_id: Identifier of the target (norm_query, nm_id, etc.).
        nm_id: Product nomenclature ID (for item/cluster scoped decisions).
        current_value: Current state value (as string for display).
        proposed_value: Proposed new value (as string for display).
        reason: Explainable rationale for the recommendation.
        confidence: Confidence score 0.0-1.0 based on data sufficiency.
    """

    action: OptimizationAction
    target_type: TargetType
    target_id: str
    nm_id: int = 0
    current_value: str | None = None
    proposed_value: str | None = None
    reason: str = ''
    confidence: float = 0.0


@dataclass(slots=True)
class AccountBalance:
    """Account-level financial balance.

    Attributes:
        balance: Available balance in kopecks.
        net: Net amount.
        bonus: Bonus balance.
        currency: Currency code.
        cashbacks: List of cashback entries.
    """

    balance: int = 0
    net: int = 0
    bonus: int = 0
    currency: str = 'RUB'
    cashbacks: list[dict] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> AccountBalance:
        """Create from WB API /adv/v1/account/balance response."""
        return cls(
            balance=data.get('balance', 0),
            net=data.get('net', 0),
            bonus=data.get('bonus', 0),
            currency=data.get('currency', 'RUB'),
            cashbacks=data.get('cashbacks', []),
        )


@dataclass(slots=True)
class MutationResult:
    """Result of a mutating API operation.

    Attributes:
        success: Whether the mutation succeeded (or would succeed).
        action: Human-readable description of the action performed.
        target_id: ID of the affected object.
        dry_run: True when the mutation was simulated only.
        message: Additional detail or confirmation message.
        already_applied: True when the desired state was already active
            and no API call was made (idempotent check).
    """

    success: bool
    action: str
    target_id: str
    dry_run: bool = False
    message: str = ''
    already_applied: bool = False


@dataclass(slots=True)
class CampaignCreate:
    """Parameters for creating a new campaign via /adv/v2/seacat/save-ad.

    Attributes:
        name: Campaign display name.
        nm_ids: Product nomenclature IDs to include.
        bid_type: Bid strategy ('manual' or 'unified').
        placement_types: Placement types to enable.
    """

    name: str
    nm_ids: list[int] = field(default_factory=list)
    bid_type: str = 'manual'
    placement_types: list[str] = field(default_factory=lambda: ['search'])

    def to_api(self) -> dict:
        """Serialize to WB API /adv/v2/seacat/save-ad payload."""
        payload: dict = {
            'name': self.name,
            'nms': self.nm_ids,
            'bid_type': self.bid_type,
        }
        if self.bid_type != 'unified':
            payload['placement_types'] = self.placement_types
        return payload


@dataclass(slots=True)
class BidMutation:
    """A bid change for product cards in a campaign.

    Attributes:
        nm_id: Product nomenclature ID.
        bid_kopecks: New bid value in kopecks.
        placement: Placement type ('search', 'recommendations', 'combined').
    """

    nm_id: int
    bid_kopecks: int
    placement: str = 'search'

    def to_api(self, campaign_id: int) -> dict:
        """Serialize to WB API PATCH /api/advert/v1/bids payload.

        Args:
            campaign_id: Campaign this bid belongs to.
        """
        return {
            'advert_id': campaign_id,
            'nm_bids': [
                {
                    'nm_id': self.nm_id,
                    'bid_kopecks': self.bid_kopecks,
                    'placement': self.placement,
                },
            ],
        }


@dataclass(slots=True)
class PlacementConfig:
    """Placement configuration for a campaign.

    Attributes:
        search_enabled: Whether search placement is active.
        recommendations_enabled: Whether recommendations placement is active.
    """

    search_enabled: bool = True
    recommendations_enabled: bool = False

    def to_api(self, campaign_id: int) -> dict:
        """Serialize to PUT /adv/v0/auction/placements payload item.

        Args:
            campaign_id: Campaign to apply placements to.
        """
        return {
            'advert_id': campaign_id,
            'placements': {
                'search': self.search_enabled,
                'recommendations': self.recommendations_enabled,
            },
        }


@dataclass(slots=True)
class RecommendedBid:
    """Platform-recommended bid for one product in a CPM campaign.

    Source: ``GET /api/advert/v0/bids/recommendations?nmId=&advertId=``.
    All bid values are in kopecks; ``error`` is non-None when WB rejected
    this NM (e.g. delisted item) so the caller can surface partial failures
    without losing the rest of the loop's results.

    Attributes:
        campaign_id: Campaign identifier (``advertId``).
        nm_id: Product nomenclature ID (``nmId``).
        competitive: ``base.competitiveBid.bidKopecks`` — the median bid.
        leaders: ``base.leadersBid.bidKopecks`` — bid for top positions.
        top2: ``base.top2.bidKopecks`` — bid to occupy the TOP-2 slot.
        error: WB error message when this NM could not be queried.
    """

    campaign_id: int
    nm_id: int = 0
    competitive: int = 0
    leaders: int = 0
    top2: int = 0
    error: str | None = None

    @classmethod
    def from_api(cls, data: dict, campaign_id: int) -> RecommendedBid:
        """Create from a ``/v0/bids/recommendations`` response object.

        Args:
            data: Raw API dict — ``{advertId, nmId, base: {competitiveBid,
                leadersBid, top2}, normQueries: […]}``.
            campaign_id: Campaign this recommendation belongs to.
        """
        base = data.get('base') or {}
        competitive = (base.get('competitiveBid') or {}).get('bidKopecks', 0)
        leaders = (base.get('leadersBid') or {}).get('bidKopecks', 0)
        top2 = (base.get('top2') or {}).get('bidKopecks', 0)
        return cls(
            campaign_id=campaign_id,
            nm_id=data.get('nmId', 0),
            competitive=competitive,
            leaders=leaders,
            top2=top2,
        )


@dataclass(slots=True)
class MinimumBid:
    """Minimum allowed bid for one product across placements.

    Source: ``POST /api/advert/v1/bids/min``. Values are in kopecks.

    Attributes:
        campaign_id: Campaign identifier (``advert_id``).
        nm_id: Product nomenclature ID.
        combined: Minimum bid for combined search+recommendation placement.
        search: Minimum bid for search placement.
        recommendation: Minimum bid for recommendation placement.
    """

    campaign_id: int
    nm_id: int = 0
    combined: int = 0
    search: int = 0
    recommendation: int = 0

    @classmethod
    def from_api(cls, data: dict, campaign_id: int) -> MinimumBid:
        """Create from a ``bids[]`` entry in /v1/bids/min response.

        Args:
            data: ``{nm_id, bids: [{type, value}]}`` per the swagger.
            campaign_id: Campaign these minimums belong to.
        """
        placements = {
            b['type']: b.get('value', 0)
            for b in (data.get('bids') or [])
            if 'type' in b
        }
        return cls(
            campaign_id=campaign_id,
            nm_id=data.get('nm_id', 0),
            combined=placements.get('combined', 0),
            search=placements.get('search', 0),
            recommendation=placements.get('recommendation', 0),
        )


@dataclass(slots=True)
class CurrentBid:
    """Current per-item bid for a campaign product.

    Source: ``GET /api/advert/v2/adverts`` — bids live in
    ``adverts[].nm_settings[].bids_kopecks.{search, recommendations}``.

    Attributes:
        campaign_id: Campaign identifier.
        nm_id: Product nomenclature ID.
        search: Current search placement bid, kopecks.
        recommendations: Current recommendation placement bid, kopecks.
    """

    campaign_id: int
    nm_id: int = 0
    search: int = 0
    recommendations: int = 0

    @classmethod
    def from_nm_setting(cls, nm: dict, campaign_id: int) -> CurrentBid:
        """Create from a single ``nm_settings[]`` entry.

        Args:
            nm: Raw nm_settings entry from /api/advert/v2/adverts.
            campaign_id: Campaign identifier.
        """
        bk = nm.get('bids_kopecks') or {}
        return cls(
            campaign_id=campaign_id,
            nm_id=nm.get('nm_id', 0),
            search=bk.get('search', 0),
            recommendations=bk.get('recommendations', 0),
        )


@dataclass(slots=True)
class PortalProductCard:
    """Product card data from the seller portal tableListv6 endpoint.

    Attributes:
        nm_id: WB article number (nmID).
        imt_id: Internal model type ID.
        vendor_code: Seller's vendor/article code.
        title: Product title.
        brand: Brand name.
        subject: Product category/subject.
        stocks: Total stock quantity.
        price: Current price in RUB.
        feedback_rating: Average feedback rating.
        feedback_count: Number of feedback reviews.
        card_rating: Card quality rating (0-10).
        tags: List of tag dicts with id, name, color.
        updated_at: Last update timestamp (ISO string).
    """

    nm_id: int
    imt_id: int
    vendor_code: str
    title: str
    brand: str
    subject: str
    stocks: int
    price: int
    feedback_rating: float
    feedback_count: int
    card_rating: float
    tags: list[dict[str, str]]
    updated_at: str

    @classmethod
    def from_portal(cls, data: dict) -> PortalProductCard:
        """Create from a raw portal tableListv6 card dict.

        Args:
            data: Raw card dict from the portal response.
        """
        sizes = data.get('sizes', [])
        price = sizes[0].get('currentPrice', 0) if sizes else 0
        feedbacks = data.get('feedbacks', {})
        rating_data = data.get('meta', {}).get('ratingData', {})

        return cls(
            nm_id=data.get('nmID', 0),
            imt_id=data.get('imtID', 0),
            vendor_code=data.get('vendorCode', ''),
            title=data.get('title', ''),
            brand=data.get('brand', ''),
            subject=data.get('subject', ''),
            stocks=data.get('stocks', 0),
            price=price,
            feedback_rating=feedbacks.get('rating', 0.0),
            feedback_count=feedbacks.get('count', 0),
            card_rating=rating_data.get('rating', 0.0),
            tags=data.get('tags', []),
            updated_at=data.get('updateAt', ''),
        )


@dataclass(slots=True)
class ProductPriceSize:
    """A single size entry from the Prices & Discounts API.

    Attributes:
        size_id: WB size identifier.
        price: Base price in currency units (before any discount).
        discounted_price: Final buyer-facing price after seller discount.
        club_discounted_price: WB Club member price.
        tech_size_name: Size label ('0' for non-sized items, 'XL', etc.).
    """

    size_id: int
    price: float
    discounted_price: float
    club_discounted_price: float
    tech_size_name: str = '0'

    @classmethod
    def from_api(cls, data: dict) -> ProductPriceSize:
        """Create from a sizes[] entry in the listGoods response.

        Args:
            data: Raw size dict from the Prices API response.
        """
        return cls(
            size_id=data.get('sizeID', 0),
            price=float(data.get('price', 0)),
            discounted_price=float(data.get('discountedPrice', 0)),
            club_discounted_price=float(data.get('clubDiscountedPrice', 0)),
            tech_size_name=data.get('techSizeName', '0'),
        )


@dataclass(slots=True)
class ProductPrice:
    """Normalized product price record from the Prices & Discounts API.

    For non-sized products, sizes contains exactly one entry.
    For clothing products, sizes may contain multiple entries.

    Convenience properties (base_price, final_price, club_price) always
    reflect the first size entry — the canonical price for non-sized goods
    and the first/default size for clothing.

    Attributes:
        nm_id: WB nomenclature ID (article number).
        vendor_code: Seller's own article/vendor code.
        currency_iso: ISO 4217 currency code (e.g. 'RUB').
        discount: Seller discount percentage applied across all sizes.
        club_discount: WB Club additional discount percentage (0 when none).
        editable_size_price: Whether per-size pricing is enabled.
        sizes: List of size-level price entries.
    """

    nm_id: int
    vendor_code: str
    currency_iso: str
    discount: int
    club_discount: int
    editable_size_price: bool
    sizes: list[ProductPriceSize] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> ProductPrice:
        """Create from a listGoods[] entry in the Prices API response.

        Args:
            data: Raw product dict from the listGoods array.
        """
        sizes = [ProductPriceSize.from_api(s) for s in data.get('sizes', [])]
        return cls(
            nm_id=data.get('nmID', 0),
            vendor_code=data.get('vendorCode', ''),
            currency_iso=data.get('currencyIsoCode4217', 'RUB'),
            discount=data.get('discount', 0),
            club_discount=data.get('clubDiscount', 0),
            editable_size_price=data.get('editableSizePrice', False),
            sizes=sizes,
        )

    @property
    def base_price(self) -> float:
        """Base price from the first size (before any discount)."""
        return self.sizes[0].price if self.sizes else 0.0

    @property
    def final_price(self) -> float:
        """Final buyer price from the first size (after seller discount)."""
        return self.sizes[0].discounted_price if self.sizes else 0.0

    @property
    def club_price(self) -> float:
        """WB Club member price from the first size."""
        return self.sizes[0].club_discounted_price if self.sizes else 0.0


@dataclass(slots=True)
class ProductSummary:
    """Composite per-product snapshot combining ad spend, funnel, price, and placement data.

    All optional data sources (prices, analytics) are best-effort: if the
    underlying service is unavailable, the affected fields remain at their
    default values rather than raising an error.

    Attributes:
        nm_id: WB nomenclature ID.
        vendor_code: Seller's vendor/article code.
        base_price: Pre-discount base price in rubles.
        final_price: Buyer-facing price after seller discount.
        discount: Seller discount percentage.
        ad_spend: Total ad spend across all campaigns (rubles).
        ad_views: Total ad impressions.
        ad_clicks: Total ad clicks.
        ad_orders: Total ad-attributed orders.
        ad_avg_position: Average search position from booster stats.
        open_count: Product page opens (analytics funnel).
        cart_count: Add-to-cart events.
        order_count: Orders from funnel analytics.
        order_sum: Order value sum (rubles).
        campaign_ids: IDs of campaigns containing this product.
        cluster_count: Total search clusters across all campaigns.
        active_cluster_count: Active search clusters across all campaigns.
        currency: Currency code.
    """

    nm_id: int
    vendor_code: str = ''
    base_price: float = 0.0
    final_price: float = 0.0
    discount: int = 0
    ad_spend: float = 0.0
    ad_views: int = 0
    ad_clicks: int = 0
    ad_orders: int = 0
    ad_avg_position: float = 0.0
    open_count: int = 0
    cart_count: int = 0
    order_count: int = 0
    order_sum: int = 0
    campaign_ids: list[int] = field(default_factory=list)
    cluster_count: int = 0
    active_cluster_count: int = 0
    currency: str = 'RUB'


@dataclass(slots=True)
class CampaignOverview:
    """Composite campaign snapshot combining details, budget, stats, and cluster data.

    Budget and stats fields are best-effort: if the underlying service call
    fails, the affected fields remain at their default values.

    Attributes:
        campaign_id: Campaign identifier.
        name: Campaign display name.
        status: Current lifecycle status.
        campaign_type: Type of campaign.
        nm_ids: Product NM IDs included in this campaign.
        total_budget: Total allocated budget in kopecks.
        cash: Cash portion of the budget in kopecks.
        netting: Netting portion of the budget in kopecks.
        views: Total impressions for the date range.
        clicks: Total clicks for the date range.
        ctr: Click-through rate.
        orders: Total orders attributed.
        spend: Total spend in rubles.
        cpc: Cost per click.
        nm_stats: Per-product breakdown.
        cluster_count: Total search clusters.
        active_cluster_count: Active search clusters.
        currency: Currency code.
    """

    campaign_id: int
    name: str
    status: CampaignStatus
    campaign_type: CampaignType
    nm_ids: list[int] = field(default_factory=list)
    total_budget: int = 0
    cash: int = 0
    netting: int = 0
    views: int = 0
    clicks: int = 0
    ctr: float = 0.0
    orders: int = 0
    spend: float = 0.0
    cpc: float = 0.0
    nm_stats: list[NmStats] = field(default_factory=list)
    cluster_count: int = 0
    active_cluster_count: int = 0
    currency: str = 'RUB'


@dataclass(slots=True)
class DailyReportRow:
    """Combined ad spend + platform orders row for a single product on a given date.

    Attributes:
        nm_id: WB nomenclature ID.
        name: Product display name.
        views: Ad impressions (Promotion API).
        clicks: Ad clicks (Promotion API).
        ad_orders: Orders attributed to advertising (Promotion API).
        spend: Total advertising spend in rubles (Promotion API).
        avg_position: Average search position from ad booster stats (0 = unknown).
        opens: Product page opens (Analytics funnel).
        cart_adds: Adds to cart (Analytics funnel).
        orders: Total platform orders from all channels (Analytics funnel).
        order_sum: Total order value in rubles (Analytics funnel).
        buyouts: Items purchased / bought out (Analytics funnel).
    """

    nm_id: int
    name: str = ''
    views: int = 0
    clicks: int = 0
    ad_orders: int = 0
    spend: float = 0.0
    avg_position: float = 0.0
    opens: int = 0
    cart_adds: int = 0
    orders: int = 0
    order_sum: int = 0
    buyouts: int = 0
