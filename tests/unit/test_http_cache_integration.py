"""Integration tests for the I-15 cache wired into WbHttpClient.

Uses respx to mock the underlying HTTP and a real
:class:`RequestCache` (backed by SQLite in tmp_path) to exercise the
full flow: cache miss → reserve → send → put; cache hit → no HTTP;
mutation → invalidate; ``no_cache=True`` → bypass; ``RateLimitError``
double-check.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from wb.client.http import WbHttpClient
from wb.core.cache_policy import canonical_hash
from wb.core.constants import (
    EP_ACCOUNT_BALANCE,
    EP_CAMPAIGN_BUDGET,
    EP_CAMPAIGN_INFO,
    EP_CAMPAIGN_START,
)
from wb.core.exceptions import RateLimitError
from wb.storage.request_cache import RequestCache

BASE_URL = 'https://test-api.example.com'


def _make_client(
        cache: RequestCache,
        *,
        token: str = 'test-token',
        token_fp: str = 'fp1',
        token_type: str = 'base',
        no_cache: bool = False,
        budget=None,
) -> WbHttpClient:
    return WbHttpClient(
        BASE_URL,
        token,
        max_retries=0,  # keep tests deterministic; no retry sleeps
        budget=budget,
        token_fp=token_fp,
        seller_id=None,
        token_type=token_type,
        request_cache=cache,
        no_cache=no_cache,
    )


class TestCacheHitMiss:
    """Cache hit returns immediately; miss triggers HTTP and writes back."""

    def test_first_call_hits_http_and_writes_cache(self, tmp_path: Path) -> None:
        cache = RequestCache(db_path=tmp_path / 'r.db')
        with respx.mock:
            route = respx.get(f'{BASE_URL}{EP_CAMPAIGN_INFO}').mock(
                return_value=httpx.Response(200, json={'adverts': [{'id': 1}]}),
            )
            with _make_client(cache) as client:
                result = client.get(EP_CAMPAIGN_INFO)
                assert result == {'adverts': [{'id': 1}]}
                assert route.call_count == 1

        # Cache should now hold the entry.
        phash = canonical_hash(None, body=None)
        assert cache.get('fp1', EP_CAMPAIGN_INFO, phash, max_age_seconds=3600) is not None

    def test_second_call_hits_cache_no_http(self, tmp_path: Path) -> None:
        cache = RequestCache(db_path=tmp_path / 'r.db')
        with respx.mock:
            route = respx.get(f'{BASE_URL}{EP_CAMPAIGN_INFO}').mock(
                return_value=httpx.Response(200, json={'adverts': [{'id': 1}]}),
            )
            with _make_client(cache) as client:
                client.get(EP_CAMPAIGN_INFO)
                # Second call: no HTTP fired.
                result = client.get(EP_CAMPAIGN_INFO)
                assert result == {'adverts': [{'id': 1}]}
                assert route.call_count == 1

    def test_different_params_dont_collide(self, tmp_path: Path) -> None:
        cache = RequestCache(db_path=tmp_path / 'r.db')
        with respx.mock:
            route = respx.get(f'{BASE_URL}{EP_CAMPAIGN_INFO}').mock(
                return_value=httpx.Response(200, json={'adverts': []}),
            )
            with _make_client(cache) as client:
                client.get(EP_CAMPAIGN_INFO, params={'statuses': '9'})
                client.get(EP_CAMPAIGN_INFO, params={'statuses': '11'})
                # Different params → different cache keys → two HTTP calls.
                assert route.call_count == 2


class TestNoCacheBypass:
    """`no_cache=True` flag fully disables cache reads and writes."""

    def test_no_cache_bypass_always_hits_http(self, tmp_path: Path) -> None:
        cache = RequestCache(db_path=tmp_path / 'r.db')
        with respx.mock:
            route = respx.get(f'{BASE_URL}{EP_CAMPAIGN_INFO}').mock(
                return_value=httpx.Response(200, json={'adverts': []}),
            )
            with _make_client(cache, no_cache=True) as client:
                client.get(EP_CAMPAIGN_INFO)
                client.get(EP_CAMPAIGN_INFO)
                assert route.call_count == 2

        # Cache stayed empty — neither call wrote it.
        phash = canonical_hash(None, body=None)
        assert cache.get('fp1', EP_CAMPAIGN_INFO, phash, max_age_seconds=3600) is None


class TestNonCacheableEndpoint:
    """Endpoints not in CACHEABLE_ENDPOINTS bypass the cache entirely."""

    def test_mutation_response_not_cached(self, tmp_path: Path) -> None:
        cache = RequestCache(db_path=tmp_path / 'r.db')
        with respx.mock:
            respx.post(f'{BASE_URL}{EP_CAMPAIGN_START}').mock(
                return_value=httpx.Response(200, json={}),
            )
            with _make_client(cache) as client:
                client.post(EP_CAMPAIGN_START, params={'id': 1})

        phash = canonical_hash({'id': 1}, body=None)
        assert cache.get('fp1', EP_CAMPAIGN_START, phash, max_age_seconds=3600) is None


class TestNonSuccessNotCached:
    """Only 2xx responses are written to cache."""

    def test_400_not_cached(self, tmp_path: Path) -> None:
        cache = RequestCache(db_path=tmp_path / 'r.db')
        with respx.mock:
            respx.get(f'{BASE_URL}{EP_CAMPAIGN_INFO}').mock(
                return_value=httpx.Response(400, json={'error': 'bad params'}),
            )
            with _make_client(cache) as client:
                from wb.core.exceptions import ApiError
                with pytest.raises(ApiError):
                    client.get(EP_CAMPAIGN_INFO, params={'bogus': 'x'})

        phash = canonical_hash({'bogus': 'x'}, body=None)
        assert cache.get('fp1', EP_CAMPAIGN_INFO, phash, max_age_seconds=3600) is None


class TestMutationInvalidation:
    """Successful mutations drop related cached reads."""

    def test_campaign_start_invalidates_campaign_info(self, tmp_path: Path) -> None:
        cache = RequestCache(db_path=tmp_path / 'r.db')
        with respx.mock:
            respx.get(f'{BASE_URL}{EP_CAMPAIGN_INFO}').mock(
                return_value=httpx.Response(200, json={'adverts': [{'id': 1}]}),
            )
            respx.post(f'{BASE_URL}{EP_CAMPAIGN_START}').mock(
                return_value=httpx.Response(200, json={}),
            )
            with _make_client(cache) as client:
                # Populate cache.
                client.get(EP_CAMPAIGN_INFO)
                phash = canonical_hash(None, body=None)
                assert cache.get(
                    'fp1', EP_CAMPAIGN_INFO, phash, max_age_seconds=3600,
                ) is not None
                # Mutation must invalidate.
                client.post(EP_CAMPAIGN_START, params={'id': 1})
                assert cache.get(
                    'fp1', EP_CAMPAIGN_INFO, phash, max_age_seconds=3600,
                ) is None

    def test_failed_mutation_does_not_invalidate(self, tmp_path: Path) -> None:
        cache = RequestCache(db_path=tmp_path / 'r.db')
        with respx.mock:
            respx.get(f'{BASE_URL}{EP_CAMPAIGN_INFO}').mock(
                return_value=httpx.Response(200, json={'adverts': []}),
            )
            respx.post(f'{BASE_URL}{EP_CAMPAIGN_START}').mock(
                return_value=httpx.Response(400, json={'error': 'nope'}),
            )
            with _make_client(cache) as client:
                client.get(EP_CAMPAIGN_INFO)
                from wb.core.exceptions import ApiError
                with pytest.raises(ApiError):
                    client.post(EP_CAMPAIGN_START, params={'id': 1})

        # Cache survived the failed mutation.
        phash = canonical_hash(None, body=None)
        assert cache.get(
            'fp1', EP_CAMPAIGN_INFO, phash, max_age_seconds=3600,
        ) is not None

    def test_budget_deposit_invalidates_balance(self, tmp_path: Path) -> None:
        cache = RequestCache(db_path=tmp_path / 'r.db')
        with respx.mock:
            respx.get(f'{BASE_URL}{EP_ACCOUNT_BALANCE}').mock(
                return_value=httpx.Response(
                    200, json={'balance': 100, 'net': 100, 'bonus': 0},
                ),
            )
            respx.get(f'{BASE_URL}{EP_CAMPAIGN_BUDGET}').mock(
                return_value=httpx.Response(200, json={'total': 50}),
            )
            respx.post(f'{BASE_URL}/adv/v1/budget/deposit').mock(
                return_value=httpx.Response(200, json={}),
            )
            with _make_client(cache) as client:
                client.get(EP_ACCOUNT_BALANCE)
                client.get(EP_CAMPAIGN_BUDGET, params={'id': 1})

                phash_balance = canonical_hash(None, body=None)
                phash_budget = canonical_hash({'id': 1}, body=None)
                assert cache.get(
                    'fp1', EP_ACCOUNT_BALANCE, phash_balance, max_age_seconds=3600,
                ) is not None
                assert cache.get(
                    'fp1', EP_CAMPAIGN_BUDGET, phash_budget, max_age_seconds=3600,
                ) is not None

                # Deposit invalidates both.
                client.post('/adv/v1/budget/deposit', json_body={'sum': 1000})
                assert cache.get(
                    'fp1', EP_ACCOUNT_BALANCE, phash_balance, max_age_seconds=3600,
                ) is None
                assert cache.get(
                    'fp1', EP_CAMPAIGN_BUDGET, phash_budget, max_age_seconds=3600,
                ) is None


class TestRateLimitDoubleCheck:
    """When EndpointBudget.reserve() raises, do one more cache lookup."""

    def test_reserve_raises_with_warm_cache_returns_cached(
            self, tmp_path: Path,
    ) -> None:
        cache = RequestCache(db_path=tmp_path / 'r.db')
        # Pre-populate the cache as if another process already published.
        phash = canonical_hash(None, body=None)
        cache.put(
            'fp1', EP_CAMPAIGN_INFO, phash,
            b'{"adverts":[{"id":42}]}',
            ttl_seconds=3600,
        )

        # Stub out the budget so reserve() raises immediately.
        class _BudgetThatBails:
            def reserve(self, *args, **kwargs):
                raise RateLimitError(
                    'Endpoint locked', retry_after=3500.0,
                )

            def observe(self, *args, **kwargs):
                pass

        # With the cache pre-populated AND budget bailing: the primary
        # lookup hits before reserve, so we never even reach the
        # double-check. This test confirms the primary lookup wins.
        with respx.mock:
            with _make_client(cache, budget=_BudgetThatBails()) as client:
                result = client.get(EP_CAMPAIGN_INFO)
                assert result == {'adverts': [{'id': 42}]}

    def test_reserve_raises_with_cold_cache_re_raises(
            self, tmp_path: Path,
    ) -> None:
        cache = RequestCache(db_path=tmp_path / 'r.db')

        class _BudgetThatBails:
            def reserve(self, *args, **kwargs):
                raise RateLimitError(
                    'Endpoint locked', retry_after=3500.0,
                )

            def observe(self, *args, **kwargs):
                pass

        with respx.mock:
            with _make_client(cache, budget=_BudgetThatBails()) as client:
                with pytest.raises(RateLimitError):
                    client.get(EP_CAMPAIGN_INFO)

    def test_reserve_raises_then_late_publish_returns_cached(
            self, tmp_path: Path,
    ) -> None:
        # Simulate the realistic race: primary lookup misses (cache cold),
        # then `reserve` raises, then between the raise and the
        # double-check another process populates the cache.
        cache = RequestCache(db_path=tmp_path / 'r.db')
        phash = canonical_hash(None, body=None)

        class _LatePublishingBudget:
            def __init__(self) -> None:
                self.calls = 0

            def reserve(self, *args, **kwargs):
                # Right before raising, simulate the publication.
                cache.put(
                    'fp1', EP_CAMPAIGN_INFO, phash,
                    b'{"adverts":[{"id":7}]}',
                    ttl_seconds=3600,
                )
                raise RateLimitError(
                    'Endpoint locked', retry_after=3500.0,
                )

            def observe(self, *args, **kwargs):
                pass

        with respx.mock:
            with _make_client(cache, budget=_LatePublishingBudget()) as client:
                result = client.get(EP_CAMPAIGN_INFO)
                assert result == {'adverts': [{'id': 7}]}


class TestPersonalTokenSubsecondTtl:
    """Personal tokens have sub-second TTLs — cache effectively bypassed."""

    def test_personal_ttl_too_short_to_hit(self, tmp_path: Path) -> None:
        # Personal /api/advert/v2/adverts is (5, 1.0) → 0.2 s.
        # We sleep 0.3 s between calls; second should miss.
        import time as _time
        cache = RequestCache(db_path=tmp_path / 'r.db')
        with respx.mock:
            route = respx.get(f'{BASE_URL}{EP_CAMPAIGN_INFO}').mock(
                return_value=httpx.Response(200, json={'adverts': []}),
            )
            with _make_client(cache, token_type='personal') as client:
                client.get(EP_CAMPAIGN_INFO)
                _time.sleep(0.3)
                client.get(EP_CAMPAIGN_INFO)
                assert route.call_count == 2
