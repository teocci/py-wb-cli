"""Domain models for WB Reports API — warehouse remains, orders, sales."""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    'WarehouseStock',
    'WarehouseRemainItem',
    'ReportTask',
    'ProductStockSummary',
    'SaleRecord',
    'WarehouseRunway',
    'StockRunwayItem',
    'StockRunwayReport',
]


@dataclass(slots=True)
class WarehouseStock:
    """Stock quantity at a single warehouse.

    Attributes:
        warehouse_name: Name of the WB warehouse.
        quantity: Number of items at this warehouse.
    """

    warehouse_name: str
    quantity: int

    @classmethod
    def from_api(cls, data: dict) -> WarehouseStock:
        """Create from a warehouse entry in the download response.

        Args:
            data: Raw dict with warehouseName and quantity.
        """
        return cls(
            warehouse_name=data.get('warehouseName', ''),
            quantity=data.get('quantity', 0),
        )


@dataclass(slots=True)
class WarehouseRemainItem:
    """Single item from the warehouse remains report download.

    Attributes:
        brand: Brand name.
        subject_name: Product subject/category.
        vendor_code: Seller's article code.
        nm_id: WB article number.
        barcode: Product barcode.
        tech_size: Product size.
        volume: Volume in liters (present when grouped by NM).
        warehouses: Per-warehouse stock breakdown.
    """

    brand: str
    subject_name: str
    vendor_code: str
    nm_id: int
    barcode: str
    tech_size: str
    volume: float
    warehouses: list[WarehouseStock] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict) -> WarehouseRemainItem:
        """Create from a raw download response item.

        Args:
            data: Raw dict from the warehouse remains download array.
        """
        raw_wh = data.get('warehouses') or []
        warehouses = [WarehouseStock.from_api(w) for w in raw_wh]
        return cls(
            brand=data.get('brand', ''),
            subject_name=data.get('subjectName', ''),
            vendor_code=data.get('vendorCode', ''),
            nm_id=data.get('nmId', 0),
            barcode=data.get('barcode', ''),
            tech_size=data.get('techSize', ''),
            volume=data.get('volume', 0.0),
            warehouses=warehouses,
        )

    @property
    def total_quantity(self) -> int:
        """Sum of quantities across all warehouses."""
        return sum(w.quantity for w in self.warehouses)


@dataclass(slots=True)
class ReportTask:
    """Status of an async report generation task.

    Attributes:
        task_id: UUID of the task.
        status: Current status (new, processing, done, purged, canceled).
    """

    task_id: str
    status: str

    @classmethod
    def from_create(cls, data: dict) -> ReportTask:
        """Create from the task creation response.

        Args:
            data: Response dict with data.taskId.
        """
        inner = data.get('data', {})
        return cls(
            task_id=inner.get('taskId', ''),
            status='new',
        )

    @classmethod
    def from_status(cls, task_id: str, data: dict) -> ReportTask:
        """Create from the status check response.

        Args:
            task_id: The task UUID.
            data: Response dict with data.status.
        """
        inner = data.get('data', {})
        return cls(
            task_id=inner.get('id', task_id),
            status=inner.get('status', 'unknown'),
        )

    @property
    def is_done(self) -> bool:
        """Whether the report is ready for download."""
        return self.status == 'done'

    @property
    def is_terminal(self) -> bool:
        """Whether the task has reached a final state."""
        return self.status in ('done', 'purged', 'canceled')


@dataclass(slots=True)
class ProductStockSummary:
    """Aggregated stock summary for a single product across warehouses.

    Attributes:
        nm_id: WB article number.
        brand: Brand name.
        subject_name: Product subject/category.
        vendor_code: Seller's article code.
        total_quantity: Total stock across all warehouses.
        warehouses: Per-warehouse breakdown.
    """

    nm_id: int
    brand: str
    subject_name: str
    vendor_code: str
    total_quantity: int
    warehouses: list[WarehouseStock] = field(default_factory=list)


@dataclass(slots=True)
class SaleRecord:
    """A single sale event from the Statistics API.

    Attributes:
        nm_id: WB article number.
        date: Sale date in YYYY-MM-DD format.
        quantity: Number of units sold.
    """

    nm_id: int
    date: str
    quantity: int

    @classmethod
    def from_api(cls, data: dict) -> SaleRecord:
        """Create from a raw Statistics API sale dict.

        Args:
            data: Dict with nmId, date, quantity keys.
        """
        return cls(
            nm_id=int(data.get('nmId', 0)),
            date=data.get('date', '')[:10],
            quantity=int(data.get('quantity', 0)),
        )


@dataclass(slots=True)
class WarehouseRunway:
    """Stock runway (days until stockout) for a single warehouse.

    Attributes:
        warehouse_name: Name of the WB warehouse.
        quantity: Current stock quantity.
        days_of_stock: Days of stock remaining, or None if no sales data.
        alert: Alert level ('critical', 'low', or None).
    """

    warehouse_name: str
    quantity: int
    days_of_stock: int | None
    alert: str | None


@dataclass(slots=True)
class StockRunwayItem:
    """Stock runway summary for a single product (NM).

    Attributes:
        nm_id: WB article number.
        avg_daily_sales: Average units sold per day over the sales period.
        confidence: Data confidence ('high', 'medium', 'low', 'none').
        total_stock: Total stock across all physical warehouses.
        total_days_of_stock: Days until total stock runs out, or None.
        alert: Worst alert level across all warehouses, or None.
        warehouses: Per-warehouse runway breakdown.
    """

    nm_id: int
    avg_daily_sales: float
    confidence: str
    total_stock: int
    total_days_of_stock: int | None
    alert: str | None
    warehouses: list[WarehouseRunway] = field(default_factory=list)


@dataclass(slots=True)
class StockRunwayReport:
    """Full stock runway computation result.

    Attributes:
        computed_at: ISO datetime when the report was computed.
        sales_period_days: Number of days used for sales velocity calculation.
        items: Per-product runway items.
    """

    computed_at: str
    sales_period_days: int
    items: list[StockRunwayItem] = field(default_factory=list)
