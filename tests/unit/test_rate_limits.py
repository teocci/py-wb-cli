"""Tests for wb.core.rate_limits — BASE_OVERRIDES + select_prior."""

import pytest

from wb.core.constants import (
    EP_ACCOUNT_BALANCE,
    EP_CAMPAIGN_BUDGET,
    EP_CAMPAIGN_FULLSTATS,
    EP_CAMPAIGN_INFO,
    EP_CAMPAIGN_START,
    EP_FUNNEL_PRODUCTS,
)
from wb.core.rate_limits import (
    BASE_OVERRIDES,
    ENDPOINT_LIMITS,
    select_prior,
)


class TestSelectPrior:
    """select_prior returns the right (calls, period) per (path, token_type)."""

    @pytest.mark.parametrize('token_type', ['personal', 'service', 'test'])
    def test_non_base_returns_endpoint_limits(self, token_type):
        """Personal / Service / Test always read from ENDPOINT_LIMITS."""
        result = select_prior(EP_ACCOUNT_BALANCE, token_type)
        assert result == ENDPOINT_LIMITS[EP_ACCOUNT_BALANCE]
        assert result == (1, 1.0)

    def test_base_uses_override_when_present(self):
        """Base reads from BASE_OVERRIDES when the path is stratified."""
        result = select_prior(EP_ACCOUNT_BALANCE, 'base')
        assert result == BASE_OVERRIDES[EP_ACCOUNT_BALANCE]
        assert result == (1, 1800.0)

    def test_base_falls_through_to_endpoint_limits_for_uniform(self):
        """Base falls through to ENDPOINT_LIMITS when no override exists."""
        # EP_CAMPAIGN_BUDGET is uniform across token types in swagger
        assert EP_CAMPAIGN_BUDGET not in BASE_OVERRIDES
        result = select_prior(EP_CAMPAIGN_BUDGET, 'base')
        assert result == ENDPOINT_LIMITS[EP_CAMPAIGN_BUDGET]

    def test_base_falls_through_for_uniform_campaign_start(self):
        """EP_CAMPAIGN_START has no per-type table — base uses ENDPOINT_LIMITS."""
        assert EP_CAMPAIGN_START not in BASE_OVERRIDES
        assert select_prior(EP_CAMPAIGN_START, 'base') == ENDPOINT_LIMITS[EP_CAMPAIGN_START]

    def test_unknown_path_returns_none(self):
        """Paths not in either map return None — no preemptive throttling."""
        assert select_prior('/some/random/path', 'base') is None
        assert select_prior('/some/random/path', 'personal') is None

    def test_unknown_token_type_treated_as_default(self):
        """Unknown token_type values fall through (no override) — use ENDPOINT_LIMITS."""
        # 'gibberish' isn't in TOKEN_TYPES; the implementation only special-cases 'base'
        result = select_prior(EP_ACCOUNT_BALANCE, 'gibberish')
        assert result == ENDPOINT_LIMITS[EP_ACCOUNT_BALANCE]

    def test_default_token_type_is_base(self):
        """select_prior() with no token_type defaults to base."""
        assert select_prior(EP_ACCOUNT_BALANCE) == BASE_OVERRIDES[EP_ACCOUNT_BALANCE]


class TestBaseOverridesShape:
    """BASE_OVERRIDES values match the documented Base limits."""

    @pytest.mark.parametrize(
        'endpoint, expected',
        [
            (EP_CAMPAIGN_FULLSTATS, (1, 3600.0)),   # 1/h
            (EP_CAMPAIGN_INFO, (1, 3600.0)),        # 1/h
            (EP_ACCOUNT_BALANCE, (1, 1800.0)),      # 2/h, 30 min interval, burst 1
            (EP_FUNNEL_PRODUCTS, (1, 1800.0)),      # 2/h, 30 min interval, burst 1
        ],
    )
    def test_known_base_overrides(self, endpoint, expected):
        """Spot-check Base overrides match swagger-documented limits."""
        assert BASE_OVERRIDES[endpoint] == expected

    def test_base_overrides_are_strictly_tighter_than_personal(self):
        """For every overridden endpoint, the Base interval >= Personal interval."""
        for endpoint, base_prior in BASE_OVERRIDES.items():
            standard = ENDPOINT_LIMITS.get(endpoint)
            if standard is None:
                continue
            base_interval = base_prior[1] / base_prior[0]
            standard_interval = standard[1] / standard[0]
            assert base_interval >= standard_interval, (
                f'Base prior for {endpoint} should be >= standard interval '
                f'({base_interval}s vs {standard_interval}s)'
            )

    def test_uniform_endpoints_excluded(self):
        """Endpoints documented as uniform across token types must not appear."""
        # These have only a single Period|Limit|Interval|Burst row in swagger
        uniform_endpoints = [EP_CAMPAIGN_BUDGET, EP_CAMPAIGN_START]
        for ep in uniform_endpoints:
            assert ep not in BASE_OVERRIDES, (
                f'{ep} is uniform in swagger and must not have a BASE_OVERRIDES entry'
            )
