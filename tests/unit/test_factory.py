"""Phase A-2 regression: runtime credential chain is profile-only.

Before A-2 the service factories fell back to ``WB_API_TOKEN`` /
``WB_ANALYTICS_TOKEN`` / ``WB_AUTHORIZEV3`` / ``WB_PORTAL_COOKIE`` when no
profile was registered (or even when one was — env vars took priority).
That dual-source model was the root cause of the F-19/F-20 fingerprint
drift: a stale ``.env`` would silently override a registered profile.

A-2 made the chain ``CLI flag → active profile → ConfigError``. The
tests below pin that contract:

- No profile + env-only → ConfigError.
- Profile + stale env → profile wins (fingerprint matches profile token).
- CLI flag still overrides everything.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from wb.auth.profiles import ProfileStore
from wb.core.exceptions import ConfigError
from wb.services._factory import (
    ServiceContainer,
    _get_analytics_token,
    _get_promotion_token,
    create_portal_client,
)


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Redirect ~/.wb-cli to a temp dir; reset cached container state."""
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    for var in (
        'WB_API_TOKEN', 'WB_ANALYTICS_TOKEN',
        'WB_AUTHORIZEV3', 'WB_PORTAL_COOKIE',
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    ServiceContainer.reset()
    yield tmp_path
    ServiceContainer.reset()


# ── No profile + env token → ConfigError ──────────────────────────────


class TestPromotionTokenNoFallback:
    """``_get_promotion_token`` no longer reads env at runtime."""

    def test_raises_configerror_with_env_only(self, isolated_home, monkeypatch):
        """Env token alone must NOT satisfy the chain — profile is required."""
        monkeypatch.setenv('WB_API_TOKEN', 'env-token-12345')
        with pytest.raises(ConfigError) as exc:
            _get_promotion_token()
        assert 'wb auth login' in str(exc.value)

    def test_raises_configerror_with_nothing(self, isolated_home):
        """No CLI flag, no env, no profile → ConfigError."""
        with pytest.raises(ConfigError):
            _get_promotion_token()

    def test_cli_flag_always_wins(self, isolated_home, monkeypatch):
        """``cli_token`` short-circuits the chain regardless of env / profile."""
        monkeypatch.setenv('WB_API_TOKEN', 'env-token')
        assert _get_promotion_token(cli_token='flag-token') == 'flag-token'

    def test_profile_wins_over_stale_env(self, isolated_home, monkeypatch):
        """F-19/F-20 regression: profile token beats env, even when env is set."""
        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('p')
        store.save_token('p', 'promotion', 'profile-token')
        store.set_active('p')

        monkeypatch.setenv('WB_API_TOKEN', 'STALE-env-token')
        assert _get_promotion_token() == 'profile-token'


class TestAnalyticsTokenNoFallback:
    """``_get_analytics_token`` no longer falls through env (both branches)."""

    def test_raises_configerror_with_analytics_env_only(
            self, isolated_home, monkeypatch,
    ):
        """``WB_ANALYTICS_TOKEN`` alone must NOT satisfy the chain."""
        monkeypatch.setenv('WB_ANALYTICS_TOKEN', 'env-analytics')
        with pytest.raises(ConfigError):
            _get_analytics_token()

    def test_raises_configerror_with_api_env_only(self, isolated_home, monkeypatch):
        """``WB_API_TOKEN`` alone must NOT satisfy the analytics chain."""
        monkeypatch.setenv('WB_API_TOKEN', 'env-api')
        with pytest.raises(ConfigError):
            _get_analytics_token()

    def test_cli_flag_overrides_everything(self, isolated_home, monkeypatch):
        monkeypatch.setenv('WB_API_TOKEN', 'env-api')
        monkeypatch.setenv('WB_ANALYTICS_TOKEN', 'env-analytics')
        assert _get_analytics_token(cli_token='flag-token') == 'flag-token'

    def test_profile_beats_stale_env(self, isolated_home, monkeypatch):
        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('p')
        store.save_token('p', 'analytics', 'profile-analytics')
        store.set_active('p')

        monkeypatch.setenv('WB_ANALYTICS_TOKEN', 'STALE-env')
        monkeypatch.setenv('WB_API_TOKEN', 'STALE-api')
        assert _get_analytics_token() == 'profile-analytics'


class TestPortalClientNoFallback:
    """``create_portal_client`` no longer reads portal env at runtime."""

    def test_raises_configerror_with_env_only(self, isolated_home, monkeypatch):
        """Env-only portal credentials must NOT satisfy the chain."""
        monkeypatch.setenv('WB_AUTHORIZEV3', 'env-auth')
        monkeypatch.setenv('WB_PORTAL_COOKIE', 'env-cookie')
        with pytest.raises(ConfigError) as exc:
            create_portal_client()
        assert 'wb auth login' in str(exc.value)

    def test_raises_configerror_with_nothing(self, isolated_home):
        with pytest.raises(ConfigError):
            create_portal_client()

    def test_cli_flags_always_win(self, isolated_home, monkeypatch):
        """Direct ``cli_authorizev3`` + ``cli_cookie`` skip the profile lookup."""
        monkeypatch.setenv('WB_AUTHORIZEV3', 'env-auth')
        client = create_portal_client(
            cli_authorizev3='flag-auth',
            cli_cookie='flag-cookie',
        )
        # The client carries the flag values, not the env values.
        assert client._authorizev3 == 'flag-auth'

    def test_profile_session_beats_stale_env(self, isolated_home, monkeypatch):
        """Registered portal session wins over stale ``WB_AUTHORIZEV3``."""
        store = ProfileStore(isolated_home / '.wb-cli')
        store.save_portal_session(
            profile_name='p',
            authorizev3='profile-auth',
            cookie='profile-cookie',
        )
        store.set_active('p')

        monkeypatch.setenv('WB_AUTHORIZEV3', 'STALE-env-auth')
        monkeypatch.setenv('WB_PORTAL_COOKIE', 'STALE-env-cookie')

        client = create_portal_client()
        assert client._authorizev3 == 'profile-auth'
