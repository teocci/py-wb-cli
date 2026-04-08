"""Tests for wb.core.constants module."""

import pytest

from wb.core.constants import (
    ALL_CATEGORY,
    ANALYTICS_BASE_URL,
    CATEGORY_DISPLAY_NAMES,
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
    """Tests for TOKEN_CATEGORIES, ALL_CATEGORY, and CATEGORY_DISPLAY_NAMES."""

    _EXPECTED_SLUGS = [
        'promotion',
        'analytics',
        'statistics',
        'content',
        'marketplace',
        'buyers-returns',
        'documents',
        'finance',
        'supplies',
        'feedbacks-questions',
        'prices-discounts',
    ]

    def test_contains_all_expected_slugs(self) -> None:
        assert TOKEN_CATEGORIES == self._EXPECTED_SLUGS

    def test_has_eleven_categories(self) -> None:
        assert len(TOKEN_CATEGORIES) == 11

    @pytest.mark.parametrize('slug', _EXPECTED_SLUGS)
    def test_each_slug_present(self, slug: str) -> None:
        assert slug in TOKEN_CATEGORIES

    def test_all_category_sentinel(self) -> None:
        assert ALL_CATEGORY == 'all'
        assert ALL_CATEGORY not in TOKEN_CATEGORIES

    def test_display_names_covers_all_categories(self) -> None:
        assert set(TOKEN_CATEGORIES) == set(CATEGORY_DISPLAY_NAMES.keys())

    @pytest.mark.parametrize('slug', _EXPECTED_SLUGS)
    def test_display_name_is_non_empty(self, slug: str) -> None:
        assert isinstance(CATEGORY_DISPLAY_NAMES[slug], str)
        assert len(CATEGORY_DISPLAY_NAMES[slug]) > 0


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
