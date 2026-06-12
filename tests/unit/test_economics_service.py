"""Tests for :class:`wb.services.economics.EconomicsService` (I-26)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wb.core.exceptions import ValidationError
from wb.domain.report_models import ProductStockSummary
from wb.services.economics import EconomicsService


def _stock(nm_id: int, qty: int, vendor: str = 'VC') -> ProductStockSummary:
    return ProductStockSummary(
        nm_id=nm_id, brand='Brand', subject_name='Subject',
        vendor_code=vendor, total_quantity=qty,
    )


def _sale_row(nm_id: int, *, qty=1, amount='1000', pay='800',
              commission='150', delivery='30', acquiring='5', vendor='VC') -> dict:
    return {
        'nmId': nm_id, 'docTypeName': 'Продажа', 'sellerOperName': 'Продажа',
        'quantity': qty, 'retailAmount': amount, 'forPay': pay,
        'ppvzSalesCommission': commission, 'deliveryService': delivery,
        'rebillLogisticCost': '0', 'acquiringFee': acquiring, 'vendorCode': vendor,
        'subjectName': 'Subject', 'brandName': 'Brand',
    }


def _logistics_row(nm_id: int, *, delivery='40') -> dict:
    return {'nmId': nm_id, 'sellerOperName': 'Логистика', 'deliveryService': delivery}


def _storage_row(amount='200') -> dict:
    # Period-level storage carries no nmId.
    return {'nmId': 0, 'sellerOperName': 'Хранение', 'paidStorage': amount}


def _deduction_row(amount='500') -> dict:
    return {'nmId': 0, 'sellerOperName': 'Удержание', 'deduction': amount}


def _return_row(nm_id: int, *, qty=1, amount='1000', pay='800') -> dict:
    return {
        'nmId': nm_id, 'docTypeName': 'Возврат', 'sellerOperName': 'Возврат',
        'quantity': qty, 'retailAmount': amount, 'forPay': pay,
    }


def _make_service(stock, rows, *, from_cache=False) -> EconomicsService:
    reports = MagicMock()
    reports.get_warehouse_top.return_value = (stock, from_cache)
    finance = MagicMock()
    finance.detailed_sales_reports.return_value = rows
    return EconomicsService(reports, finance)


def _run(svc, **kwargs):
    base = {'date_from': '2026-05-01', 'date_to': '2026-05-31'}
    return svc.get_product_economics(**{**base, **kwargs})


class TestExactMode:
    def test_basic_sale_economics(self):
        svc = _make_service([_stock(1, 10)], [_sale_row(1, qty=2, amount='2000', pay='1500', delivery='100')])
        rows, _ = _run(svc)
        (e,) = rows
        assert e.units_in_stock == 10
        assert e.units_sold == 2
        assert e.revenue == 2000.0
        assert e.gross_payout_rub == 1500.0
        # Exact: net = gross_payout - direct logistics (100); no period costs.
        assert e.logistics_rub == 100.0
        assert e.storage_rub == 0.0
        assert e.deductions_rub == 0.0
        assert e.net_payout_rub == 1400.0
        assert e.wb_cost_total == 600.0
        assert e.avg_sale_price == 1000.0
        assert e.wb_cost_per_sold == 300.0
        assert e.margin_per_sold == 700.0
        assert e.margin_pct == 70.0
        assert e.period_costs_apportioned is False

    def test_exact_excludes_pool(self):
        rows = [_sale_row(1, qty=2, amount='2000', pay='1600', delivery='0'),
                _storage_row('200'), _deduction_row('300')]
        svc = _make_service([_stock(1, 5)], rows)
        products, period = _run(svc, apportion=False)
        (e,) = products
        # Pool stays out of the product row in exact mode.
        assert e.storage_rub == 0.0
        assert e.deductions_rub == 0.0
        assert e.net_payout_rub == 1600.0
        # But the period reconciliation still carries them.
        assert period.storage == 200.0
        assert period.deductions == 300.0

    def test_returns_reduce_units_sold(self):
        rows = [_sale_row(1, qty=3, amount='3000', pay='2400', delivery='0'),
                _return_row(1, qty=1, amount='1000', pay='-800')]
        svc = _make_service([_stock(1, 5)], rows)
        (rows_out, _) = _run(svc)
        (e,) = rows_out
        assert e.units_sold == 2
        assert e.revenue == 2000.0
        assert e.gross_payout_rub == 1600.0  # 2400 + (-800)


class TestApportionMode:
    def test_pool_split_pro_rata(self):
        # Two products, revenue 3000 / 1000 → 75% / 25% of a 400 storage pool.
        rows = [
            _sale_row(1, qty=3, amount='3000', pay='3000', delivery='0'),
            _sale_row(2, qty=1, amount='1000', pay='1000', delivery='0'),
            _storage_row('400'),
        ]
        svc = _make_service([_stock(1, 5), _stock(2, 5)], rows)
        products, period = _run(svc, scope='all', apportion=True)
        by_id = {e.nm_id: e for e in products}
        assert by_id[1].storage_rub == 300.0  # 75%
        assert by_id[2].storage_rub == 100.0  # 25%
        assert all(e.period_costs_apportioned for e in products)

    def test_reconciles_to_bank_payment(self):
        rows = [
            _sale_row(1, qty=3, amount='3000', pay='3000', delivery='50'),
            _sale_row(2, qty=1, amount='1000', pay='1000', delivery='30'),
            _logistics_row(1, delivery='20'),
            _storage_row('400'),
            _deduction_row('600'),
        ]
        svc = _make_service([_stock(1, 5), _stock(2, 5)], rows)
        products, period = _run(svc, scope='all', apportion=True)
        total_net = round(sum(e.net_payout_rub for e in products), 2)
        # Σ net_payout must equal WB's bank payment (the reconciliation invariant).
        assert total_net == period.bank_payment

    def test_zero_revenue_gets_no_pool(self):
        rows = [_sale_row(1, qty=2, amount='2000', pay='2000'), _storage_row('400')]
        svc = _make_service([_stock(1, 5), _stock(9, 5)], rows)
        products, _ = _run(svc, scope='all', apportion=True)
        by_id = {e.nm_id: e for e in products}
        assert by_id[1].storage_rub == 400.0  # only product with revenue
        assert by_id[9].storage_rub == 0.0


class TestPeriodReconciliation:
    def test_period_totals(self):
        rows = [
            _sale_row(1, qty=2, amount='2000', pay='1800', delivery='100'),
            _storage_row('200'), _deduction_row('300'),
        ]
        svc = _make_service([_stock(1, 5)], rows)
        _, period = _run(svc)
        assert period.revenue == 2000.0
        assert period.gross_payout == 1800.0
        assert period.logistics == 100.0
        assert period.storage == 200.0
        assert period.deductions == 300.0
        # bank = 1800 - 100 - 200 - 300
        assert period.bank_payment == 1200.0
        assert period.wb_cost_total == 800.0
        assert period.products == 1


class TestScopeAndEdgeCases:
    def test_in_stock_filters_zero_stock(self):
        svc = _make_service([_stock(1, 0), _stock(2, 5)], [])
        results, _ = _run(svc, scope='in-stock')
        assert [e.nm_id for e in results] == [2]

    def test_min_stock_threshold(self):
        svc = _make_service([_stock(1, 3), _stock(2, 10)], [])
        results, _ = _run(svc, scope='in-stock', min_stock=5)
        assert [e.nm_id for e in results] == [2]

    def test_scope_sold_includes_out_of_stock(self):
        svc = _make_service([_stock(1, 5)], [_sale_row(9, vendor='OOS')])
        results, _ = _run(svc, scope='sold')
        assert [e.nm_id for e in results] == [9]
        assert results[0].vendor_code == 'OOS'
        assert results[0].units_in_stock == 0

    def test_scope_all_is_union(self):
        svc = _make_service([_stock(1, 5)], [_sale_row(9)])
        results, _ = _run(svc, scope='all')
        assert sorted(e.nm_id for e in results) == [1, 9]

    def test_zero_sales_no_division_error(self):
        svc = _make_service([_stock(1, 5)], [])
        (rows, _) = _run(svc)
        (e,) = rows
        assert e.units_sold == 0
        assert e.avg_sale_price == 0.0
        assert e.wb_cost_per_sold is None
        assert e.margin_per_sold is None
        assert e.margin_pct is None

    def test_nm_id_string_coercion_on_join(self):
        row = _sale_row(1)
        row['nmId'] = '1'
        svc = _make_service([_stock(1, 5)], [row])
        (rows, _) = _run(svc)
        assert rows[0].units_sold == 1

    def test_nm_id_zero_routed_to_pool_not_product(self):
        # A storage row with nmId=0 must not create a phantom product 0.
        svc = _make_service([_stock(1, 5)], [_sale_row(1, amount='1000', pay='1000'), _storage_row('200')])
        results, period = _run(svc, scope='all', apportion=True)
        assert 0 not in {e.nm_id for e in results}
        assert period.storage == 200.0

    def test_invalid_scope_raises(self):
        svc = _make_service([], [])
        with pytest.raises(ValidationError):
            _run(svc, scope='bogus')

    def test_from_cache_flag_propagates(self):
        svc = _make_service([_stock(1, 5)], [], from_cache=True)
        (rows, _) = _run(svc)
        assert rows[0].stock_from_cache is True


class TestCogs:
    def test_net_profit_with_cogs(self):
        svc = _make_service([_stock(1, 10)], [_sale_row(1, qty=2, amount='2000', pay='1600', delivery='0')])
        (rows, _) = _run(svc, cogs_map={1: 100.0})
        (e,) = rows
        assert e.cogs_per_unit == 100.0
        # margin_per_sold = 1600/2 = 800; net profit = 800 - 100.
        assert e.margin_per_sold == 800.0
        assert e.net_profit_per_sold == 700.0

    def test_no_cogs_leaves_net_none(self):
        svc = _make_service([_stock(1, 10)], [_sale_row(1)])
        (rows, _) = _run(svc)
        assert rows[0].cogs_per_unit is None
        assert rows[0].net_profit_per_sold is None
