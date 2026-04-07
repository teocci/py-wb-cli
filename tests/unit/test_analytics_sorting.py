"""Tests for --sort-by / --top N sorting in analytics sales-funnel products."""

from __future__ import annotations

import pytest
import typer

from wb.cli.analytics import _sort_funnel
from wb.domain.analytics_models import ProductFunnelStats


def _make_stats(nm_id: int, orders: int = 0, opens: int = 0,
                cart: int = 0, revenue: int = 0, buyouts: int = 0) -> ProductFunnelStats:
    return ProductFunnelStats(
        nm_id=nm_id,
        order_count=orders,
        open_count=opens,
        cart_count=cart,
        order_sum=revenue,
        buyout_count=buyouts,
    )


@pytest.fixture()
def sample_stats() -> list[ProductFunnelStats]:
    return [
        _make_stats(1, orders=10, opens=500, revenue=15000, buyouts=8),
        _make_stats(2, orders=50, opens=200, revenue=5000,  buyouts=40),
        _make_stats(3, orders=5,  opens=800, revenue=30000, buyouts=3),
        _make_stats(4, orders=20, opens=100, revenue=8000,  buyouts=15),
        _make_stats(5, orders=35, opens=400, revenue=2000,  buyouts=25),
    ]


class TestSortFunnel:
    def test_sort_by_orders(self, sample_stats):
        result = _sort_funnel(sample_stats, 'orders', None)
        order_counts = [s.order_count for s in result]
        assert order_counts == sorted(order_counts, reverse=True)

    def test_sort_by_opens(self, sample_stats):
        result = _sort_funnel(sample_stats, 'opens', None)
        values = [s.open_count for s in result]
        assert values == sorted(values, reverse=True)

    def test_sort_by_cart(self, sample_stats):
        stats = [_make_stats(i, cart=i * 10) for i in range(5)]
        result = _sort_funnel(stats, 'cart', None)
        values = [s.cart_count for s in result]
        assert values == sorted(values, reverse=True)

    def test_sort_by_revenue(self, sample_stats):
        result = _sort_funnel(sample_stats, 'revenue', None)
        values = [s.order_sum for s in result]
        assert values == sorted(values, reverse=True)

    def test_sort_by_buyouts(self, sample_stats):
        result = _sort_funnel(sample_stats, 'buyouts', None)
        values = [s.buyout_count for s in result]
        assert values == sorted(values, reverse=True)

    def test_top_n_limits_results(self, sample_stats):
        result = _sort_funnel(sample_stats, None, 2)
        assert len(result) == 2

    def test_sort_then_top(self, sample_stats):
        result = _sort_funnel(sample_stats, 'orders', 3)
        assert len(result) == 3
        # First result must be the highest-order product (nm_id=2, orders=50)
        assert result[0].nm_id == 2
        assert result[1].nm_id == 5  # orders=35
        assert result[2].nm_id == 4  # orders=20

    def test_no_sort_no_top_returns_original(self, sample_stats):
        result = _sort_funnel(sample_stats, None, None)
        assert [s.nm_id for s in result] == [s.nm_id for s in sample_stats]

    def test_top_larger_than_list_returns_all(self, sample_stats):
        result = _sort_funnel(sample_stats, None, 100)
        assert len(result) == len(sample_stats)

    def test_invalid_sort_field_raises(self, sample_stats):
        with pytest.raises(typer.BadParameter, match='Unknown sort field'):
            _sort_funnel(sample_stats, 'nonexistent', None)

    def test_invalid_sort_field_message_lists_valid_options(self, sample_stats):
        with pytest.raises(typer.BadParameter) as exc_info:
            _sort_funnel(sample_stats, 'xyz', None)
        msg = str(exc_info.value)
        # All valid aliases should appear in the error
        for alias in ('orders', 'opens', 'cart', 'revenue', 'buyouts'):
            assert alias in msg
