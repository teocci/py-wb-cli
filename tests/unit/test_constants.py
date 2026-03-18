"""Tests for wb.core.constants module."""

import pytest

from wb.core.constants import (
    ANALYTICS_BASE_URL,
    PROMOTION_BASE_URL,
    ExitCode,
    TOKEN_CATEGORIES,
)


class TestExitCode:
    """Tests for the ExitCode enum."""

    @pytest.mark.parametrize(
        ('member', 'value'),
        [
            ('SUCCESS', 0),
            ('VALIDATION_ERROR', 2),
            ('AUTH_FAILURE', 3),
            ('AUTH_MISSING_SCOPE', 4),
            ('RATE_LIMITED', 5),
            ('API_ERROR', 6),
            ('CONFIG_ERROR', 7),
        ],
    )
    def test_exit_code_member_value(self, member: str, value: int) -> None:
        """Each ExitCode member maps to its expected integer value."""
        assert ExitCode[member] == value

    def test_exit_code_has_all_expected_members(self) -> None:
        """ExitCode contains exactly the expected set of members."""
        expected = {
            'SUCCESS',
            'VALIDATION_ERROR',
            'AUTH_FAILURE',
            'AUTH_MISSING_SCOPE',
            'RATE_LIMITED',
            'API_ERROR',
            'CONFIG_ERROR',
        }
        actual = {m.name for m in ExitCode}
        assert actual == expected

    def test_exit_code_is_int(self) -> None:
        """ExitCode values behave as integers."""
        assert ExitCode.SUCCESS == 0
        assert isinstance(ExitCode.SUCCESS, int)


class TestTokenCategories:
    """Tests for TOKEN_CATEGORIES constant."""

    def test_contains_promotion(self) -> None:
        assert 'promotion' in TOKEN_CATEGORIES

    def test_contains_analytics(self) -> None:
        assert 'analytics' in TOKEN_CATEGORIES


class TestUrlConstants:
    """Tests for API URL constants."""

    @pytest.mark.parametrize(
        'url',
        [PROMOTION_BASE_URL, ANALYTICS_BASE_URL],
    )
    def test_url_is_non_empty_string(self, url: str) -> None:
        assert isinstance(url, str)
        assert len(url) > 0

    @pytest.mark.parametrize(
        'url',
        [PROMOTION_BASE_URL, ANALYTICS_BASE_URL],
    )
    def test_url_starts_with_https(self, url: str) -> None:
        assert url.startswith('https://')
