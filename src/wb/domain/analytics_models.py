"""Domain models for WB Analytics API responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

__all__ = [
    'ReportType',
    'AggregationLevel',
    'ProductFunnelStats',
    'FunnelHistoryDay',
    'ProductFunnelHistory',
    'SearchReportProduct',
    'SearchReportGroup',
    'SearchTextEntry',
    'CsvReportStatus',
]


class ReportType(str, Enum):
    """Analytics CSV report type identifiers."""

    DETAIL_HISTORY = 'DETAIL_HISTORY_REPORT'
    GROUPED_HISTORY = 'GROUPED_HISTORY_REPORT'
    SEARCH_QUERIES_GROUP = 'SEARCH_QUERIES_PREMIUM_REPORT_GROUP'
    SEARCH_QUERIES_PRODUCT = 'SEARCH_QUERIES_PREMIUM_REPORT_PRODUCT'
    SEARCH_QUERIES_TEXT = 'SEARCH_QUERIES_PREMIUM_REPORT_TEXT'
    STOCK_HISTORY = 'STOCK_HISTORY_REPORT_CSV'
    STOCK_HISTORY_DAILY = 'STOCK_HISTORY_DAILY_CSV'


class AggregationLevel(str, Enum):
    """Time aggregation level for history endpoints."""

    DAY = 'day'
    WEEK = 'week'


@dataclass(slots=True)
class ProductFunnelStats:
    """Per-product sales funnel statistics for a period.

    Attributes:
        nm_id: WB article number.
        title: Product card name.
        vendor_code: Seller's article code.
        brand_name: Brand name.
        subject_id: Subject category ID.
        subject_name: Subject category name.
        open_count: Click-throughs.
        cart_count: Adds to cart.
        order_count: Items ordered.
        order_sum: Total order value.
        buyout_count: Items purchased.
        buyout_sum: Total purchase value.
        cancel_count: Items canceled/returned.
        cancel_sum: Canceled/returned value.
        avg_price: Average item price.
        cart_conversion: Conversion to cart percent.
        order_conversion: Conversion to order percent.
        buyout_percent: Purchase rate percent.
        currency: Report currency code.
    """

    nm_id: int
    title: str = ''
    vendor_code: str = ''
    brand_name: str = ''
    subject_id: int = 0
    subject_name: str = ''
    open_count: int = 0
    cart_count: int = 0
    order_count: int = 0
    order_sum: int = 0
    buyout_count: int = 0
    buyout_sum: int = 0
    cancel_count: int = 0
    cancel_sum: int = 0
    avg_price: int = 0
    cart_conversion: float = 0.0
    order_conversion: float = 0.0
    buyout_percent: float = 0.0
    currency: str = 'RUB'

    @classmethod
    def from_api(cls, data: dict, currency: str = 'RUB') -> ProductFunnelStats:
        """Create from sales-funnel/products response item.

        Args:
            data: Raw dict with product + statistic nested objects.
            currency: Currency code from the response wrapper.
        """
        product = data.get('product', {})
        stats = data.get('statistic', {})
        selected = stats.get('selected', {})
        conversions = selected.get('conversions', {})

        return cls(
            nm_id=product.get('nmId', 0),
            title=product.get('title', ''),
            vendor_code=product.get('vendorCode', ''),
            brand_name=product.get('brandName', ''),
            subject_id=product.get('subjectId', 0),
            subject_name=product.get('subjectName', ''),
            open_count=selected.get('openCount', 0),
            cart_count=selected.get('cartCount', 0),
            order_count=selected.get('orderCount', 0),
            order_sum=selected.get('orderSum', 0),
            buyout_count=selected.get('buyoutCount', 0),
            buyout_sum=selected.get('buyoutSum', 0),
            cancel_count=selected.get('cancelCount', 0),
            cancel_sum=selected.get('cancelSum', 0),
            avg_price=selected.get('avgPrice', 0),
            cart_conversion=conversions.get('addToCartPercent', 0.0),
            order_conversion=conversions.get('cartToOrderPercent', 0.0),
            buyout_percent=conversions.get('buyoutPercent', 0.0),
            currency=currency,
        )


@dataclass(slots=True)
class FunnelHistoryDay:
    """Single day/week aggregation in funnel history.

    Attributes:
        dt: Date string (YYYY-MM-DD).
        open_count: Click-throughs.
        cart_count: Adds to cart.
        order_count: Items ordered.
        order_sum: Total order value.
        buyout_count: Items purchased.
        buyout_sum: Total purchase value.
        cancel_count: Items canceled/returned.
        cancel_sum: Canceled/returned value.
    """

    dt: str
    open_count: int = 0
    cart_count: int = 0
    order_count: int = 0
    order_sum: int = 0
    buyout_count: int = 0
    buyout_sum: int = 0
    cancel_count: int = 0
    cancel_sum: int = 0

    @classmethod
    def from_api(cls, data: dict) -> FunnelHistoryDay:
        """Create from a history entry dict.

        Args:
            data: Raw dict with dt and metric fields.
        """
        return cls(
            dt=data.get('dt', ''),
            open_count=data.get('openCount', 0),
            cart_count=data.get('cartCount', 0),
            order_count=data.get('orderCount', 0),
            order_sum=data.get('orderSum', 0),
            buyout_count=data.get('buyoutCount', 0),
            buyout_sum=data.get('buyoutSum', 0),
            cancel_count=data.get('cancelCount', 0),
            cancel_sum=data.get('cancelSum', 0),
        )


@dataclass(slots=True)
class ProductFunnelHistory:
    """Product with its daily/weekly funnel history.

    Attributes:
        nm_id: WB article number.
        title: Product card name.
        history: List of per-day/week metric aggregations.
        currency: Report currency code.
    """

    nm_id: int
    title: str = ''
    history: list[FunnelHistoryDay] = field(default_factory=list)
    currency: str = 'RUB'

    @classmethod
    def from_api(cls, data: dict) -> ProductFunnelHistory:
        """Create from sales-funnel/products/history response item.

        Args:
            data: Raw dict with product, history, and currency fields.
        """
        product = data.get('product', {})
        history_raw = data.get('history', [])
        currency = data.get('currency', 'RUB')

        return cls(
            nm_id=product.get('nmId', 0),
            title=product.get('title', ''),
            history=[FunnelHistoryDay.from_api(h) for h in history_raw],
            currency=currency,
        )


@dataclass(slots=True)
class SearchReportProduct:
    """Product entry within a search report group.

    Attributes:
        nm_id: WB article number.
        vendor_code: Seller's article code.
        name: Product name.
        open_count: Click-throughs from search.
        add_to_cart_count: Adds to cart from search.
        order_count: Items ordered from search.
        avg_position: Average position in search results.
        visibility: Visibility percentage in search.
    """

    nm_id: int
    vendor_code: str = ''
    name: str = ''
    open_count: int = 0
    add_to_cart_count: int = 0
    order_count: int = 0
    avg_position: float = 0.0
    visibility: float = 0.0

    @classmethod
    def from_api(cls, data: dict) -> SearchReportProduct:
        """Create from a search report product dict.

        Args:
            data: Raw dict with product metrics.
        """
        return cls(
            nm_id=data.get('nmId', 0),
            vendor_code=data.get('vendorCode', ''),
            name=data.get('name', ''),
            open_count=data.get('openCard', 0),
            add_to_cart_count=data.get('addToCart', 0),
            order_count=data.get('orders', 0),
            avg_position=data.get('avgPosition', 0.0),
            visibility=data.get('visibility', 0.0),
        )


@dataclass(slots=True)
class SearchReportGroup:
    """A group in the search report (by subject/brand/tag).

    Attributes:
        subject_id: Subject category ID.
        subject_name: Subject category name.
        brand_name: Brand name.
        tag_id: Label ID.
        products: Product entries within this group.
    """

    subject_id: int = 0
    subject_name: str = ''
    brand_name: str = ''
    tag_id: int = 0
    products: list[SearchReportProduct] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> SearchReportGroup:
        """Create from a search report group dict.

        Args:
            data: Raw dict with group info and products array.
        """
        raw_products = data.get('products', [])
        return cls(
            subject_id=data.get('subjectId', 0),
            subject_name=data.get('subjectName', ''),
            brand_name=data.get('brandName', ''),
            tag_id=data.get('tagId', 0),
            products=[
                SearchReportProduct.from_api(p) for p in raw_products
            ],
        )


@dataclass(slots=True)
class SearchTextEntry:
    """A search text with metrics for a single product.

    Attributes:
        text: The search query text.
        frequency: Number of search requests.
        avg_position: Average product position for this text.
        median_position: Median product position for this text.
        open_count: Click-throughs from this text.
        add_to_cart_count: Adds to cart from this text.
        order_count: Items ordered from this text.
        visibility: Visibility percentage.
    """

    text: str
    frequency: int = 0
    avg_position: float = 0.0
    median_position: float = 0.0
    open_count: int = 0
    add_to_cart_count: int = 0
    order_count: int = 0
    visibility: float = 0.0

    @classmethod
    def from_api(cls, data: dict) -> SearchTextEntry:
        """Create from a search text entry dict.

        Args:
            data: Raw dict with text metrics.
        """
        return cls(
            text=data.get('text', ''),
            frequency=data.get('frequency', 0),
            avg_position=data.get('avgPosition', 0.0),
            median_position=data.get('medianPosition', 0.0),
            open_count=data.get('openCard', 0),
            add_to_cart_count=data.get('addToCart', 0),
            order_count=data.get('orders', 0),
            visibility=data.get('visibility', 0.0),
        )


@dataclass(slots=True)
class CsvReportStatus:
    """Status of a CSV report generation task.

    Attributes:
        id: Report UUID.
        name: User-defined report name.
        status: Generation status (WAITING, PROCESSING, SUCCESS, RETRY, FAILED).
        size: Report file size in bytes.
        created_at: Generation completion timestamp.
        start_date: Report period start date.
        end_date: Report period end date.
    """

    id: str
    name: str = ''
    status: str = 'WAITING'
    size: int = 0
    created_at: str = ''
    start_date: str = ''
    end_date: str = ''

    @classmethod
    def from_api(cls, data: dict) -> CsvReportStatus:
        """Create from nm-report/downloads list response item.

        Args:
            data: Raw dict with report status fields.
        """
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            status=data.get('status', 'WAITING'),
            size=data.get('size', 0),
            created_at=data.get('createdAt', ''),
            start_date=data.get('startDate', ''),
            end_date=data.get('endDate', ''),
        )
