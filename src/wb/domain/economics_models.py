"""Domain models for per-product unit economics (I-26).

A :class:`ProductEconomics` row joins one product's current stock with its
finance-settlement costs over a reporting period; :class:`EconomicsPeriod`
carries the period-level reconciliation totals. Money fields are floats
(rubles) — already aggregated, so fixed-precision string parity is not needed
here (unlike the raw finance passthrough rows).

Cost model (empirically reconciled against WB's own settlement totals):

``forPay`` is the gross payout for sold items; logistics, storage, deductions,
penalties and acceptance sit on *separate* rows (``forPay = 0``) and are
subtracted from it — WB's identity is::

    bank_payment = forPay - logistics - storage - deduction - penalty - acceptance

Logistics attributes per nmId. Storage and deductions are reported at the
period level with no nmId; in exact mode they stay out of the per-product rows
(surfaced only in :class:`EconomicsPeriod`), and under ``--apportion`` they are
spread across products pro-rata by sales revenue (an estimate). ``net_payout``
then reconciles to WB's bank payment and ``wb_cost_total = revenue -
net_payout`` is the all-in WB cost to sell. Commission and acquiring are
informational sub-components already netted inside the payout.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ['ProductEconomics', 'EconomicsPeriod']


@dataclass(slots=True)
class ProductEconomics:
    """Unit economics for one product over a reporting period.

    Per-sold figures divide period totals by ``units_sold``; per-held figures
    divide by ``units_in_stock`` (estimates — period costs over a current
    stock snapshot). Under ``--apportion`` (``period_costs_apportioned``),
    ``storage_rub``/``deductions_rub`` include an apportioned share of
    period-level costs and are likewise estimates.

    Attributes:
        nm_id: WB article number.
        vendor_code: Seller's article code.
        subject_name: Product subject/category.
        brand: Brand name.
        units_in_stock: Total stock across all warehouses (current snapshot).
        units_sold: Net units sold in the period (sales minus returns).
        revenue: Gross sales revenue in the period (Σ retailAmount).
        avg_sale_price: revenue / units_sold (0 when no sales).
        commission_rub: WB commission as reported (Σ ppvzSalesCommission;
            informational — already inside the payout).
        acquiring_rub: Acquiring/card fee (Σ acquiringFee; informational —
            already inside the payout).
        logistics_rub: Logistics to buyer attributed per nmId
            (Σ deliveryService + rebillLogisticCost).
        storage_rub: Paid storage — 0 in exact mode, apportioned estimate
            under ``--apportion``.
        deductions_rub: Penalties/withholdings/acceptance — 0 in exact mode,
            apportioned estimate under ``--apportion``.
        gross_payout_rub: Gross payout for sold items (Σ forPay).
        net_payout_rub: Payout net of the costs applied in the active mode
            (reconciles to WB's bank payment under ``--apportion``).
        wb_cost_total: WB cost to sell (revenue - net_payout_rub).
        wb_cost_per_sold: wb_cost_total / units_sold (None when no sales).
        period_cost_per_sold: Apportioned storage+deductions per sold unit —
            the soft (estimated) portion (0 in exact mode, None when no sales).
        margin_per_sold: net_payout per sold unit before COGS, i.e.
            avg_sale_price - wb_cost_per_sold (None when no sales).
        margin_pct: margin_per_sold as a percent of avg_sale_price (None when
            no sales).
        wb_cost_per_held: wb_cost_total / units_in_stock (None when no stock).
        storage_per_held: storage_rub / units_in_stock (None when no stock).
        cogs_per_unit: Seller cost of goods per unit, when supplied (else None).
        net_profit_per_sold: margin_per_sold - cogs_per_unit (None without
            COGS/sales).
        period_costs_apportioned: Whether period storage+deductions were folded
            into this row (the ``--apportion`` mode).
        stock_from_cache: Whether the stock snapshot came from the local cache.
    """

    nm_id: int
    vendor_code: str
    subject_name: str
    brand: str
    units_in_stock: int
    units_sold: int
    revenue: float
    avg_sale_price: float
    commission_rub: float
    acquiring_rub: float
    logistics_rub: float
    storage_rub: float
    deductions_rub: float
    gross_payout_rub: float
    net_payout_rub: float
    wb_cost_total: float
    wb_cost_per_sold: float | None
    period_cost_per_sold: float | None
    margin_per_sold: float | None
    margin_pct: float | None
    wb_cost_per_held: float | None
    storage_per_held: float | None
    cogs_per_unit: float | None
    net_profit_per_sold: float | None
    period_costs_apportioned: bool
    stock_from_cache: bool


@dataclass(slots=True)
class EconomicsPeriod:
    """Period-level settlement reconciliation across all products.

    Mirrors WB's settlement identity so the raw period totals (including the
    storage and withholding pools that carry no nmId) are never hidden, even in
    exact mode.

    Attributes:
        revenue: Σ retailAmount over all sale rows.
        gross_payout: Σ forPay (gross payout for sold items).
        logistics: Σ logistics across all rows (per-nm + pool).
        storage: Σ paidStorage (period-level pool).
        deductions: Σ deduction + penalty + acceptance (period-level pool).
        bank_payment: gross_payout - logistics - storage - deductions.
        wb_cost_total: revenue - bank_payment (all-in WB take for the period).
        wb_cost_pct: wb_cost_total as a percent of revenue (0 when no revenue).
        products: Number of products with sales in the period.
    """

    revenue: float
    gross_payout: float
    logistics: float
    storage: float
    deductions: float
    bank_payment: float
    wb_cost_total: float
    wb_cost_pct: float
    products: int
