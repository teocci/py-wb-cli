"""Composite service computing per-product unit economics (I-26).

Joins the warehouse-remains stock snapshot (:class:`ReportsService`) with the
finance settlement detail rows (:class:`FinanceService`). Imitates the
multi-source composition pattern of :class:`wb.services.product.ProductService`.

Cost model (empirically reconciled against WB's settlement totals): ``forPay``
is the gross payout for sold items; logistics, storage, deductions, penalties
and acceptance sit on separate rows (``forPay = 0``) and are subtracted from
it. Logistics attributes per nmId; storage and period deductions carry no nmId
— in exact mode they stay in the period pool (surfaced via
:class:`EconomicsPeriod`); under ``apportion`` they are spread across products
pro-rata by sales revenue. The resulting ``net_payout`` reconciles to WB's bank
payment, and ``wb_cost_total = revenue - net_payout``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from wb.core.constants import (
    ECONOMICS_DEFAULT_MIN_STOCK,
    ECONOMICS_SALE_OPER,
    ECONOMICS_STOCK_LIMIT,
)
from wb.core.exceptions import ValidationError
from wb.domain.economics_models import EconomicsPeriod, ProductEconomics

__all__ = ['EconomicsService']

logger = logging.getLogger(__name__)

_VALID_SCOPES = ('in-stock', 'sold', 'all')
_RETURN_OPERS = ('Возврат',)


def _num(value) -> float:
    """Coerce a WB money field (str/None/number) to float; 0.0 on failure."""
    if value is None or value == '':
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _round_opt(value: float | None) -> float | None:
    """Round to 2 decimals, preserving None."""
    return None if value is None else round(value, 2)


@dataclass(slots=True)
class _Agg:
    """Per-nmId accumulator over finance detail rows."""

    units_sold: int = 0
    revenue: float = 0.0
    gross_payout: float = 0.0
    commission: float = 0.0
    acquiring: float = 0.0
    logistics: float = 0.0
    storage_direct: float = 0.0
    deduction_direct: float = 0.0
    vendor_code: str = ''
    subject_name: str = ''
    brand: str = ''


@dataclass(slots=True)
class _Pool:
    """Period-level costs that carry no nmId (apportioned later)."""

    storage: float = 0.0
    deductions: float = 0.0
    logistics: float = 0.0


class EconomicsService:
    """Aggregate stock + settlement costs into per-product unit economics.

    Attributes:
        reports_service: Warehouse-remains stock source (analytics token).
        finance_service: Settlement-report source (finance token).
    """

    def __init__(self, reports_service, finance_service) -> None:
        self._reports = reports_service
        self._finance = finance_service

    def get_product_economics(
            self,
            *,
            date_from: str,
            date_to: str,
            period: str | None = None,
            scope: str = 'in-stock',
            apportion: bool = False,
            cogs_map: dict[int, float] | None = None,
            min_stock: int = ECONOMICS_DEFAULT_MIN_STOCK,
            use_cache: bool = True,
            fetch_all: bool = True,
    ) -> tuple[list[ProductEconomics], EconomicsPeriod]:
        """Build unit-economics rows + the period reconciliation.

        Args:
            date_from: Reporting-period start (YYYY-MM-DD).
            date_to: Reporting-period end (YYYY-MM-DD).
            period: ``weekly`` (default) or ``daily``.
            scope: ``in-stock`` (default), ``sold``, or ``all``.
            apportion: Fold period storage+deductions into each row pro-rata
                by revenue (estimate) instead of leaving them in the pool.
            cogs_map: Optional per-nmId cost of goods (rubles) for net profit.
            min_stock: Minimum stock to qualify under the in-stock scope.
            use_cache: Reuse a cached stock snapshot when available.
            fetch_all: Exhaust the finance rrdId cursor (1 req/min throttle).

        Returns:
            Tuple of (rows sorted by nmId, period reconciliation).
        """
        scope = self._validate_scope(scope)
        stock_map, from_cache = self._load_stock(use_cache)
        rows = self._finance.detailed_sales_reports(
            date_from=date_from, date_to=date_to,
            period=period, fetch_all=fetch_all,
        )
        aggs, pool = self._aggregate(rows)
        total_rev = sum(a.revenue for a in aggs.values() if a.revenue > 0)
        cogs_map = cogs_map or {}
        nm_ids = self._resolve_scope(scope, stock_map, aggs, min_stock)
        products = [
            self._compute(
                nm_id, stock_map.get(nm_id), aggs.get(nm_id), pool,
                total_rev, apportion, cogs_map.get(nm_id), from_cache,
            )
            for nm_id in nm_ids
        ]
        return products, self._period(aggs, pool, total_rev)

    # ── validation / loading ─────────────────────────────────────────

    @staticmethod
    def _validate_scope(scope: str) -> str:
        """Return ``scope`` when valid; raise otherwise."""
        if scope not in _VALID_SCOPES:
            raise ValidationError(
                f'scope must be one of {_VALID_SCOPES}; got {scope!r}',
            )
        return scope

    def _load_stock(self, use_cache: bool) -> tuple[dict[int, object], bool]:
        """Fetch stock summaries and key them by nmId."""
        summaries, from_cache = self._reports.get_warehouse_top(
            limit=ECONOMICS_STOCK_LIMIT, use_cache=use_cache,
        )
        return {s.nm_id: s for s in summaries}, from_cache

    # ── aggregation ──────────────────────────────────────────────────

    def _aggregate(self, rows: list[dict]) -> tuple[dict[int, _Agg], _Pool]:
        """Group finance rows by nmId; pool nmId-less period costs."""
        aggs: dict[int, _Agg] = {}
        pool = _Pool()
        for row in rows:
            nm_id = self._row_nm_id(row)
            if nm_id is None:
                self._pool_costs(pool, row)
                continue
            self._accumulate(aggs.setdefault(nm_id, _Agg()), row)
        return aggs, pool

    @staticmethod
    def _row_nm_id(row: dict) -> int | None:
        """Coerce a row's nmId to a positive int; None when absent/zero."""
        raw = row.get('nmId')
        if raw in (None, ''):
            return None
        try:
            nm_id = int(raw)
        except (TypeError, ValueError):
            return None
        return nm_id if nm_id > 0 else None

    @staticmethod
    def _pool_costs(pool: _Pool, row: dict) -> None:
        """Add a nmId-less row's separate costs to the period pool."""
        pool.storage += _num(row.get('paidStorage'))
        pool.deductions += _row_deductions(row)
        pool.logistics += _row_logistics(row)

    @staticmethod
    def _accumulate(agg: _Agg, row: dict) -> None:
        """Fold one nmId-bearing detail row into its accumulator."""
        name = row.get('docTypeName') or row.get('sellerOperName') or ''
        qty = int(_num(row.get('quantity')))
        amount = _num(row.get('retailAmount'))
        if name == ECONOMICS_SALE_OPER:
            agg.units_sold += qty
            agg.revenue += amount
        elif name in _RETURN_OPERS:
            agg.units_sold -= qty
            agg.revenue -= amount
        agg.gross_payout += _num(row.get('forPay'))
        agg.commission += _num(row.get('ppvzSalesCommission'))
        agg.acquiring += _num(row.get('acquiringFee'))
        agg.logistics += _row_logistics(row)
        agg.storage_direct += _num(row.get('paidStorage'))
        agg.deduction_direct += _row_deductions(row)
        if not agg.vendor_code:
            agg.vendor_code = row.get('vendorCode', '') or ''
            agg.subject_name = row.get('subjectName', '') or ''
            agg.brand = row.get('brandName', '') or ''

    @staticmethod
    def _resolve_scope(
            scope: str,
            stock_map: dict[int, object],
            aggs: dict[int, _Agg],
            min_stock: int,
    ) -> list[int]:
        """Resolve the nmId universe for the requested scope."""
        in_stock = {
            nm for nm, s in stock_map.items() if s.total_quantity >= min_stock
        }
        if scope == 'in-stock':
            nm_ids = in_stock
        elif scope == 'sold':
            nm_ids = set(aggs.keys())
        else:
            nm_ids = in_stock | set(aggs.keys())
        return sorted(nm_ids)

    # ── per-product assembly ─────────────────────────────────────────

    @staticmethod
    def _compute(
            nm_id: int,
            stock,
            agg: _Agg | None,
            pool: _Pool,
            total_rev: float,
            apportion: bool,
            cogs: float | None,
            from_cache: bool,
    ) -> ProductEconomics:
        """Derive one product's economics for the active cost mode."""
        agg = agg or _Agg()
        units_held = stock.total_quantity if stock else 0
        sold, revenue = agg.units_sold, agg.revenue
        share = (revenue / total_rev) if apportion and total_rev > 0 and revenue > 0 else 0.0
        storage = agg.storage_direct + pool.storage * share
        deductions = agg.deduction_direct + pool.deductions * share
        logistics = agg.logistics + pool.logistics * share
        net_payout = agg.gross_payout - logistics - storage - deductions
        wb_cost_total = revenue - net_payout
        period_cost = storage + deductions
        return ProductEconomics(
            nm_id=nm_id,
            vendor_code=stock.vendor_code if stock else agg.vendor_code,
            subject_name=stock.subject_name if stock else agg.subject_name,
            brand=stock.brand if stock else agg.brand,
            units_in_stock=units_held,
            units_sold=sold,
            revenue=round(revenue, 2),
            avg_sale_price=round(revenue / sold, 2) if sold > 0 else 0.0,
            commission_rub=round(agg.commission, 2),
            acquiring_rub=round(agg.acquiring, 2),
            logistics_rub=round(logistics, 2),
            storage_rub=round(storage, 2),
            deductions_rub=round(deductions, 2),
            gross_payout_rub=round(agg.gross_payout, 2),
            net_payout_rub=round(net_payout, 2),
            wb_cost_total=round(wb_cost_total, 2),
            wb_cost_per_sold=_round_opt(wb_cost_total / sold if sold > 0 else None),
            period_cost_per_sold=_round_opt(period_cost / sold if sold > 0 else None),
            margin_per_sold=_round_opt(net_payout / sold if sold > 0 else None),
            margin_pct=_round_opt(
                net_payout / revenue * 100 if sold > 0 and revenue > 0 else None,
            ),
            wb_cost_per_held=_round_opt(
                wb_cost_total / units_held if units_held > 0 else None,
            ),
            storage_per_held=_round_opt(
                storage / units_held if units_held > 0 else None,
            ),
            cogs_per_unit=cogs,
            net_profit_per_sold=_round_opt(
                net_payout / sold - cogs
                if sold > 0 and cogs is not None else None,
            ),
            period_costs_apportioned=apportion,
            stock_from_cache=from_cache,
        )

    @staticmethod
    def _period(
            aggs: dict[int, _Agg],
            pool: _Pool,
            total_rev: float,
    ) -> EconomicsPeriod:
        """Build the period-level settlement reconciliation."""
        gross_payout = sum(a.gross_payout for a in aggs.values())
        logistics = sum(a.logistics for a in aggs.values()) + pool.logistics
        storage = sum(a.storage_direct for a in aggs.values()) + pool.storage
        deductions = sum(a.deduction_direct for a in aggs.values()) + pool.deductions
        bank = gross_payout - logistics - storage - deductions
        wb_cost = total_rev - bank
        return EconomicsPeriod(
            revenue=round(total_rev, 2),
            gross_payout=round(gross_payout, 2),
            logistics=round(logistics, 2),
            storage=round(storage, 2),
            deductions=round(deductions, 2),
            bank_payment=round(bank, 2),
            wb_cost_total=round(wb_cost, 2),
            wb_cost_pct=round(wb_cost / total_rev * 100, 2) if total_rev > 0 else 0.0,
            products=sum(1 for a in aggs.values() if a.revenue > 0),
        )


def _row_logistics(row: dict) -> float:
    """Logistics cost on a row (delivery to buyer + rebill)."""
    return _num(row.get('deliveryService')) + _num(row.get('rebillLogisticCost'))


def _row_deductions(row: dict) -> float:
    """Withholding-type cost on a row (deduction + penalty + acceptance)."""
    return (
        _num(row.get('deduction')) + _num(row.get('penalty'))
        + _num(row.get('paidAcceptance'))
    )
