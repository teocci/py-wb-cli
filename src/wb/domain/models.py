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
    'JamReport',
    'CampaignFinanceEntry',
    'CampaignFinancePage',
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


@dataclass(slots=True)
class ReachTier:
    """Reach forecast tier from the unofficial portal bid endpoints.

    Each tier represents a (bid, projected-traffic) point WB suggests
    for one of three reach levels. A tier filled with zeros means WB
    has no forecast at that level for the queried NM (typically when
    historical impression data is missing).

    Attributes:
        bid: Suggested bid in kopecks (0 = no forecast).
        min: Per-tier floor in kopecks; mostly 0 in observed samples.
        budget: Projected daily budget in kopecks at this bid/tier.
        shows: Projected daily impressions at this bid/tier.
        clicks: Projected daily clicks at this bid/tier.
    """

    bid: int = 0
    min: int = 0
    budget: int = 0
    shows: int = 0
    clicks: int = 0

    @classmethod
    def from_portal(cls, data: dict | None) -> ReachTier:
        """Create from a tier sub-dict; missing/null yields a zeroed tier."""
        if not isinstance(data, dict):
            return cls()
        return cls(
            bid=data.get('bid', 0),
            min=data.get('min', 0),
            budget=data.get('budget', 0),
            shows=data.get('shows', 0),
            clicks=data.get('clicks', 0),
        )


@dataclass(slots=True)
class PortalBidRecommendation:
    """Portal bid recommendation for one (NM, placement) pair.

    Returned by the unofficial endpoints on ``cmp.wildberries.ru``:
    ``/api/v1/advert/bids-cpc`` and ``/api/v1/advert/bids``. The
    response shape depends on ``bid_type`` rather than ``payment_type``:

    - ``bid_type=1`` (manual) → ``{'combined': [...]}`` — one record per
      NM, ``placement = 'combined'``.
    - ``bid_type=2`` (unified) → ``{'search': [...], 'recommendations': [...]}``
      — two records per NM, ``placement = 'search'`` / ``'recommendations'``.

    See ``docs/portal/endpoints/`` for the empiric reference.

    Attributes:
        nm_id: WB article number echoed back by the portal.
        payment_type: ``'cpm'`` or ``'cpc'`` — the endpoint that was hit.
        placement: Top-level key from the response (e.g. ``'combined'``,
            ``'search'``, ``'recommendations'``). ``None`` only if a future
            response variant returns a flat array with no placement context.
        min_bid: Absolute floor in kopecks for this NM × placement.
        reach_max: Max-reach tier forecast.
        reach_medium: Medium-reach tier forecast.
        reach_min: Min-reach tier forecast.
    """

    nm_id: int
    payment_type: str
    placement: str | None
    min_bid: int
    reach_max: ReachTier
    reach_medium: ReachTier
    reach_min: ReachTier

    @classmethod
    def from_portal(
            cls,
            data: dict,
            payment_type: str,
            placement: str | None = None,
    ) -> PortalBidRecommendation:
        """Create from a per-NM entry in the portal bids response.

        Args:
            data: Raw entry dict — `{id, min, reach_max, reach_medium, reach_min}`.
            payment_type: ``'cpm'`` or ``'cpc'``.
            placement: The placement key (top-level dict key from the
                response), or ``None`` if the entry came from a flat array.
        """
        return cls(
            nm_id=data.get('id', 0),
            payment_type=payment_type,
            placement=placement,
            min_bid=data.get('min', 0),
            reach_max=ReachTier.from_portal(data.get('reach_max')),
            reach_medium=ReachTier.from_portal(data.get('reach_medium')),
            reach_min=ReachTier.from_portal(data.get('reach_min')),
        )


def parse_portal_bids_response(
        raw: dict | list,
        payment_type: str,
) -> list[PortalBidRecommendation]:
    """Normalize the portal bids response into a flat record list.

    The response is shape-flexible — observed variants include
    ``{'combined': [...]}`` (manual bidding) and
    ``{'search': [...], 'recommendations': [...]}`` (unified bidding).
    A flat list is also accepted as a defensive fallback. The parser
    surfaces whatever placement keys WB returns without hard-coding
    a fixed set, so a future ``'cart'`` (or similar) placement just
    works.

    Args:
        raw: Raw response body (dict-of-lists in current samples; a
            flat list is tolerated for robustness).
        payment_type: ``'cpm'`` or ``'cpc'`` — stored on each record.
    """
    if isinstance(raw, dict):
        results: list[PortalBidRecommendation] = []
        for placement_key, items in raw.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict):
                    results.append(
                        PortalBidRecommendation.from_portal(
                            item,
                            payment_type=payment_type,
                            placement=placement_key,
                        )
                    )
        return results
    if isinstance(raw, list):
        return [
            PortalBidRecommendation.from_portal(item, payment_type=payment_type)
            for item in raw
            if isinstance(item, dict)
        ]
    return []


@dataclass(slots=True)
class JamReport:
    """Async report entry from the WB Джем (Jam) ``file-manager/downloads`` list.

    Attributes:
        id: Client-generated UUID echoed by WB; used to match the report we just
            requested against the list response and to build the download URL.
        status: WB status string — ``SUCCESS`` is terminal-ok, ``FAILED``/``ERROR``
            terminal-fail, anything else (``PROCESSING`` etc.) means keep polling.
        name: Human-readable report name (Russian; e.g. "Поисковые запросы — ваши товары").
        size: ZIP size in bytes (``0`` until generated).
        start_date: Reporting period start (``YYYY-MM-DD``).
        end_date: Reporting period end (``YYYY-MM-DD``).
        download_url: Full URL on the downloads-content-analytics host.
        created_at: When WB queued the report (ISO-8601).
        generated_at: When WB finished generating it (ISO-8601; empty if not ready).
    """

    id: str
    status: str
    name: str
    size: int
    start_date: str
    end_date: str
    download_url: str
    created_at: str
    generated_at: str

    @classmethod
    def from_api(cls, data: dict) -> JamReport:
        """Build from a raw ``data.downloads[]`` entry; tolerant of missing keys."""
        return cls(
            id=str(data.get('id', '')),
            status=str(data.get('status', '')),
            name=str(data.get('name', '')),
            size=int(data.get('size') or 0),
            start_date=str(data.get('startDate', '')),
            end_date=str(data.get('endDate', '')),
            download_url=str(data.get('downloadUrl', '')),
            created_at=str(data.get('createdAt', '')),
            generated_at=str(data.get('generatedAt', '')),
        )

    @property
    def is_terminal(self) -> bool:
        """True once the report has reached a final state (success or failure)."""
        return self.status in ('SUCCESS', 'FAILED', 'ERROR')

    @property
    def is_success(self) -> bool:
        return self.status == 'SUCCESS'


@dataclass(slots=True)
class SalesReport:
    """Metadata for a WB seller-goods sales report (I-25).

    Returned by both the generate (POST) and list (GET) endpoints on
    ``seller-weekly-report.wildberries.ru``. The list endpoint returns a
    narrower projection — only ``id, createdAt, dateFrom, dateTo`` — so the
    other fields are tolerated as defaults.

    Readiness is **not** signalled by any field here: the list endpoint
    omits status; ``total_count == 0`` is ambiguous (pending vs. legitimately
    empty day); ``file_url`` is empty on the immediate POST response.
    The orchestrator decides readiness by attempting the xlsx download and
    treating a non-empty ``data`` envelope as success.

    Attributes:
        id: Server-assigned id of the shape
            ``supplier-goods-{supplierID}-{from}-{to}-{nonce}``.
        supplier_id: Seller ID; 0 when the producing endpoint omits it.
        locale: WB locale string (e.g. ``'ru'``); empty when omitted.
        report_name: Report-type slug (``'supplier-goods'``).
        date_from: Reporting period start (``YYYY-MM-DD``).
        date_to: Reporting period end (``YYYY-MM-DD``).
        created_at: When WB queued the report (ISO-8601).
        expired_at: When WB will purge the report (ISO-8601; ``''`` from list).
        file_url: Populated once WB exposes the file; not used as a readiness
            check (backfilled by the service after a successful download).
        total_count: Row count of the xlsx; do **not** use as readiness signal.
        is_deleted: WB-side soft-delete flag.
    """

    id: str
    supplier_id: int
    locale: str
    report_name: str
    date_from: str
    date_to: str
    created_at: str
    expired_at: str
    file_url: str
    total_count: int
    is_deleted: bool

    @classmethod
    def from_api(cls, data: dict) -> SalesReport:
        """Build from a raw ``data`` entry; tolerant of missing keys."""
        return cls(
            id=str(data.get('id', '')),
            supplier_id=int(data.get('supplierID') or 0),
            locale=str(data.get('locale', '')),
            report_name=str(data.get('reportName', '')),
            date_from=str(data.get('dateFrom', '')),
            date_to=str(data.get('dateTo', '')),
            created_at=str(data.get('createdAt', '')),
            expired_at=str(data.get('expiredAt', '')),
            file_url=str(data.get('fileUrl', '')),
            total_count=int(data.get('totalCount') or 0),
            is_deleted=bool(data.get('isDeleted') or False),
        )


@dataclass(slots=True)
class CampaignFinanceEntry:
    """One deduction row from the cmp.wildberries.ru expense ledger.

    Mirrors a single ``upd_info[]`` entry returned by ``GET /api/v6/upd`` and
    the matching row in the ``GET /api/v5/updxlsx`` workbook. All fields are
    pass-through; in particular ``bid_type`` is the raw integer WB returns
    (semantics differ from the F-21 ``_BID_TYPE_INT`` mapping — see
    ``docs/phases/I-24-portal-campaign-finance.md``).

    Attributes:
        advert_id: Campaign identifier.
        camp_name: Seller-chosen campaign name.
        upd_time: Charge timestamp (ISO-8601 with MSK offset).
        upd_sum: Charge amount in rubles.
        bid_type: Raw WB enum (1 or 2); do not assume the F-21 manual/unified
            mapping — empirically the xlsx labels ``bid_type=1`` as
            "Единая Ставка" (Unified Rate).
        payment_type: Russian label for the payment source (e.g. "Баланс").
        payment_type_id: Numeric payment-source code.
        advert_status: WB campaign status code at charge time (e.g. "9", "11").
        payment_model: Pricing model — "cpm" or "cpc".
        upd_num: Document number (0 when not yet assigned).
        booked_time: When the charge was booked (ISO-8601; JSON ``time`` field).
        source_service_id: Source-service code from WB.
        is_autorefill: True when the charge was funded by an auto-refill rule.
        advert_type: WB sub-type label (often empty).
        category_uid: Category UUID (often the all-sixes sentinel).
    """

    advert_id: int
    camp_name: str
    upd_time: str
    upd_sum: int
    bid_type: int
    payment_type: str
    payment_type_id: int
    advert_status: str
    payment_model: str
    upd_num: int
    booked_time: str
    source_service_id: int
    is_autorefill: bool
    advert_type: str
    category_uid: str

    @classmethod
    def from_api(cls, data: dict) -> CampaignFinanceEntry:
        """Build from one ``upd_info[]`` entry; tolerant of missing keys."""
        return cls(
            advert_id=int(data.get('advert_id') or 0),
            camp_name=str(data.get('camp_name', '')),
            upd_time=str(data.get('upd_time', '')),
            upd_sum=int(data.get('upd_sum') or 0),
            bid_type=int(data.get('bid_type') or 0),
            payment_type=str(data.get('payment_type', '')),
            payment_type_id=int(data.get('payment_type_id') or 0),
            advert_status=str(data.get('advert_status', '')),
            payment_model=str(data.get('payment_model', '')),
            upd_num=int(data.get('upd_num') or 0),
            booked_time=str(data.get('time', '')),
            source_service_id=int(data.get('source_service_id') or 0),
            is_autorefill=bool(data.get('is_autorefill', False)),
            advert_type=str(data.get('advert_type', '')),
            category_uid=str(data.get('category_uid', '')),
        )


@dataclass(slots=True)
class CampaignFinancePage:
    """One page (or the merged result of all pages) from ``GET /api/v6/upd``.

    Attributes:
        entries: Per-deduction rows.
        upd_total_amount: Sum of all charges across the requested date range
            (not just this page — WB returns the full-range total on every page).
        total_count: Total row count for the date range (same — full-range).
        page_number: 1-indexed page number this response represents. When the
            page is the merged "fetch-all" result, this is 1 and ``page_size``
            equals ``total_count``.
        page_size: Per-page size used for the request.
    """

    entries: list[CampaignFinanceEntry]
    upd_total_amount: int
    total_count: int
    page_number: int
    page_size: int

    @classmethod
    def from_api(cls, data: dict, *, page_number: int, page_size: int) -> CampaignFinancePage:
        """Build from a raw ``/api/v6/upd`` response."""
        raw_rows = data.get('upd_info') or []
        entries = [CampaignFinanceEntry.from_api(r) for r in raw_rows if isinstance(r, dict)]
        return cls(
            entries=entries,
            upd_total_amount=int(data.get('upd_total_amount') or 0),
            total_count=int(data.get('total_count') or 0),
            page_number=page_number,
            page_size=page_size,
        )
