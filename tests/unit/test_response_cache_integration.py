"""Tests that StatsService and AnalyticsService honour the response cache."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from wb.domain.analytics_models import ProductFunnelHistory, ProductFunnelStats
from wb.services.analytics import AnalyticsService
from wb.services.stats import StatsService
from wb.storage.response_cache import ResponseCache


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def cache(tmp_path):
    return ResponseCache(tmp_path / 'response_cache.db', retention_days=90)


@pytest.fixture
def today_iso():
    from datetime import date
    return date.today().isoformat()


@pytest.fixture
def past_date_iso():
    from datetime import date, timedelta
    return (date.today() - timedelta(days=3)).isoformat()


# ── StatsService.get_product_spend ────────────────────────────────────

class TestStatsCaching:
    """StatsService serves past-day product_spend queries from the cache."""

    def _make_service(self, cache):
        client = MagicMock()
        client.list_campaigns.return_value = [
            {
                'id': 1001,
                'status': 9,
                'nm_settings': [{'nm_id': 42}],
            },
        ]
        client.get_campaign_stats.return_value = [{
            'advertId': 1001,
            'sum_price': 100,
            'days': [{
                'date': '2026-04-22',
                'apps': [{
                    'nm': [{
                        'nmId': 42, 'name': 'X', 'views': 10,
                        'clicks': 1, 'sum': 50.0, 'orders': 1,
                    }],
                }],
            }],
        }]
        svc = StatsService(
            client=client,
            response_cache=cache,
            cache_token='fake-token',
        )
        return svc, client

    def test_past_day_first_call_fetches_second_call_hits_cache(
            self, cache, past_date_iso,
    ):
        svc, client = self._make_service(cache)
        first = svc.get_product_spend([42], past_date_iso, past_date_iso)
        second = svc.get_product_spend([42], past_date_iso, past_date_iso)

        assert first == second
        # Second call must not have triggered any fresh HTTP calls.
        assert client.list_campaigns.call_count == 1
        assert client.get_campaign_stats.call_count == 1

    def test_current_day_is_never_cached(self, cache, today_iso):
        svc, client = self._make_service(cache)
        svc.get_product_spend([42], today_iso, today_iso)
        svc.get_product_spend([42], today_iso, today_iso)

        # Both calls hit the API — today's data is mutable.
        assert client.list_campaigns.call_count == 2

    def test_no_cache_configured_still_works(self, past_date_iso):
        client = MagicMock()
        client.list_campaigns.return_value = []
        svc = StatsService(client=client)  # no response_cache
        result = svc.get_product_spend([42], past_date_iso, past_date_iso)
        assert result == [pytest.importorskip('wb.domain.models').NmStats(nm_id=42)]

    def test_different_nm_ids_do_not_collide(self, cache, past_date_iso):
        svc, client = self._make_service(cache)
        svc.get_product_spend([42], past_date_iso, past_date_iso)
        svc.get_product_spend([99], past_date_iso, past_date_iso)
        # Separate cache entries → two fetches (client called for each).
        assert client.list_campaigns.call_count == 2


# ── AnalyticsService.get_product_funnel ───────────────────────────────

class TestAnalyticsCaching:
    """AnalyticsService serves past-day funnel queries from the cache."""

    def _make_service(self, cache):
        client = MagicMock()
        client.get_funnel_products.return_value = {
            'data': {
                'currency': 'RUB',
                'products': [{
                    'product': {'nmId': 42, 'title': 'X'},
                    'statistic': {
                        'selected': {
                            'openCount': 10,
                            'orderCount': 2,
                            'conversions': {},
                        },
                    },
                }],
            },
        }
        svc = AnalyticsService(
            client=client,
            response_cache=cache,
            cache_token='analytics-token',
        )
        return svc, client

    def test_past_day_funnel_cache_hit_on_second_call(
            self, cache, past_date_iso,
    ):
        svc, client = self._make_service(cache)
        first = svc.get_product_funnel(
            past_date_iso, past_date_iso, nm_ids=[42],
        )
        second = svc.get_product_funnel(
            past_date_iso, past_date_iso, nm_ids=[42],
        )

        assert len(first) == 1
        assert first[0].nm_id == second[0].nm_id == 42
        assert client.get_funnel_products.call_count == 1

    def test_current_day_funnel_is_never_cached(self, cache, today_iso):
        svc, client = self._make_service(cache)
        svc.get_product_funnel(today_iso, today_iso, nm_ids=[42])
        svc.get_product_funnel(today_iso, today_iso, nm_ids=[42])
        assert client.get_funnel_products.call_count == 2

    def test_history_cache_preserves_nested_days(
            self, cache, past_date_iso,
    ):
        client = MagicMock()
        client.get_funnel_history.return_value = [{
            'product': {'nmId': 42, 'title': 'X'},
            'currency': 'RUB',
            'history': [
                {'dt': '2026-04-22', 'openCount': 5, 'orderCount': 1},
                {'dt': '2026-04-23', 'openCount': 8, 'orderCount': 2},
            ],
        }]
        svc = AnalyticsService(
            client=client,
            response_cache=cache,
            cache_token='analytics-token',
        )
        svc.get_product_history(past_date_iso, past_date_iso, nm_ids=[42])
        cached = svc.get_product_history(
            past_date_iso, past_date_iso, nm_ids=[42],
        )
        assert client.get_funnel_history.call_count == 1
        assert isinstance(cached[0], ProductFunnelHistory)
        assert len(cached[0].history) == 2
        assert cached[0].history[0].dt == '2026-04-22'
        assert cached[0].history[1].order_count == 2
