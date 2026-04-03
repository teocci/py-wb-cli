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
    'CampaignStats',
    'ClusterStats',
    'MinusPhraseSet',
    'OptimizationDecision',
    'AccountBalance',
    'RecommendedBid',
    'MutationResult',
    'CampaignCreate',
    'BidMutation',
    'PlacementConfig',
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
    start_time: str | None = None
    updated_time: str | None = None
    create_time: str | None = None

    @classmethod
    def from_api(cls, data: dict) -> Campaign:
        """Create from WB /api/advert/v2/adverts response payload."""
        settings = data.get('settings', {})
        timestamps = data.get('timestamps', {})
        return cls(
            campaign_id=data['id'],
            name=settings.get('name', ''),
            status=CampaignStatus(data['status']),
            campaign_type=CampaignType(data.get('type', 9)),
            payment_type=PaymentType(settings.get('payment_type', 'cpm')),
            bid_type=data.get('bid_type', 'manual'),
            currency=data.get('currency', 'RUB'),
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
class CampaignStats:
    """Aggregated campaign statistics for a date range.

    Attributes:
        campaign_id: Campaign identifier.
        views: Total impressions/views.
        clicks: Total clicks.
        ctr: Click-through rate.
        orders: Total orders attributed.
        spend: Total spend in kopecks.
        cpc: Cost per click.
        cr: Conversion rate.
        atbs: Add-to-basket count.
        shks: Units shipped.
        currency: Currency code.
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

    @classmethod
    def from_api(cls, data: dict) -> CampaignStats:
        """Create from WB API /adv/v3/fullstats response payload."""
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
    """

    success: bool
    action: str
    target_id: str
    dry_run: bool = False
    message: str = ''


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
        return {
            'name': self.name,
            'nms': self.nm_ids,
            'bid_type': self.bid_type,
            'placement_types': self.placement_types,
        }


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
    """Platform-recommended bid for a campaign product.

    Attributes:
        campaign_id: Campaign identifier.
        nm_id: Product nomenclature ID.
        recommended: Recommended CPM value.
        minimum: Minimum acceptable CPM.
    """

    campaign_id: int
    nm_id: int = 0
    recommended: int = 0
    minimum: int = 0

    @classmethod
    def from_api(cls, data: dict, campaign_id: int) -> RecommendedBid:
        """Create from WB API recommended_cpm response item.

        Args:
            data: Raw API dict for a bid recommendation.
            campaign_id: Campaign this recommendation belongs to.
        """
        return cls(
            campaign_id=campaign_id,
            nm_id=data.get('nmId', 0),
            recommended=data.get('cpm', 0),
            minimum=data.get('minCpm', 0),
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
