"""Tests for `wb auth` CLI commands — focus on R-5 token_type wiring."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from wb.auth.profiles import ProfileStore
from wb.cli.app import app

runner = CliRunner()

# Stub out validate_promotion_token so login doesn't try to hit WB.
PATCH_VALIDATE = 'wb.cli.auth.validate_promotion_token'


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Redirect ~/.wb-cli to a temp dir; clear any inherited env tokens."""
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    for var in (
        'WB_API_TOKEN', 'WB_ANALYTICS_TOKEN',
        'WB_AUTHORIZEV3', 'WB_PORTAL_COOKIE',
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    yield tmp_path


# ── auth login --token-type ───────────────────────────────────────────


class TestAuthLoginTokenType:
    """The --token-type flag persists the field via ProfileStore.set_token_type."""

    def test_default_token_type_is_base_for_new_profile(self, isolated_home):
        """Login without --token-type leaves the default ('base') in place."""
        with patch(PATCH_VALIDATE, return_value=True):
            result = runner.invoke(
                app,
                ['auth', 'login', '--token', 'tok', '--profile', 'p'],
            )

        assert result.exit_code == 0
        store = ProfileStore(isolated_home / '.wb-cli')
        assert store.get_profile('p').token_type == 'base'
        # The success line surfaces the resolved type
        assert 'type=base' in result.output

    @pytest.mark.parametrize('ttype', ['personal', 'service', 'base', 'test'])
    def test_explicit_token_type_persists(self, isolated_home, ttype):
        """--token-type writes to the profile and survives a reload."""
        with patch(PATCH_VALIDATE, return_value=True):
            result = runner.invoke(
                app,
                [
                    'auth', 'login', '--token', 'tok',
                    '--profile', 'p', '--token-type', ttype,
                ],
            )

        assert result.exit_code == 0, result.output
        # Reload to confirm persistence
        store = ProfileStore(isolated_home / '.wb-cli')
        assert store.get_profile('p').token_type == ttype
        assert f'type={ttype}' in result.output

    def test_invalid_token_type_rejected(self, isolated_home):
        """Unknown --token-type values exit with VALIDATION_ERROR (2)."""
        with patch(PATCH_VALIDATE, return_value=True):
            result = runner.invoke(
                app,
                [
                    'auth', 'login', '--token', 'tok',
                    '--profile', 'p', '--token-type', 'bogus',
                ],
            )

        assert result.exit_code == 2
        assert 'Invalid --token-type' in result.output

    def test_existing_token_type_kept_when_flag_omitted(self, isolated_home):
        """Re-login without --token-type doesn't reset a previously-set type."""
        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('p')
        store.set_token_type('p', 'personal')

        with patch(PATCH_VALIDATE, return_value=True):
            result = runner.invoke(
                app,
                ['auth', 'login', '--token', 'new-tok', '--profile', 'p'],
            )

        assert result.exit_code == 0
        store2 = ProfileStore(isolated_home / '.wb-cli')
        assert store2.get_profile('p').token_type == 'personal'


# ── auth list / status include token_type ─────────────────────────────


class TestAuthListShowsTokenType:
    """`wb auth list` JSON payload carries `token_type` per profile."""

    def test_list_json_includes_token_type(self, isolated_home):
        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('p')
        store.save_token('p', 'promotion', 'tok')
        store.set_token_type('p', 'service')

        result = runner.invoke(app, ['--json', 'auth', 'list'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert any(
            entry['name'] == 'p' and entry['token_type'] == 'service'
            for entry in data
        )

    def test_status_json_includes_token_type(self, isolated_home):
        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('default')
        store.save_token('default', 'promotion', 'tok')
        store.set_token_type('default', 'base')

        result = runner.invoke(app, ['--json', 'auth', 'status'])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload['token_type'] == 'base'


# ── auth login — JWT-driven auto-naming (A-1) ──────────────────────────


class TestAuthLoginAutoNaming:
    """`wb auth login` decodes the JWT, auto-names the profile, slug-validates --profile."""

    def test_login_without_profile_uses_oid_and_type(self, isolated_home):
        """Auto-named profile is '{oid}_{token_type}' with seller_id + exp populated."""
        from tests.unit.test_token_utils import TOKEN_PROD_BASE

        with patch(PATCH_VALIDATE, return_value=True):
            result = runner.invoke(
                app, ['auth', 'login', '--token', TOKEN_PROD_BASE, '--category', 'all'],
            )

        assert result.exit_code == 0, result.output
        store = ProfileStore(isolated_home / '.wb-cli')
        profile = store.get_profile('668554_base')
        assert profile.seller_id == '668554'
        assert profile.token_expires_at == 1790136818
        assert profile.token_type == 'base'

    def test_login_collision_requires_explicit_profile(self, isolated_home):
        """Auto-name collision exits with VALIDATION_ERROR and instructs --profile."""
        from tests.unit.test_token_utils import TOKEN_PROD_BASE

        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('668554_base')

        with patch(PATCH_VALIDATE, return_value=True):
            result = runner.invoke(app, ['auth', 'login', '--token', TOKEN_PROD_BASE])

        assert result.exit_code == 2
        assert 'already exists' in result.output
        assert '--profile' in result.output

    def test_login_explicit_profile_overrides_auto_name(self, isolated_home):
        """User-supplied --profile is used as-is (and slug-validated)."""
        from tests.unit.test_token_utils import TOKEN_PROD_BASE

        with patch(PATCH_VALIDATE, return_value=True):
            result = runner.invoke(
                app, ['auth', 'login', '--token', TOKEN_PROD_BASE,
                      '--profile', 'my_seller', '--category', 'all'],
            )

        assert result.exit_code == 0, result.output
        store = ProfileStore(isolated_home / '.wb-cli')
        # The explicit name was used, not the auto-generated one.
        assert store.get_profile('my_seller').seller_id == '668554'

    @pytest.mark.parametrize(
        'bad_name',
        ['My Profile', 'has-dash', 'UPPER', 'with/slash', 'with.dot', 'a b', ''],
        ids=['space', 'dash', 'upper', 'slash', 'dot', 'middle-space', 'empty'],
    )
    def test_login_invalid_profile_slug_rejected(self, isolated_home, bad_name):
        with patch(PATCH_VALIDATE, return_value=True):
            result = runner.invoke(
                app, ['auth', 'login', '--token', 'tok', '--profile', bad_name],
            )
        assert result.exit_code == 2
        assert 'Invalid profile name' in result.output

    def test_login_test_token_auto_sets_token_type(self, isolated_home):
        """JWT with `t: true` auto-sets token_type='test' (and the profile name suffix)."""
        from tests.unit.test_token_utils import TOKEN_TEST

        with patch(PATCH_VALIDATE, return_value=True):
            result = runner.invoke(app, ['auth', 'login', '--token', TOKEN_TEST])

        assert result.exit_code == 0, result.output
        store = ProfileStore(isolated_home / '.wb-cli')
        profile = store.get_profile('999_test')
        assert profile.token_type == 'test'

    def test_login_undecodable_token_falls_back_to_default(self, isolated_home):
        """Token that isn't a JWT → no claims → uses active/default profile name."""
        with patch(PATCH_VALIDATE, return_value=True):
            result = runner.invoke(
                app, ['auth', 'login', '--token', 'not-a-jwt', '--category', 'all'],
            )

        assert result.exit_code == 0, result.output
        store = ProfileStore(isolated_home / '.wb-cli')
        # No oid → fell back to active profile name (which is 'default' on a fresh install)
        profile = store.get_profile('default')
        assert profile.seller_id is None
        assert profile.token_expires_at is None

    def test_status_json_includes_seller_id_and_expires(self, isolated_home):
        """`wb auth status --json` surfaces seller_id and token_expires_at."""
        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('default')
        store.save_token('default', 'promotion', 'tok')
        store.set_seller_id('default', '7777')
        store.set_token_expires_at('default', 1790136818)

        result = runner.invoke(app, ['--json', 'auth', 'status'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['seller_id'] == '7777'
        assert data['token_expires_at'] == 1790136818

    def test_list_json_includes_seller_id(self, isolated_home):
        """`wb auth list --json` surfaces seller_id and token_expires_at per entry."""
        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('p')
        store.save_token('p', 'promotion', 'tok')
        store.set_seller_id('p', '8888')

        result = runner.invoke(app, ['--json', 'auth', 'list'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert any(e['name'] == 'p' and e['seller_id'] == '8888' for e in data)


# ── auth list surfaces portal identity ────────────────────────────────


class TestAuthListShowsPortalIdentity:
    """`wb auth list` exposes `portal_user_id` and dashes Type for portal-only profiles."""

    def test_json_includes_portal_user_id_when_set(self, isolated_home):
        """JSON entry carries `portal_user_id` when the profile has a portal session."""
        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('p')
        store.save_token('p', 'promotion', 'tok')
        store.save_portal_session(
            'p', authorizev3='av3-token', user_id='10799201',
        )

        result = runner.invoke(app, ['--json', 'auth', 'list'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert any(
            e['name'] == 'p' and e['portal_user_id'] == '10799201'
            for e in data
        )

    def test_json_portal_user_id_is_null_when_no_portal_session(self, isolated_home):
        """JSON entry always carries the `portal_user_id` key; `null` when not configured."""
        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('p')
        store.save_token('p', 'promotion', 'tok')

        result = runner.invoke(app, ['--json', 'auth', 'list'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        entry = next(e for e in data if e['name'] == 'p')
        assert 'portal_user_id' in entry
        assert entry['portal_user_id'] is None

    def test_table_dashes_type_for_portal_only_profile(self, isolated_home):
        """A profile with portal session and zero JWT tokens shows '—' in Type."""
        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('portal_only')
        store.save_portal_session(
            'portal_only', authorizev3='av3-token', user_id='10799201',
        )

        result = runner.invoke(app, ['auth', 'list'])
        assert result.exit_code == 0
        # Portal user id is visible in the row.
        assert '10799201' in result.output
        # Type cell is a dash, not the default 'base'.
        assert '—' in result.output
        # The row carries no JWT type label — Categories says 'none'.
        assert 'none' in result.output


# ── auth login env-bootstrap (A-2) ────────────────────────────────────


class TestAuthLoginEnvBootstrap:
    """`wb auth login` without --token reads WB_API_TOKEN from env / .env.

    This is the rare single-seller fallback. Multi-profile users should
    keep passing --token explicitly.
    """

    def test_no_flag_no_env_exits_with_config_error(self, isolated_home):
        """No --token and no env → exit code 7 (CONFIG_ERROR)."""
        with patch(PATCH_VALIDATE, return_value=True):
            result = runner.invoke(app, ['auth', 'login'])

        assert result.exit_code == 7
        assert 'WB_API_TOKEN' in result.output

    def test_env_bootstrap_creates_profile(self, isolated_home, monkeypatch):
        """WB_API_TOKEN in env materializes a profile when --token omitted."""
        from tests.unit.test_token_utils import TOKEN_PROD_BASE

        monkeypatch.setenv('WB_API_TOKEN', TOKEN_PROD_BASE)
        with patch(PATCH_VALIDATE, return_value=True):
            result = runner.invoke(app, ['auth', 'login'])

        assert result.exit_code == 0, result.output
        store = ProfileStore(isolated_home / '.wb-cli')
        profile = store.get_profile('668554_base')
        # No --category passed → bootstrap defaults to 'all'.
        assert set(profile.tokens.keys()) >= {'promotion', 'analytics'}
        assert profile.tokens['promotion'] == TOKEN_PROD_BASE

    def test_env_bootstrap_default_category_is_all(self, isolated_home, monkeypatch):
        """Bootstrap path defaults --category to 'all' (single full-scope token)."""
        from tests.unit.test_token_utils import TOKEN_PROD_BASE

        monkeypatch.setenv('WB_API_TOKEN', TOKEN_PROD_BASE)
        with patch(PATCH_VALIDATE, return_value=True):
            result = runner.invoke(app, ['auth', 'login'])

        assert result.exit_code == 0
        assert 'all 11 categories' in result.output

    def test_explicit_token_flag_keeps_promotion_default(self, isolated_home):
        """--token without --category keeps the historical 'promotion' default."""
        with patch(PATCH_VALIDATE, return_value=True):
            result = runner.invoke(
                app, ['auth', 'login', '--token', 'tok', '--profile', 'p'],
            )

        assert result.exit_code == 0
        store = ProfileStore(isolated_home / '.wb-cli')
        profile = store.get_profile('p')
        assert list(profile.tokens.keys()) == ['promotion']

    def test_env_bootstrap_explicit_category_honored(
            self, isolated_home, monkeypatch,
    ):
        """Bootstrap path still honors --category overrides."""
        from tests.unit.test_token_utils import TOKEN_PROD_BASE

        monkeypatch.setenv('WB_API_TOKEN', TOKEN_PROD_BASE)
        with patch(PATCH_VALIDATE, return_value=True):
            result = runner.invoke(
                app, ['auth', 'login', '--category', 'promotion'],
            )

        assert result.exit_code == 0
        store = ProfileStore(isolated_home / '.wb-cli')
        profile = store.get_profile('668554_base')
        assert list(profile.tokens.keys()) == ['promotion']

    def test_analytics_env_used_when_category_analytics(
            self, isolated_home, monkeypatch,
    ):
        """``--category analytics`` (no --token) prefers WB_ANALYTICS_TOKEN."""
        from tests.unit.test_token_utils import TOKEN_PROD_BASE

        monkeypatch.setenv('WB_ANALYTICS_TOKEN', TOKEN_PROD_BASE)
        with patch(PATCH_VALIDATE, return_value=True):
            result = runner.invoke(
                app, ['auth', 'login', '--category', 'analytics', '--profile', 'p'],
            )

        assert result.exit_code == 0, result.output
        store = ProfileStore(isolated_home / '.wb-cli')
        assert store.get_profile('p').tokens['analytics'] == TOKEN_PROD_BASE


class TestAuthLoginPortalEnvBootstrap:
    """`wb auth login-portal` mirrors the env-bootstrap pattern."""

    def test_no_flags_no_env_exits_with_config_error(self, isolated_home):
        result = runner.invoke(app, ['auth', 'login-portal'])
        assert result.exit_code == 7
        assert 'WB_AUTHORIZEV3' in result.output

    def test_env_bootstrap_skip_auth(self, isolated_home, monkeypatch):
        """``--skip-auth`` with env creds writes a profile without WB calls."""
        monkeypatch.setenv('WB_AUTHORIZEV3', 'env-authv3')
        monkeypatch.setenv('WB_PORTAL_COOKIE', 'env-cookie')

        result = runner.invoke(
            app, ['auth', 'login-portal', '--skip-auth', '--profile', 'p'],
        )
        assert result.exit_code == 0, result.output
        store = ProfileStore(isolated_home / '.wb-cli')
        session = store.get_profile('p').get_portal_session()
        assert session is not None
        assert session['authorizev3'] == 'env-authv3'
        assert session['cookie'] == 'env-cookie'


# ── auth whoami (A-3) ──────────────────────────────────────────────────


class TestAuthWhoami:
    """`wb auth whoami` is the F-19/F-20 diagnostic closer."""

    def test_no_profile_table_mode(self, isolated_home):
        """Empty home → friendly stderr/stdout, exit 0 (diagnostic)."""
        result = runner.invoke(app, ['auth', 'whoami'])
        assert result.exit_code == 0
        assert 'No active profile' in result.output

    def test_no_profile_json_mode(self, isolated_home):
        """Empty home → JSON payload with ``profile: null`` and ``source``."""
        result = runner.invoke(app, ['--json', 'auth', 'whoami'])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload['profile'] is None
        assert payload['source'] == 'active-profile'
        assert payload['tokens'] == {}

    def test_active_profile_json_includes_fingerprints(self, isolated_home):
        """Each registered category surfaces its SHA-256[:16] fingerprint."""
        from wb.core.rate_limiter import compute_token_fingerprint

        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('p')
        store.save_token('p', 'promotion', 'promo-token')
        store.save_token('p', 'analytics', 'analytics-token')
        store.set_active('p')

        result = runner.invoke(app, ['--json', 'auth', 'whoami'])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload['profile'] == 'p'
        assert payload['source'] == 'active-profile'
        assert payload['tokens']['promotion'] == compute_token_fingerprint('promo-token')
        assert payload['tokens']['analytics'] == compute_token_fingerprint('analytics-token')

    def test_profile_flag_sets_source_to_profile_flag(self, isolated_home):
        """Global ``--profile X`` reports ``source: profile-flag``."""
        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('active_p')
        store.save_token('active_p', 'promotion', 'active-token')
        store.create_profile('other_p')
        store.save_token('other_p', 'promotion', 'other-token')
        store.set_active('active_p')

        result = runner.invoke(
            app, ['--json', '--profile', 'other_p', 'auth', 'whoami'],
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload['profile'] == 'other_p'
        assert payload['source'] == 'profile-flag'

    def test_stale_env_does_not_change_whoami(self, isolated_home, monkeypatch):
        """F-19/F-20 regression: stale env doesn't change the reported fingerprint.

        Before A-2 the runtime chain would have fingerprinted the stale
        env token instead of the active profile's token. After A-2
        whoami reports the *profile* fingerprint regardless of env.
        """
        from wb.core.rate_limiter import compute_token_fingerprint

        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('p')
        store.save_token('p', 'promotion', 'profile-token')
        store.set_active('p')

        monkeypatch.setenv('WB_API_TOKEN', 'STALE-env-token')

        result = runner.invoke(app, ['--json', 'auth', 'whoami'])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        expected_fp = compute_token_fingerprint('profile-token')
        stale_fp = compute_token_fingerprint('STALE-env-token')
        assert payload['tokens']['promotion'] == expected_fp
        assert payload['tokens']['promotion'] != stale_fp

    def test_table_mode_renders_source_field(self, isolated_home):
        """Human-readable mode prints the new Source line."""
        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('p')
        store.save_token('p', 'promotion', 'tok')
        store.set_seller_id('p', '12345')
        store.set_active('p')

        result = runner.invoke(app, ['auth', 'whoami'])
        assert result.exit_code == 0
        assert 'Profile' in result.output
        assert 'Source' in result.output
        assert 'active-profile' in result.output
        assert '12345' in result.output


# ── auth refresh (F-22) ───────────────────────────────────────────────


class TestAuthRefresh:
    """`wb auth refresh` re-decodes the stored JWT to repair seller_id."""

    def test_refresh_restores_seller_id_from_jwt(self, isolated_home):
        """F-22 recovery: refresh resets a clobbered seller_id from the JWT."""
        from tests.unit.test_token_utils import TOKEN_PROD_BASE

        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('25169_personal')
        store.save_token('25169_personal', 'promotion', TOKEN_PROD_BASE)
        store.set_seller_id('25169_personal', '10799201')
        store.set_active('25169_personal')

        result = runner.invoke(app, ['auth', 'refresh'])

        assert result.exit_code == 0, result.output
        reloaded = ProfileStore(isolated_home / '.wb-cli').get_profile('25169_personal')
        assert reloaded.seller_id == '668554'
        assert reloaded.token_expires_at == 1790136818

    def test_refresh_no_token_exits_auth_failure(self, isolated_home):
        """A profile with no JWT cannot be refreshed."""
        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('p')
        store.set_active('p')

        result = runner.invoke(app, ['auth', 'refresh'])

        assert result.exit_code == 3
        assert 'no JWT registered' in result.output.lower() or 'no jwt' in result.output.lower()

    def test_refresh_json_mode_outputs_structured_data(self, isolated_home):
        """--json returns before/after seller_id + token_expires_at."""
        from tests.unit.test_token_utils import TOKEN_PROD_BASE

        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('p')
        store.save_token('p', 'promotion', TOKEN_PROD_BASE)
        store.set_seller_id('p', '10799201')
        store.set_active('p')

        result = runner.invoke(app, ['--json', 'auth', 'refresh'])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload['profile'] == 'p'
        assert payload['before']['seller_id'] == '10799201'
        assert payload['after']['seller_id'] == '668554'
        assert payload['after']['token_expires_at'] == 1790136818

    def test_refresh_explicit_profile_flag(self, isolated_home):
        """--profile targets a non-active profile."""
        from tests.unit.test_token_utils import TOKEN_PROD_BASE

        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('active_p')
        store.set_active('active_p')
        store.create_profile('target_p')
        store.save_token('target_p', 'promotion', TOKEN_PROD_BASE)

        result = runner.invoke(
            app, ['auth', 'refresh', '--profile', 'target_p'],
        )

        assert result.exit_code == 0, result.output
        reloaded = ProfileStore(isolated_home / '.wb-cli').get_profile('target_p')
        assert reloaded.seller_id == '668554'

    def test_refresh_does_not_touch_portal_user_id(self, isolated_home):
        """The portal user_id stays intact across a refresh."""
        from tests.unit.test_token_utils import TOKEN_PROD_BASE

        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('p')
        store.save_token('p', 'promotion', TOKEN_PROD_BASE)
        store.save_portal_session('p', authorizev3='k', user_id='10799201')
        store.set_active('p')

        result = runner.invoke(app, ['auth', 'refresh'])

        assert result.exit_code == 0, result.output
        reloaded = ProfileStore(isolated_home / '.wb-cli').get_profile('p')
        assert reloaded.seller_id == '668554'
        assert reloaded.portal_user_id == '10799201'
