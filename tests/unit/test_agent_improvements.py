"""Tests for v0.9.0 agent improvement features.

Covers:
- Structured JSON error output (error_code, to_dict)
- Campaign.nm_ids from API response
- CampaignStats with per-NM breakdown (NmStats, DayStats)
- Shared CLI helpers
"""

import json

import pytest

from wb.core.constants import ExitCode
from wb.core.exceptions import (
    ApiError,
    AuthenticationError,
    ConfigError,
    RateLimitError,
    ValidationError,
    WbCliError,
)
from wb.domain.models import (
    Campaign,
    CampaignStats,
    DayStats,
    NmStats,
)


# ── Error codes and to_dict ─────────────────────────────────────────


class TestErrorCodes:
    """Each exception subclass has a machine-readable error_code."""

    def test_base_error_code(self):
        err = WbCliError('generic')
        assert err.error_code == 'CLI_ERROR'

    def test_validation_error_code(self):
        err = ValidationError('bad input')
        assert err.error_code == 'VALIDATION_ERROR'

    def test_auth_error_code(self):
        err = AuthenticationError('expired')
        assert err.error_code == 'AUTH_FAILURE'

    def test_rate_limit_error_code(self):
        err = RateLimitError('slow down')
        assert err.error_code == 'RATE_LIMITED'

    def test_api_error_code(self):
        err = ApiError('server fail')
        assert err.error_code == 'API_ERROR'

    def test_config_error_code(self):
        err = ConfigError('missing file')
        assert err.error_code == 'CONFIG_ERROR'


class TestToDict:
    """to_dict() returns structured JSON-serializable error dicts."""

    def test_base_to_dict(self):
        err = WbCliError('generic error')
        d = err.to_dict()
        assert d['status'] == 'error'
        assert d['error']['code'] == 'CLI_ERROR'
        assert d['error']['message'] == 'generic error'
        assert d['error']['exit_code'] == int(ExitCode.API_ERROR)

    def test_validation_to_dict(self):
        err = ValidationError('field required')
        d = err.to_dict()
        assert d['error']['code'] == 'VALIDATION_ERROR'
        assert d['error']['exit_code'] == int(ExitCode.VALIDATION_ERROR)

    def test_rate_limit_to_dict_with_retry(self):
        err = RateLimitError('slow down', retry_after=30.0)
        d = err.to_dict()
        assert d['error']['code'] == 'RATE_LIMITED'
        assert d['error']['retry_after'] == 30.0

    def test_rate_limit_to_dict_without_retry(self):
        err = RateLimitError('slow down')
        d = err.to_dict()
        assert 'retry_after' not in d['error']

    def test_api_error_to_dict_with_status(self):
        err = ApiError('not found', status_code=404)
        d = err.to_dict()
        assert d['error']['code'] == 'API_ERROR'
        assert d['error']['status_code'] == 404

    def test_api_error_to_dict_without_status(self):
        err = ApiError('unknown')
        d = err.to_dict()
        assert 'status_code' not in d['error']

    def test_to_dict_is_json_serializable(self):
        err = ApiError('fail', status_code=500)
        serialized = json.dumps(err.to_dict())
        assert '"API_ERROR"' in serialized


# ── Campaign.nm_ids ──────────────────────────────────────────────────


class TestCampaignNmIds:
    """Campaign.from_api() extracts nm_ids from nm_settings."""

    def test_nm_ids_from_nm_settings(self):
        data = {
            'id': 123,
            'status': 11,
            'type': 9,
            'settings': {'name': 'Test', 'payment_type': 'cpm'},
            'timestamps': {},
            'nm_settings': [
                {'nm_id': 100525085},
                {'nm_id': 227403075},
            ],
        }
        campaign = Campaign.from_api(data)
        assert campaign.nm_ids == [100525085, 227403075]

    def test_nm_ids_empty_when_missing(self):
        data = {
            'id': 456,
            'status': 9,
            'type': 9,
            'settings': {'name': 'No Products'},
            'timestamps': {},
        }
        campaign = Campaign.from_api(data)
        assert campaign.nm_ids == []

    def test_nm_ids_empty_list(self):
        data = {
            'id': 789,
            'status': 7,
            'type': 9,
            'settings': {},
            'timestamps': {},
            'nm_settings': [],
        }
        campaign = Campaign.from_api(data)
        assert campaign.nm_ids == []

    def test_nm_ids_skips_entries_without_nm_id(self):
        data = {
            'id': 101,
            'status': 11,
            'type': 9,
            'settings': {},
            'timestamps': {},
            'nm_settings': [
                {'nm_id': 555},
                {'other_field': 'no nm_id'},
                {'nm_id': 666},
            ],
        }
        campaign = Campaign.from_api(data)
        assert campaign.nm_ids == [555, 666]


# ── NmStats ──────────────────────────────────────────────────────────


class TestNmStats:
    """NmStats.from_api() correctly parses per-NM stats."""

    def test_from_api(self):
        data = {
            'nmId': 100525085,
            'name': 'Selection Pink',
            'views': 19,
            'clicks': 2,
            'ctr': 10.5,
            'orders': 3,
            'sum': 6.02,
            'cpc': 3.01,
            'cr': 15.0,
            'atbs': 4,
            'shks': 2,
        }
        nm = NmStats.from_api(data)
        assert nm.nm_id == 100525085
        assert nm.name == 'Selection Pink'
        assert nm.views == 19
        assert nm.clicks == 2
        assert nm.orders == 3
        assert nm.spend == 6.02

    def test_from_api_minimal(self):
        data = {'nmId': 1}
        nm = NmStats.from_api(data)
        assert nm.nm_id == 1
        assert nm.name == ''
        assert nm.views == 0
        assert nm.spend == 0.0


# ── DayStats ─────────────────────────────────────────────────────────


class TestDayStats:
    """DayStats.from_api() aggregates across app types."""

    def test_aggregates_same_nm_across_app_types(self):
        data = {
            'date': '2026-04-01T00:00:00Z',
            'views': 10,
            'clicks': 2,
            'orders': 1,
            'sum': 5.0,
            'apps': [
                {
                    'appType': 32,
                    'nms': [
                        {'nmId': 100, 'name': 'P1', 'views': 3, 'clicks': 1,
                         'orders': 0, 'sum': 2.0, 'atbs': 0, 'shks': 0,
                         'ctr': 0, 'cpc': 0, 'cr': 0},
                    ],
                },
                {
                    'appType': 64,
                    'nms': [
                        {'nmId': 100, 'name': 'P1', 'views': 7, 'clicks': 1,
                         'orders': 1, 'sum': 3.0, 'atbs': 1, 'shks': 1,
                         'ctr': 0, 'cpc': 0, 'cr': 0},
                    ],
                },
            ],
        }
        day = DayStats.from_api(data)
        assert day.date == '2026-04-01T00:00:00Z'
        assert len(day.nm_stats) == 1
        nm = day.nm_stats[0]
        assert nm.nm_id == 100
        assert nm.views == 10
        assert nm.clicks == 2
        assert nm.orders == 1
        assert nm.spend == 5.0

    def test_multiple_nms(self):
        data = {
            'date': '2026-04-02T00:00:00Z',
            'views': 20,
            'clicks': 5,
            'orders': 2,
            'sum': 10.0,
            'apps': [
                {
                    'appType': 64,
                    'nms': [
                        {'nmId': 100, 'name': 'P1', 'views': 12, 'clicks': 3,
                         'orders': 1, 'sum': 6.0, 'atbs': 1, 'shks': 1,
                         'ctr': 0, 'cpc': 0, 'cr': 0},
                        {'nmId': 200, 'name': 'P2', 'views': 8, 'clicks': 2,
                         'orders': 1, 'sum': 4.0, 'atbs': 0, 'shks': 1,
                         'ctr': 0, 'cpc': 0, 'cr': 0},
                    ],
                },
            ],
        }
        day = DayStats.from_api(data)
        assert len(day.nm_stats) == 2
        nm_map = {nm.nm_id: nm for nm in day.nm_stats}
        assert nm_map[100].views == 12
        assert nm_map[200].views == 8

    def test_empty_apps(self):
        data = {
            'date': '2026-04-03T00:00:00Z',
            'views': 0,
            'clicks': 0,
            'orders': 0,
            'sum': 0,
        }
        day = DayStats.from_api(data)
        assert day.nm_stats == []


# ── CampaignStats with per-NM breakdown ─────────────────────────────


class TestCampaignStatsPerNm:
    """CampaignStats.from_api() preserves per-NM breakdown."""

    def test_aggregates_nm_across_days(self):
        data = {
            'advertId': 33819998,
            'views': 30,
            'clicks': 4,
            'ctr': 13.3,
            'orders': 2,
            'sum': 8.0,
            'cpc': 2.0,
            'cr': 6.7,
            'atbs': 2,
            'shks': 2,
            'currency': 'RUB',
            'days': [
                {
                    'date': '2026-04-01T00:00:00Z',
                    'views': 10,
                    'clicks': 1,
                    'orders': 0,
                    'sum': 3.0,
                    'apps': [
                        {
                            'appType': 64,
                            'nms': [
                                {'nmId': 100, 'name': 'P1', 'views': 10,
                                 'clicks': 1, 'orders': 0, 'sum': 3.0,
                                 'atbs': 0, 'shks': 0, 'ctr': 0,
                                 'cpc': 0, 'cr': 0},
                            ],
                        },
                    ],
                },
                {
                    'date': '2026-04-02T00:00:00Z',
                    'views': 20,
                    'clicks': 3,
                    'orders': 2,
                    'sum': 5.0,
                    'apps': [
                        {
                            'appType': 64,
                            'nms': [
                                {'nmId': 100, 'name': 'P1', 'views': 20,
                                 'clicks': 3, 'orders': 2, 'sum': 5.0,
                                 'atbs': 2, 'shks': 2, 'ctr': 0,
                                 'cpc': 0, 'cr': 0},
                            ],
                        },
                    ],
                },
            ],
        }
        stats = CampaignStats.from_api(data)

        # Top-level aggregates preserved
        assert stats.campaign_id == 33819998
        assert stats.views == 30
        assert stats.spend == 8.0

        # Days preserved
        assert len(stats.days) == 2

        # Aggregated per-NM stats
        assert len(stats.nm_stats) == 1
        nm = stats.nm_stats[0]
        assert nm.nm_id == 100
        assert nm.views == 30
        assert nm.clicks == 4
        assert nm.orders == 2
        assert nm.spend == 8.0

    def test_no_days(self):
        data = {
            'advertId': 999,
            'views': 0,
            'clicks': 0,
            'ctr': 0,
            'orders': 0,
            'sum': 0,
            'cpc': 0,
            'cr': 0,
            'atbs': 0,
            'shks': 0,
            'currency': 'RUB',
        }
        stats = CampaignStats.from_api(data)
        assert stats.days == []
        assert stats.nm_stats == []

    def test_multiple_nms_across_days(self):
        data = {
            'advertId': 1000,
            'views': 15,
            'clicks': 3,
            'ctr': 20.0,
            'orders': 2,
            'sum': 10.0,
            'cpc': 3.3,
            'cr': 13.3,
            'atbs': 1,
            'shks': 2,
            'currency': 'RUB',
            'days': [
                {
                    'date': '2026-04-01T00:00:00Z',
                    'views': 8,
                    'clicks': 2,
                    'orders': 1,
                    'sum': 6.0,
                    'apps': [
                        {
                            'appType': 64,
                            'nms': [
                                {'nmId': 100, 'name': 'P1', 'views': 5,
                                 'clicks': 1, 'orders': 1, 'sum': 4.0,
                                 'atbs': 1, 'shks': 1, 'ctr': 0,
                                 'cpc': 0, 'cr': 0},
                                {'nmId': 200, 'name': 'P2', 'views': 3,
                                 'clicks': 1, 'orders': 0, 'sum': 2.0,
                                 'atbs': 0, 'shks': 0, 'ctr': 0,
                                 'cpc': 0, 'cr': 0},
                            ],
                        },
                    ],
                },
                {
                    'date': '2026-04-02T00:00:00Z',
                    'views': 7,
                    'clicks': 1,
                    'orders': 1,
                    'sum': 4.0,
                    'apps': [
                        {
                            'appType': 32,
                            'nms': [
                                {'nmId': 200, 'name': 'P2', 'views': 7,
                                 'clicks': 1, 'orders': 1, 'sum': 4.0,
                                 'atbs': 0, 'shks': 1, 'ctr': 0,
                                 'cpc': 0, 'cr': 0},
                            ],
                        },
                    ],
                },
            ],
        }
        stats = CampaignStats.from_api(data)
        assert len(stats.nm_stats) == 2
        nm_map = {nm.nm_id: nm for nm in stats.nm_stats}
        assert nm_map[100].views == 5
        assert nm_map[100].spend == 4.0
        assert nm_map[200].views == 10
        assert nm_map[200].spend == 6.0
        assert nm_map[200].orders == 1


# ── Shared CLI helpers ───────────────────────────────────────────────


class TestSharedHelpers:
    """Test shared helper functions from _helpers.py."""

    def test_get_renderer_json_mode(self):
        from wb.cli._helpers import get_renderer
        from wb.domain.enums import OutputFormat

        class FakeCtx:
            obj = {'json_output': True, 'quiet': False, 'verbose': False}

        renderer = get_renderer(FakeCtx())
        assert renderer.output_format == OutputFormat.JSON

    def test_get_renderer_table_mode(self):
        from wb.cli._helpers import get_renderer
        from wb.domain.enums import OutputFormat

        class FakeCtx:
            obj = {'json_output': False, 'quiet': False, 'verbose': False}

        renderer = get_renderer(FakeCtx())
        assert renderer.output_format == OutputFormat.TABLE

    def test_get_profile(self):
        from wb.cli._helpers import get_profile

        class FakeCtx:
            obj = {'profile': 'myprofile'}

        assert get_profile(FakeCtx()) == 'myprofile'

    def test_get_profile_none(self):
        from wb.cli._helpers import get_profile

        class FakeCtx:
            obj = {}

        assert get_profile(FakeCtx()) is None

    def test_confirm_or_abort_skips_when_yes(self):
        from wb.cli._helpers import confirm_or_abort, get_renderer
        from wb.domain.enums import OutputFormat, VerbosityLevel
        from wb.core.output import OutputRenderer

        renderer = OutputRenderer(OutputFormat.TABLE, VerbosityLevel.NORMAL)
        # Should not raise when yes=True
        confirm_or_abort(renderer, 'test action', yes=True)

    def test_confirm_or_abort_skips_in_json_mode(self):
        from wb.cli._helpers import confirm_or_abort
        from wb.domain.enums import OutputFormat, VerbosityLevel
        from wb.core.output import OutputRenderer

        renderer = OutputRenderer(OutputFormat.JSON, VerbosityLevel.NORMAL)
        # Should not raise in JSON mode even when yes=False
        confirm_or_abort(renderer, 'test action', yes=False)
