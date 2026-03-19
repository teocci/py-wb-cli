"""Domain models for WB CLI - normalized representations of WB API objects."""

from __future__ import annotations

from dataclasses import dataclass, field

from wb.domain.enums import (
    CampaignStatus,
    CampaignType,
    PaymentType,
)

# CPM campaign type code for auto campaigns in the WB API
_AUTO_CAMPAIGN_TYPE_CODE = 8

__all__ = [
    'Campaign',
    'ProductCard',
    'ItemBid',
    'SearchCluster',
    'ClusterBid',
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
        daily_budget: Daily budget in kopecks.
        start_time: ISO timestamp of campaign start.
        end_time: ISO timestamp of campaign end.
        create_time: ISO timestamp of creation.
    """

    campaign_id: int
    name: str
    status: CampaignStatus
    campaign_type: CampaignType
    payment_type: PaymentType
    daily_budget: int = 0
    start_time: str | None = None
    end_time: str | None = None
    create_time: str | None = None

    @classmethod
    def from_api(cls, data: dict) -> Campaign:
        """Create from WB API response payload."""
        return cls(
            campaign_id=data['advertId'],
            name=data.get('name', ''),
            status=CampaignStatus(data['status']),
            campaign_type=CampaignType(data['type']),
            payment_type=PaymentType(data.get('paymentType', 'cpm')),
            daily_budget=data.get('dailyBudget', 0),
            start_time=data.get('startTime'),
            end_time=data.get('endTime'),
            create_time=data.get('createTime'),
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
    """A search cluster attached to a campaign + product pair.

    Attributes:
        cluster_id: Cluster identifier.
        cluster_name: Human-readable cluster label.
        count: Number of queries in the cluster.
        is_active: Whether the cluster is currently active.
        bid: Current bid on this cluster.
        recommended_bid: Platform-recommended bid.
    """

    cluster_id: int
    cluster_name: str
    count: int = 0
    is_active: bool = True
    bid: int = 0
    recommended_bid: int = 0

    @classmethod
    def from_api(cls, data: dict, is_active: bool = True) -> SearchCluster:
        """Create from WB API response payload.

        Args:
            data: Raw API dict for a cluster.
            is_active: Whether this cluster is active.
        """
        return cls(
            cluster_id=data.get('id', 0),
            cluster_name=data.get('keyword', ''),
            count=data.get('count', 0),
            is_active=is_active,
            bid=data.get('bid', 0),
            recommended_bid=data.get('recommendedBid', 0),
        )


@dataclass(slots=True)
class ClusterBid:
    """Bid mutation for a search cluster.

    Attributes:
        cluster_id: Target cluster ID.
        bid: New bid value.
    """

    cluster_id: int
    bid: int


@dataclass(slots=True)
class BudgetSnapshot:
    """Campaign budget state at a point in time.

    Attributes:
        campaign_id: Campaign identifier.
        total: Total budget allocated.
        daily: Daily budget limit.
        balance: Remaining balance.
    """

    campaign_id: int
    total: int = 0
    daily: int = 0
    balance: int = 0

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
            daily=data.get('dailyBudget', 0),
            balance=data.get('balance', 0),
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
        cpm: Cost per mille.
    """

    campaign_id: int
    views: int = 0
    clicks: int = 0
    ctr: float = 0.0
    orders: int = 0
    spend: int = 0
    cpc: float = 0.0
    cpm: float = 0.0

    @classmethod
    def from_api(cls, data: dict) -> CampaignStats:
        """Create from WB API /adv/v2/fullstats response payload."""
        return cls(
            campaign_id=data.get('advertId', 0),
            views=data.get('views', 0),
            clicks=data.get('clicks', 0),
            ctr=data.get('ctr', 0.0),
            orders=data.get('orders', 0),
            spend=data.get('sum', 0),
            cpc=data.get('cpc', 0.0),
            cpm=data.get('cpm', 0.0),
        )


@dataclass(slots=True)
class ClusterStats:
    """Statistics for a single search cluster.

    Attributes:
        cluster_id: Cluster identifier.
        cluster_name: Cluster label.
        views: Impressions.
        clicks: Clicks.
        ctr: Click-through rate.
        orders: Orders.
        spend: Spend in kopecks.
    """

    cluster_id: int
    cluster_name: str = ''
    views: int = 0
    clicks: int = 0
    ctr: float = 0.0
    orders: int = 0
    spend: int = 0

    @classmethod
    def from_api(cls, data: dict) -> ClusterStats:
        """Create from WB API cluster stats response payload."""
        return cls(
            cluster_id=data.get('id', 0),
            cluster_name=data.get('keyword', ''),
            views=data.get('views', 0),
            clicks=data.get('clicks', 0),
            ctr=data.get('ctr', 0.0),
            orders=data.get('orders', 0),
            spend=data.get('sum', 0),
        )


@dataclass(slots=True)
class MinusPhraseSet:
    """Set of minus phrases for a campaign + product pair.

    Attributes:
        campaign_id: Campaign identifier.
        nm_id: Product nomenclature ID.
        phrases: List of excluded phrases.
    """

    campaign_id: int
    nm_id: int
    phrases: list[str] = field(default_factory=list)


@dataclass(slots=True)
class OptimizationDecision:
    """A recommended optimization action.

    Attributes:
        action: Type of action (raise_bid, lower_bid, add_minus, etc.).
        target_type: What the action targets (campaign, item, cluster).
        target_id: Identifier of the target.
        current_value: Current state value.
        proposed_value: Proposed new value.
        reason: Explanation for the recommendation.
        confidence: Confidence score 0.0-1.0.
    """

    action: str
    target_type: str
    target_id: str
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
    """

    balance: int = 0
    net: int = 0
    bonus: int = 0

    @classmethod
    def from_api(cls, data: dict) -> AccountBalance:
        """Create from WB API /adv/v1/account/balance response."""
        return cls(
            balance=data.get('balance', 0),
            net=data.get('net', 0),
            bonus=data.get('bonus', 0),
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
    """Parameters for creating a new campaign.

    Attributes:
        name: Campaign display name.
        campaign_type: Type of campaign to create.
        daily_budget: Daily budget limit in kopecks.
        nm_ids: Product nomenclature IDs to include.
        subject_id: Subject category ID (optional).
    """

    name: str
    campaign_type: CampaignType
    daily_budget: int
    nm_ids: list[int] = field(default_factory=list)
    subject_id: int | None = None

    def to_api(self) -> dict:
        """Serialize to WB API create-campaign payload."""
        payload: dict = {
            'type': self.campaign_type.value,
            'name': self.name,
            'dailyBudget': self.daily_budget,
        }
        if self.nm_ids:
            payload['nms'] = self.nm_ids
        if self.subject_id is not None:
            payload['subjectId'] = self.subject_id
        return payload


@dataclass(slots=True)
class BidMutation:
    """A single CPM bid change for an item in a campaign.

    Attributes:
        nm_id: Product nomenclature ID.
        cpm: New CPM bid value in kopecks.
        subject_id: Subject category scope (0 = all subjects).
    """

    nm_id: int
    cpm: int
    subject_id: int = 0

    def to_api(self, campaign_id: int) -> dict:
        """Serialize to WB API set-bid payload.

        Args:
            campaign_id: Campaign this bid belongs to.
        """
        return {
            'advertId': campaign_id,
            'type': _AUTO_CAMPAIGN_TYPE_CODE,
            'cpm': self.cpm,
            'param': self.subject_id,
        }


@dataclass(slots=True)
class PlacementConfig:
    """Placement configuration for a campaign.

    Attributes:
        search_enabled: Whether search placement is active.
        catalog_enabled: Whether catalog placement is active.
        booster_enabled: Whether booster placement is active.
    """

    search_enabled: bool = True
    catalog_enabled: bool = True
    booster_enabled: bool = False

    def to_api(self, campaign_id: int) -> dict:
        """Serialize to WB API update-params payload.

        Args:
            campaign_id: Campaign to apply placements to.
        """
        return {
            'advertId': campaign_id,
            'params': [
                {
                    'active': self.search_enabled,
                    'place': 1,
                },
                {
                    'active': self.catalog_enabled,
                    'place': 2,
                },
            ],
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
