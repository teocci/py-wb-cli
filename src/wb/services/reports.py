"""Service layer for WB Reports — warehouse remains with async polling and file cache."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from wb.client.reports import ReportsClient
from wb.client.statistics import StatisticsClient
from wb.core.constants import (
    EXCLUDED_WAREHOUSE_PREFIXES,
    REPORT_CACHE_TTL_HOURS,
    REPORT_POLL_INTERVAL,
    REPORT_POLL_TIMEOUT,
    RUNWAY_ALERT_CRITICAL_DAYS,
    RUNWAY_ALERT_LOW_DAYS,
    RUNWAY_CONFIDENCE_HIGH_DAYS,
    RUNWAY_CONFIDENCE_MEDIUM_DAYS,
)
from wb.core.exceptions import ApiError, ValidationError
from wb.domain.cache_models import ReportCacheEntry
from wb.domain.report_models import (
    ProductStockSummary,
    ReportTask,
    SaleRecord,
    StockRunwayItem,
    StockRunwayReport,
    WarehouseRemainItem,
    WarehouseRunway,
    WarehouseStock,
)

__all__ = ['ReportsService']

logger = logging.getLogger(__name__)


class ReportsService:
    """Business logic for WB report operations.

    Orchestrates the async report lifecycle (create -> poll -> download)
    and provides aggregation helpers. Optionally caches results to disk
    to avoid repeated 30–120 s API round-trips.

    Attributes:
        client: Underlying ReportsClient.
        statistics_client: Optional StatisticsClient for sales velocity data.
        reports_dir: Optional path to per-profile reports directory.
        cache_store: Optional CacheStore for report metadata.
        profile_name: Profile name used in cache entries.
    """

    def __init__(
            self,
            client: ReportsClient,
            statistics_client: StatisticsClient | None = None,
            reports_dir: Path | None = None,
            cache_store=None,
            profile_name: str = 'default',
    ) -> None:
        self._client = client
        self._stats = statistics_client
        self._reports_dir = reports_dir
        self._cache_store = cache_store
        self._profile_name = profile_name

    @property
    def _has_cache(self) -> bool:
        """Whether both a reports directory and cache store are configured."""
        return self._reports_dir is not None and self._cache_store is not None

    # ── Warehouse Remains ────────────────────────────────────────────

    def create_warehouse_report(self, **kwargs) -> ReportTask:
        """Create a warehouse remains report task.

        Args:
            **kwargs: Forwarded to ReportsClient.create_warehouse_remains.

        Returns:
            ReportTask with the new task ID.
        """
        raw = self._client.create_warehouse_remains(**kwargs)
        return ReportTask.from_create(raw)

    def check_warehouse_status(self, task_id: str) -> ReportTask:
        """Check the status of a warehouse report task.

        Args:
            task_id: UUID of the task.

        Returns:
            ReportTask with current status.
        """
        raw = self._client.get_warehouse_remains_status(task_id)
        return ReportTask.from_status(task_id, raw)

    def download_warehouse_report(
            self, task_id: str,
    ) -> list[WarehouseRemainItem]:
        """Download a completed warehouse report.

        Args:
            task_id: UUID of a task with status 'done'.

        Returns:
            List of WarehouseRemainItem with per-warehouse breakdown.
        """
        raw_items = self._client.download_warehouse_remains(task_id)
        return [WarehouseRemainItem.from_api(item) for item in raw_items]

    def poll_warehouse_report(
            self,
            task_id: str,
            *,
            interval: float = REPORT_POLL_INTERVAL,
            timeout: float = REPORT_POLL_TIMEOUT,
    ) -> ReportTask:
        """Poll a warehouse report task until it reaches a terminal state.

        Args:
            task_id: UUID of the task.
            interval: Seconds between status checks.
            timeout: Maximum seconds to wait before raising.

        Returns:
            ReportTask in a terminal state (done, purged, or canceled).

        Raises:
            ApiError: If the task does not finish within timeout.
        """
        elapsed = 0.0
        while elapsed < timeout:
            task = self.check_warehouse_status(task_id)
            logger.debug('Task %s status: %s (%.0fs)', task_id, task.status, elapsed)
            if task.is_terminal:
                return task
            time.sleep(interval)
            elapsed += interval

        raise ApiError(
            f'Warehouse report {task_id} did not finish within '
            f'{timeout:.0f}s (last status: {task.status})'
        )

    def get_warehouse_top(
            self,
            *,
            limit: int = 10,
            locale: str = 'ru',
            poll_interval: float = REPORT_POLL_INTERVAL,
            poll_timeout: float = REPORT_POLL_TIMEOUT,
            use_cache: bool = True,
    ) -> tuple[list[ProductStockSummary], bool]:
        """Convenience: create, poll, download, and return top products by stock.

        Creates a report grouped by NM, waits for completion, downloads,
        then aggregates and sorts by total quantity descending.
        Optionally returns a cached result if one exists within the TTL.

        Args:
            limit: Number of top products to return.
            locale: Language for warehouse names.
            poll_interval: Seconds between status checks.
            poll_timeout: Maximum seconds to wait.
            use_cache: When True, return cached result if available.

        Returns:
            Tuple of (summaries, from_cache) where from_cache indicates
            whether the data came from the local cache.

        Raises:
            ValidationError: If limit < 1.
            ApiError: If the report task fails or times out.
        """
        if limit < 1:
            raise ValidationError('limit must be at least 1')

        today = date.today().isoformat()
        cache_type = 'warehouse_remains'

        if use_cache and self._has_cache:
            cached_path, hit = self._cache_hit(cache_type, today)
            if hit and cached_path is not None:
                items = _load_stock_items(cached_path)
                return _aggregate_top(items, limit), True

        items = self._api_fetch_all_stock(poll_interval, poll_timeout, locale=locale)

        if self._has_cache:
            self._write_cache(cache_type, today, [asdict(i) for i in items])

        return _aggregate_top(items, limit), False

    # ── Stock Runway ─────────────────────────────────────────────────

    def get_stock_runway(
            self,
            *,
            sales_period_days: int = 30,
            poll_interval: float = REPORT_POLL_INTERVAL,
            poll_timeout: float = REPORT_POLL_TIMEOUT,
            use_cache: bool = True,
    ) -> tuple[StockRunwayReport, bool]:
        """Compute days-until-stockout per product per warehouse.

        Fetches warehouse stock (all products) and cross-references with
        sales velocity from the Statistics API.
        Optionally returns a cached result if both stock and sales data
        are within TTL.

        Args:
            sales_period_days: Lookback window for sales velocity.
            poll_interval: Seconds between warehouse report status checks.
            poll_timeout: Max seconds to wait for the warehouse report.
            use_cache: When True, use cached stock+sales data if available.

        Returns:
            Tuple of (report, from_cache) where from_cache is True only
            when both stock and sales data came from the cache.

        Raises:
            ValidationError: If statistics_client was not provided.
            ApiError: If the warehouse report fails or times out.
        """
        if self._stats is None:
            raise ValidationError(
                'statistics_client is required for stock runway computation'
            )
        if sales_period_days < 1:
            raise ValidationError('sales_period_days must be at least 1')

        today = date.today().isoformat()
        stock_type = 'warehouse_remains'
        sales_type = f'sales_{sales_period_days}d'

        stock_items, stock_cached = self._get_stock_items(
            today, stock_type, poll_interval, poll_timeout, use_cache,
        )
        sales, sales_cached = self._get_sales(
            today, sales_type, sales_period_days, use_cache,
        )

        velocity_map, sale_days_map = _build_velocity_map(sales, sales_period_days)
        computed_at = _utc_now_iso()
        items = [
            _compute_runway_item(item, velocity_map, sale_days_map, sales_period_days)
            for item in stock_items
        ]
        report = StockRunwayReport(
            computed_at=computed_at,
            sales_period_days=sales_period_days,
            items=items,
        )
        return report, stock_cached and sales_cached

    # ── Internal helpers ─────────────────────────────────────────────

    def _get_stock_items(
            self,
            today: str,
            cache_type: str,
            poll_interval: float,
            poll_timeout: float,
            use_cache: bool,
    ) -> tuple[list[WarehouseRemainItem], bool]:
        """Load stock items from cache or API."""
        if use_cache and self._has_cache:
            cached_path, hit = self._cache_hit(cache_type, today)
            if hit and cached_path is not None:
                return _load_stock_items(cached_path), True

        items = self._api_fetch_all_stock(poll_interval, poll_timeout)
        if self._has_cache:
            self._write_cache(cache_type, today, [asdict(i) for i in items])
        return items, False

    def _get_sales(
            self,
            today: str,
            cache_type: str,
            sales_period_days: int,
            use_cache: bool,
    ) -> tuple[list[SaleRecord], bool]:
        """Load sales records from cache or API."""
        if use_cache and self._has_cache:
            cached_path, hit = self._cache_hit(cache_type, today)
            if hit and cached_path is not None:
                return _load_sale_records(cached_path), True

        sales = self._fetch_sales(sales_period_days)
        if self._has_cache:
            self._write_cache(cache_type, today, [asdict(s) for s in sales])
        return sales, False

    def _api_fetch_all_stock(
            self,
            poll_interval: float,
            poll_timeout: float,
            locale: str = 'ru',
    ) -> list[WarehouseRemainItem]:
        """Create, poll, and download the full warehouse remains report."""
        task = self.create_warehouse_report(
            group_by_nm=True,
            group_by_brand=True,
            group_by_subject=True,
            group_by_sa=True,
            locale=locale,
        )
        logger.info('Created warehouse report task: %s', task.task_id)
        task = self.poll_warehouse_report(
            task.task_id,
            interval=poll_interval,
            timeout=poll_timeout,
        )
        if not task.is_done:
            raise ApiError(f'Warehouse report ended with status: {task.status}')
        return self.download_warehouse_report(task.task_id)

    def _fetch_sales(self, sales_period_days: int) -> list[SaleRecord]:
        """Fetch sales for the lookback window."""
        date_from = (date.today() - timedelta(days=sales_period_days)).isoformat()
        raw = self._stats.get_sales(date_from)  # type: ignore[union-attr]
        return [SaleRecord.from_api(r) for r in raw]

    def _cache_hit(
            self, report_type: str, date_str: str,
    ) -> tuple[Path | None, bool]:
        """Return (path, True) if a valid cached file exists within TTL.

        Args:
            report_type: Cache type key.
            date_str: Date string (YYYY-MM-DD) to look up.

        Returns:
            (path, True) on hit, (None, False) on miss or expired TTL.
        """
        entry = self._cache_store.get_report_cache(
            self._profile_name, report_type, date_str,
        )
        if entry is None:
            return None, False

        path = Path(entry.payload_path)
        if not path.exists():
            return None, False

        try:
            computed = datetime.fromisoformat(entry.computed_at).replace(
                tzinfo=timezone.utc,
            )
        except ValueError:
            return None, False

        age_hours = (datetime.now(timezone.utc) - computed).total_seconds() / 3600
        if age_hours > REPORT_CACHE_TTL_HOURS:
            return None, False

        return path, True

    def _write_cache(
            self, report_type: str, date_str: str, data: list,
    ) -> None:
        """Write JSON payload to file and upsert cache metadata row.

        Args:
            report_type: Cache type key.
            date_str: Date string (YYYY-MM-DD).
            data: Serializable list to store as JSON.
        """
        assert self._reports_dir is not None
        assert self._cache_store is not None

        filename = f'{report_type}_{date_str}.json'
        path = self._reports_dir / filename
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

        entry = ReportCacheEntry(
            profile_name=self._profile_name,
            seller_id=None,
            report_type=report_type,
            date=date_str,
            payload_path=str(path),
            computed_at=_utc_now_iso(),
        )
        self._cache_store.save_report_cache(entry)
        logger.debug(
            'Cached %s/%s at %s', report_type, date_str, path,
        )


# ── Aggregation helpers ──────────────────────────────────────────────


def _physical_warehouses(item: WarehouseRemainItem) -> list[WarehouseStock]:
    """Return real warehouse entries, dropping WB's synthetic rows.

    Excludes the duplicate ``Всего находится на складах`` aggregate (never a
    real warehouse) and ``В пути`` in-transit rows, so quantities are not
    double-counted.

    Args:
        item: A parsed warehouse-remains item.

    Returns:
        Warehouse entries that represent physical, on-shelf stock.
    """
    return [
        wh for wh in item.warehouses
        if not wh.warehouse_name.startswith(EXCLUDED_WAREHOUSE_PREFIXES)
    ]


def _aggregate_top(
        items: list[WarehouseRemainItem],
        limit: int,
) -> list[ProductStockSummary]:
    """Aggregate items by nm_id and return top N by total quantity.

    Args:
        items: Raw warehouse remain items (may have duplicates per nm_id).
        limit: Number of top products to return.

    Returns:
        Sorted list of ProductStockSummary.
    """
    by_nm: dict[int, ProductStockSummary] = {}
    for item in items:
        if item.nm_id not in by_nm:
            by_nm[item.nm_id] = ProductStockSummary(
                nm_id=item.nm_id,
                brand=item.brand,
                subject_name=item.subject_name,
                vendor_code=item.vendor_code,
                total_quantity=0,
                warehouses=[],
            )
        summary = by_nm[item.nm_id]
        for wh in _physical_warehouses(item):
            summary.total_quantity += wh.quantity
            summary.warehouses.append(
                WarehouseStock(
                    warehouse_name=wh.warehouse_name,
                    quantity=wh.quantity,
                )
            )

    sorted_items = sorted(
        by_nm.values(),
        key=lambda s: s.total_quantity,
        reverse=True,
    )
    return sorted_items[:limit]


# ── Cache deserialisation ────────────────────────────────────────────


def _load_stock_items(path: Path) -> list[WarehouseRemainItem]:
    """Load WarehouseRemainItem list from a cached JSON file.

    Args:
        path: Path to the JSON file written by _write_cache.

    Returns:
        List of WarehouseRemainItem.
    """
    data = json.loads(path.read_text(encoding='utf-8'))
    return [_stock_item_from_dict(d) for d in data]


def _load_sale_records(path: Path) -> list[SaleRecord]:
    """Load SaleRecord list from a cached JSON file.

    Args:
        path: Path to the JSON file written by _write_cache.

    Returns:
        List of SaleRecord.
    """
    data = json.loads(path.read_text(encoding='utf-8'))
    return [_sale_record_from_dict(d) for d in data]


def _stock_item_from_dict(d: dict) -> WarehouseRemainItem:
    """Deserialise a WarehouseRemainItem from a snake_case dict (cache format).

    Args:
        d: Dict with snake_case fields as produced by dataclasses.asdict().
    """
    warehouses = [
        WarehouseStock(
            warehouse_name=w['warehouse_name'],
            quantity=w['quantity'],
        )
        for w in d.get('warehouses', [])
    ]
    return WarehouseRemainItem(
        brand=d.get('brand', ''),
        subject_name=d.get('subject_name', ''),
        vendor_code=d.get('vendor_code', ''),
        nm_id=d.get('nm_id', 0),
        barcode=d.get('barcode', ''),
        tech_size=d.get('tech_size', ''),
        volume=d.get('volume', 0.0),
        warehouses=warehouses,
    )


def _sale_record_from_dict(d: dict) -> SaleRecord:
    """Deserialise a SaleRecord from a snake_case dict (cache format).

    Args:
        d: Dict with snake_case fields as produced by dataclasses.asdict().
    """
    return SaleRecord(
        nm_id=d.get('nm_id', 0),
        date=d.get('date', ''),
        quantity=d.get('quantity', 0),
    )


# ── Runway computation ───────────────────────────────────────────────


def _build_velocity_map(
        sales: list[SaleRecord],
        period_days: int,
) -> tuple[dict[int, float], dict[int, int]]:
    """Compute avg daily sales and distinct sale-days per nm_id.

    Args:
        sales: List of SaleRecord from the Statistics API.
        period_days: Length of the lookback window in days.

    Returns:
        Tuple of (velocity_map, sale_days_map):
            velocity_map: nm_id → avg units sold per day.
            sale_days_map: nm_id → number of days with at least one sale.
    """
    total_sales: dict[int, int] = {}
    sale_day_sets: dict[int, set[str]] = {}
    for rec in sales:
        nm = rec.nm_id
        total_sales[nm] = total_sales.get(nm, 0) + rec.quantity
        if nm not in sale_day_sets:
            sale_day_sets[nm] = set()
        sale_day_sets[nm].add(rec.date)

    velocity_map = {
        nm: total / period_days
        for nm, total in total_sales.items()
    }
    sale_days_map = {nm: len(days) for nm, days in sale_day_sets.items()}
    return velocity_map, sale_days_map


def _runway_alert(days: int | None) -> str | None:
    """Return alert level for a given days-of-stock value."""
    if days is None:
        return None
    if days <= RUNWAY_ALERT_CRITICAL_DAYS:
        return 'critical'
    if days <= RUNWAY_ALERT_LOW_DAYS:
        return 'low'
    return None


def _runway_confidence(sale_days: int) -> str:
    """Return confidence label based on number of sale-days observed."""
    if sale_days == 0:
        return 'none'
    if sale_days >= RUNWAY_CONFIDENCE_HIGH_DAYS:
        return 'high'
    if sale_days >= RUNWAY_CONFIDENCE_MEDIUM_DAYS:
        return 'medium'
    return 'low'


def _compute_runway_item(
        item: WarehouseRemainItem,
        velocity_map: dict[int, float],
        sale_days_map: dict[int, int],
        period_days: int,
) -> StockRunwayItem:
    """Build a StockRunwayItem for a single product.

    Args:
        item: WarehouseRemainItem with per-warehouse stock data.
        velocity_map: nm_id → avg daily sales.
        sale_days_map: nm_id → observed sale-day count.
        period_days: Sales lookback window (used for confidence fallback).

    Returns:
        StockRunwayItem with per-warehouse runway data.
    """
    avg_daily = velocity_map.get(item.nm_id, 0.0)
    sale_days = sale_days_map.get(item.nm_id, 0)
    confidence = _runway_confidence(sale_days)

    physical_wh = _physical_warehouses(item)

    wh_runways = []
    for wh in physical_wh:
        if avg_daily > 0:
            days = int(wh.quantity / avg_daily)
        else:
            days = None
        wh_runways.append(WarehouseRunway(
            warehouse_name=wh.warehouse_name,
            quantity=wh.quantity,
            days_of_stock=days,
            alert=_runway_alert(days),
        ))

    total_stock = sum(wh.quantity for wh in physical_wh)
    total_days = int(total_stock / avg_daily) if avg_daily > 0 else None
    worst_alert = _worst_alert([r.alert for r in wh_runways])

    return StockRunwayItem(
        nm_id=item.nm_id,
        avg_daily_sales=round(avg_daily, 4),
        confidence=confidence,
        total_stock=total_stock,
        total_days_of_stock=total_days,
        alert=worst_alert,
        warehouses=wh_runways,
    )


def _worst_alert(alerts: list[str | None]) -> str | None:
    """Return the most severe alert from a list."""
    if 'critical' in alerts:
        return 'critical'
    if 'low' in alerts:
        return 'low'
    return None


def _utc_now_iso() -> str:
    """Return current UTC datetime as an ISO string (seconds precision)."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
