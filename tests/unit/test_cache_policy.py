"""Tests for the I-15 cache policy module."""

from __future__ import annotations

from wb.core import cache_policy
from wb.core.cache_policy import (
    CACHEABLE_ENDPOINTS,
    MUTATION_INVALIDATES,
    NEVER_CACHE,
    cache_ttl_seconds,
    canonical_hash,
    is_cacheable,
)
from wb.core.constants import (
    EP_ACCOUNT_BALANCE,
    EP_BID_SET,
    EP_CAMPAIGN_BUDGET,
    EP_CAMPAIGN_FULLSTATS,
    EP_CAMPAIGN_INFO,
    EP_CAMPAIGN_START,
    EP_FUNNEL_PRODUCTS,
    EP_NQ_GET_BIDS,
    EP_NQ_LIST,
    EP_NQ_SET_BIDS,
    EP_RECOMMENDED_BID,
)
from wb.core.rate_limits import ENDPOINT_LIMITS


class TestCoverage:
    """Every endpoint with a rate-limit prior must be categorised."""

    def test_every_known_endpoint_is_categorised(self) -> None:
        # Every endpoint in ENDPOINT_LIMITS is in exactly one of
        # CACHEABLE_ENDPOINTS or NEVER_CACHE.
        uncategorised = []
        for endpoint in ENDPOINT_LIMITS:
            in_cacheable = endpoint in CACHEABLE_ENDPOINTS
            in_never = endpoint in NEVER_CACHE
            if in_cacheable == in_never:  # both True or both False
                uncategorised.append(endpoint)
        assert not uncategorised, (
            f'Endpoints not categorised exactly once: {uncategorised}'
        )

    def test_cacheable_and_never_are_disjoint(self) -> None:
        overlap = CACHEABLE_ENDPOINTS & NEVER_CACHE
        assert overlap == frozenset(), f'Overlap: {overlap}'


class TestMutationMap:
    """Mutation-invalidation map must reference correctly categorised endpoints."""

    def test_mutation_keys_in_never_cache(self) -> None:
        for mutation in MUTATION_INVALIDATES:
            assert mutation in NEVER_CACHE, (
                f'{mutation} drives invalidation but is itself cacheable'
            )

    def test_invalidation_targets_in_cacheable(self) -> None:
        for mutation, targets in MUTATION_INVALIDATES.items():
            for target in targets:
                assert target in CACHEABLE_ENDPOINTS, (
                    f'{mutation} invalidates {target}, '
                    f'but {target} is not cacheable'
                )

    def test_campaign_start_invalidates_campaign_info(self) -> None:
        assert EP_CAMPAIGN_INFO in MUTATION_INVALIDATES[EP_CAMPAIGN_START]

    def test_bid_set_invalidates_recommended_bid(self) -> None:
        assert EP_RECOMMENDED_BID in MUTATION_INVALIDATES[EP_BID_SET]


class TestIsCacheable:
    def test_known_cacheable(self) -> None:
        assert is_cacheable(EP_CAMPAIGN_INFO) is True
        assert is_cacheable(EP_FUNNEL_PRODUCTS) is True

    def test_mutations_not_cacheable(self) -> None:
        assert is_cacheable(EP_CAMPAIGN_START) is False
        assert is_cacheable(EP_BID_SET) is False

    def test_unknown_endpoint_not_cacheable(self) -> None:
        assert is_cacheable('/unknown/path') is False


class TestCacheTtl:
    def test_base_token_returns_period_over_calls(self) -> None:
        # Base /api/advert/v2/adverts is (1, 3600) → 3600 s.
        ttl = cache_ttl_seconds(EP_CAMPAIGN_INFO, token_type='base')
        assert ttl == 3600.0

    def test_personal_token_returns_short_ttl(self) -> None:
        # Personal /api/advert/v2/adverts is (5, 1.0) → 0.2 s.
        ttl = cache_ttl_seconds(EP_CAMPAIGN_INFO, token_type='personal')
        assert ttl == 0.2

    def test_non_cacheable_endpoint_returns_zero(self) -> None:
        assert cache_ttl_seconds(EP_CAMPAIGN_START, token_type='base') == 0.0

    def test_unknown_endpoint_returns_zero(self) -> None:
        assert cache_ttl_seconds('/no/prior/here', token_type='base') == 0.0

    def test_base_funnel_is_thirty_minutes(self) -> None:
        # Base /api/analytics/v3/sales-funnel/products is (1, 1800) → 1800 s.
        ttl = cache_ttl_seconds(EP_FUNNEL_PRODUCTS, token_type='base')
        assert ttl == 1800.0

    def test_base_fullstats_is_one_hour(self) -> None:
        ttl = cache_ttl_seconds(EP_CAMPAIGN_FULLSTATS, token_type='base')
        assert ttl == 3600.0


class TestCanonicalHash:
    def test_dict_order_independence(self) -> None:
        a = canonical_hash({'a': 1, 'b': 2}, body=None)
        b = canonical_hash({'b': 2, 'a': 1}, body=None)
        assert a == b

    def test_primitive_list_order_independence(self) -> None:
        a = canonical_hash({'ids': [3, 1, 2]}, body=None)
        b = canonical_hash({'ids': [1, 2, 3]}, body=None)
        assert a == b

    def test_different_params_differ(self) -> None:
        a = canonical_hash({'x': 1}, body=None)
        b = canonical_hash({'x': 2}, body=None)
        assert a != b

    def test_get_and_post_same_params_differ(self) -> None:
        # GET (body=None) must not collide with POST (body={...}) even if
        # query params are identical.
        a = canonical_hash({'x': 1}, body=None)
        b = canonical_hash({'x': 1}, body={'extra': 1})
        assert a != b

    def test_none_params_and_empty_dict_collide(self) -> None:
        # An empty dict is semantically "no query params" — same as None.
        a = canonical_hash(None, body=None)
        b = canonical_hash({}, body=None)
        assert a == b

    def test_bytes_body_is_hashed_stably(self) -> None:
        a = canonical_hash(None, body=b'\x00\x01\x02')
        b = canonical_hash(None, body=b'\x00\x01\x02')
        assert a == b

    def test_returns_hex_digest(self) -> None:
        result = canonical_hash({'x': 1}, body=None)
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex
        int(result, 16)  # parses as hex


class TestPolicyExports:
    """Verify the public surface stays stable for callers."""

    def test_exports_cover_public_api(self) -> None:
        for name in ('CACHEABLE_ENDPOINTS', 'NEVER_CACHE', 'MUTATION_INVALIDATES',
                    'cache_ttl_seconds', 'canonical_hash', 'is_cacheable'):
            assert name in cache_policy.__all__
            assert hasattr(cache_policy, name)

    def test_specific_known_invalidations(self) -> None:
        # NQ set-bids should drop the get-bids and list caches.
        targets = MUTATION_INVALIDATES[EP_NQ_SET_BIDS]
        assert EP_NQ_GET_BIDS in targets
        assert EP_NQ_LIST in targets
        # Budget deposit drops budget + balance reads.
        targets = MUTATION_INVALIDATES['/adv/v1/budget/deposit']  # EP_BUDGET_DEPOSIT
        assert EP_CAMPAIGN_BUDGET in targets
        assert EP_ACCOUNT_BALANCE in targets
