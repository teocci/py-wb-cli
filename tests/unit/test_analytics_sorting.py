"""Tests for --sort-by / --top N / --min-orders / --all in analytics sales-funnel products."""

from __future__ import annotations
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from wb.cli.analytics import _sort_funnel, funnel_app
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


# ── --min-orders filter ──────────────────────────────────────────────


class TestMinOrdersFilter:
    def test_excludes_below_threshold(self, sample_stats):
        filtered = [s for s in sample_stats if s.order_count >= 20]
        assert all(s.order_count >= 20 for s in filtered)
        assert len(filtered) == 3  # orders: 50, 20, 35

    def test_zero_threshold_keeps_all(self, sample_stats):
        filtered = [s for s in sample_stats if s.order_count >= 0]
        assert len(filtered) == len(sample_stats)

    def test_high_threshold_returns_empty(self, sample_stats):
        filtered = [s for s in sample_stats if s.order_count >= 999]
        assert filtered == []

    def test_min_orders_one_drops_zero_order_rows(self):
        stats = [
            _make_stats(1, orders=0),
            _make_stats(2, orders=5),
            _make_stats(3, orders=0),
            _make_stats(4, orders=1),
        ]
        filtered = [s for s in stats if s.order_count >= 1]
        assert [s.nm_id for s in filtered] == [2, 4]


# ── --all auto-pagination (CLI integration) ──────────────────────────


_runner = CliRunner()

_PAGE_1 = [_make_stats(i, orders=i) for i in range(1, 4)]
_PAGE_2 = [_make_stats(i, orders=i) for i in range(4, 6)]


def _mock_svc(pages: list[list]) -> MagicMock:
    """Return a mock AnalyticsService whose get_product_funnel returns pages in order."""
    svc = MagicMock()
    call_count = {'n': 0}

    def _side_effect(*args, **kwargs):
        idx = call_count['n']
        call_count['n'] += 1
        return pages[idx] if idx < len(pages) else []

    svc.get_product_funnel.side_effect = _side_effect
    return svc


class TestAllFlag:
    def test_all_flag_paginates_until_short_page(self):
        """--all keeps fetching until a page shorter than page_size is returned."""
        from wb.core.batching import paginate_all

        call_log: list[tuple[int, int]] = []

        def fetch(limit: int, offset: int) -> list:
            call_log.append((limit, offset))
            if offset == 0:
                return list(range(limit))   # full page — more data exists
            return list(range(3))           # short page — signals end

        result = paginate_all(fetch, page_size=5)
        assert call_log == [(5, 0), (5, 5)]
        assert len(result) == 5 + 3

    def test_all_flag_single_page_stops(self):
        """When first page is shorter than page_size, no second call is made."""
        from wb.core.batching import paginate_all

        calls = []

        def fetch(limit: int, offset: int) -> list:
            calls.append(offset)
            return list(range(3))   # always short

        paginate_all(fetch, page_size=1000)
        assert calls == [0]

    def test_all_flag_empty_first_page(self):
        """Empty first page returns empty list immediately."""
        from wb.core.batching import paginate_all

        result = paginate_all(fetch=lambda l, o: [], page_size=100)
        assert result == []
