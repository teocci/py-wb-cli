"""Tests for wb.auth.profiles — Profile and ProfileStore."""

import json

import pytest

from wb.auth.profiles import Profile, ProfileStore
from wb.core.constants import (
    ALL_CATEGORY,
    DEFAULT_TOKEN_TYPE,
    TOKEN_CATEGORIES,
    TOKEN_TYPES,
)
from wb.core.exceptions import ConfigError, ValidationError


# ── Profile dataclass ─────────────────────────────────────────────────


class TestProfile:
    """Tests for the Profile dataclass."""

    def test_create_with_name_and_tokens(self):
        """Profile can be created with a name and token mapping."""
        tokens = {'promotion': 'tok-promo'}
        profile = Profile(name='seller-a', tokens=tokens)

        assert profile.name == 'seller-a'
        assert profile.tokens == {'promotion': 'tok-promo'}

    def test_create_defaults(self):
        """Profile created with only a name gets empty tokens and timestamps."""
        profile = Profile(name='bare')

        assert profile.tokens == {}
        assert profile.created_at is not None
        assert profile.last_used is None

    # ── has_token ─────────────────────────────────────────────────────

    @pytest.mark.parametrize(
        'tokens, category, expected',
        [
            ({'promotion': 'abc'}, 'promotion', True),
            ({'promotion': 'abc'}, 'analytics', False),
            ({}, 'promotion', False),
            ({'promotion': ''}, 'promotion', False),
        ],
        ids=[
            'present-category',
            'missing-category',
            'empty-tokens',
            'empty-string-token',
        ],
    )
    def test_has_token(self, tokens, category, expected):
        """has_token returns True only when category key exists and is non-empty."""
        profile = Profile(name='p', tokens=tokens)
        assert profile.has_token(category) is expected

    # ── get_token ─────────────────────────────────────────────────────

    def test_get_token_success(self):
        """get_token returns the stored token string."""
        profile = Profile(name='p', tokens={'analytics': 'secret-123'})
        assert profile.get_token('analytics') == 'secret-123'

    def test_get_token_missing_raises_validation_error(self):
        """get_token raises ValidationError for a missing category."""
        profile = Profile(name='p')
        with pytest.raises(ValidationError, match='no token for category'):
            profile.get_token('analytics')

    # ── set_token ─────────────────────────────────────────────────────

    @pytest.mark.parametrize('category', TOKEN_CATEGORIES)
    def test_set_token_valid_category(self, category):
        """set_token accepts every category in TOKEN_CATEGORIES."""
        profile = Profile(name='p')
        profile.set_token(category, 'tok-value')
        assert profile.tokens[category] == 'tok-value'

    def test_set_token_unknown_category_raises(self):
        """set_token rejects categories not in TOKEN_CATEGORIES."""
        profile = Profile(name='p')
        with pytest.raises(ValidationError, match='Unknown token category'):
            profile.set_token('nonexistent', 'val')

    # ── portal_session ─────────────────────────────────────────────────

    def test_create_defaults_empty_portal_session(self):
        """Profile created with only a name gets empty portal_session."""
        profile = Profile(name='bare2')
        assert profile.portal_session == {}

    def test_has_portal_session_false_when_empty(self):
        """has_portal_session returns False when no session stored."""
        profile = Profile(name='p')
        assert profile.has_portal_session() is False

    def test_has_portal_session_true_when_set(self):
        """has_portal_session returns True after set_portal_session."""
        profile = Profile(name='p')
        profile.set_portal_session(authorizev3='key-123')
        assert profile.has_portal_session() is True

    def test_get_portal_session_none_when_empty(self):
        """get_portal_session returns None when no session stored."""
        profile = Profile(name='p')
        assert profile.get_portal_session() is None

    def test_get_portal_session_returns_copy(self):
        """get_portal_session returns a copy, not the original dict."""
        profile = Profile(name='p')
        profile.set_portal_session(authorizev3='key')
        session = profile.get_portal_session()
        session['injected'] = 'bad'
        assert 'injected' not in profile.portal_session

    def test_set_portal_session_stores_all_fields(self):
        """set_portal_session stores all provided fields."""
        profile = Profile(name='p')
        profile.set_portal_session(
            authorizev3='auth-key',
            cookie='session=abc',
            session_token='jwt-token',
            user_id='12345',
            exp='1773884106',
        )
        session = profile.get_portal_session()
        assert session['authorizev3'] == 'auth-key'
        assert session['cookie'] == 'session=abc'
        assert session['session_token'] == 'jwt-token'
        assert session['user_id'] == '12345'
        assert session['exp'] == '1773884106'

    def test_set_portal_session_omits_none_fields(self):
        """set_portal_session does not store None-valued optional fields."""
        profile = Profile(name='p')
        profile.set_portal_session(authorizev3='key')
        session = profile.get_portal_session()
        assert 'cookie' not in session
        assert 'session_token' not in session

    # ── to_dict / from_dict roundtrip ─────────────────────────────────

    def test_roundtrip_to_dict_from_dict(self):
        """Profile survives a to_dict -> from_dict roundtrip."""
        original = Profile(
            name='roundtrip',
            tokens={'promotion': 'rt-tok'},
            created_at='2025-01-01T00:00:00+00:00',
            last_used='2025-06-15T12:30:00+00:00',
        )
        rebuilt = Profile.from_dict(original.to_dict())

        assert rebuilt.name == original.name
        assert rebuilt.tokens == original.tokens
        assert rebuilt.created_at == original.created_at
        assert rebuilt.last_used == original.last_used

    def test_roundtrip_with_portal_session(self):
        """Profile with portal_session survives to_dict -> from_dict."""
        original = Profile(name='portal-rt')
        original.set_portal_session(
            authorizev3='key',
            session_token='jwt',
            user_id='123',
        )
        rebuilt = Profile.from_dict(original.to_dict())
        assert rebuilt.portal_session == original.portal_session
        assert rebuilt.has_portal_session() is True

    def test_to_dict_omits_empty_portal_session(self):
        """to_dict does not include portal_session when empty."""
        profile = Profile(name='no-portal')
        data = profile.to_dict()
        assert 'portal_session' not in data

    def test_from_dict_missing_optional_fields(self):
        """from_dict fills defaults for optional keys."""
        data = {'name': 'minimal'}
        profile = Profile.from_dict(data)

        assert profile.name == 'minimal'
        assert profile.tokens == {}
        assert profile.portal_session == {}
        assert profile.last_used is None

    # ── token_type (R-5) ──────────────────────────────────────────────

    def test_default_token_type_is_base(self):
        """New profiles default token_type to DEFAULT_TOKEN_TYPE ('base')."""
        profile = Profile(name='p')
        assert profile.token_type == DEFAULT_TOKEN_TYPE
        assert profile.token_type == 'base'

    @pytest.mark.parametrize('token_type', TOKEN_TYPES)
    def test_token_type_persists_through_roundtrip(self, token_type):
        """to_dict/from_dict preserves every TOKEN_TYPES value."""
        original = Profile(name='p', token_type=token_type)
        rebuilt = Profile.from_dict(original.to_dict())
        assert rebuilt.token_type == token_type

    def test_legacy_dict_without_token_type_defaults_to_base(self):
        """Profiles JSON written before R-5 must read as 'base'."""
        legacy_data = {'name': 'legacy', 'tokens': {'promotion': 'tok'}}
        profile = Profile.from_dict(legacy_data)
        assert profile.token_type == DEFAULT_TOKEN_TYPE

    def test_to_dict_includes_token_type(self):
        """to_dict must serialize the token_type field."""
        profile = Profile(name='p', token_type='personal')
        data = profile.to_dict()
        assert data['token_type'] == 'personal'

    # ── touch ─────────────────────────────────────────────────────────

    def test_touch_sets_last_used(self):
        """touch() populates last_used with an ISO timestamp."""
        profile = Profile(name='p')
        assert profile.last_used is None
        profile.touch()
        assert profile.last_used is not None


# ── ProfileStore ──────────────────────────────────────────────────────


class TestProfileStore:
    """Tests for ProfileStore filesystem operations."""

    def test_create_profile_on_disk(self, tmp_path):
        """create_profile persists a new profile to disk."""
        store = ProfileStore(tmp_path)
        store.create_profile('seller-1')

        profiles_file = tmp_path / 'profiles.json'
        assert profiles_file.exists()
        data = json.loads(profiles_file.read_text(encoding='utf-8'))
        names = [p['name'] for p in data['profiles']]
        assert 'seller-1' in names

    def test_create_duplicate_raises(self, tmp_path):
        """Creating a profile that already exists raises ValidationError."""
        store = ProfileStore(tmp_path)
        store.create_profile('dup')
        with pytest.raises(ValidationError, match='already exists'):
            store.create_profile('dup')

    def test_list_profiles_returns_all(self, tmp_path):
        """list_profiles returns every stored profile."""
        store = ProfileStore(tmp_path)
        store.create_profile('a')
        store.create_profile('b')

        names = [p.name for p in store.list_profiles()]
        assert sorted(names) == ['a', 'b']

    def test_list_profiles_empty(self, tmp_path):
        """list_profiles returns empty list when no profiles exist."""
        store = ProfileStore(tmp_path)
        assert store.list_profiles() == []

    def test_get_profile_returns_correct(self, tmp_path):
        """get_profile retrieves the named profile."""
        store = ProfileStore(tmp_path)
        store.create_profile('target')
        store.create_profile('other')

        profile = store.get_profile('target')
        assert profile.name == 'target'

    def test_get_profile_nonexistent_raises_config_error(self, tmp_path):
        """get_profile raises ConfigError for an unknown profile."""
        store = ProfileStore(tmp_path)
        with pytest.raises(ConfigError, match='does not exist'):
            store.get_profile('ghost')

    def test_get_profile_defaults_to_active(self, tmp_path):
        """get_profile with no argument returns the active profile."""
        store = ProfileStore(tmp_path)
        store.create_profile('default')
        profile = store.get_profile()
        assert profile.name == 'default'

    def test_set_active_changes_active_profile(self, tmp_path):
        """set_active switches the active profile."""
        store = ProfileStore(tmp_path)
        store.create_profile('alpha')
        store.create_profile('beta')

        store.set_active('beta')
        assert store.active_profile_name == 'beta'

    def test_set_active_nonexistent_raises_config_error(self, tmp_path):
        """set_active raises ConfigError for a missing profile."""
        store = ProfileStore(tmp_path)
        with pytest.raises(ConfigError, match='does not exist'):
            store.set_active('no-such-profile')

    def test_save_token_stores_token(self, tmp_path):
        """save_token writes the token into an existing profile."""
        store = ProfileStore(tmp_path)
        store.create_profile('tok-test')
        store.save_token('tok-test', 'promotion', 'promo-123')

        profile = store.get_profile('tok-test')
        assert profile.get_token('promotion') == 'promo-123'

    def test_save_token_creates_profile_if_needed(self, tmp_path):
        """save_token auto-creates a profile when it does not exist."""
        store = ProfileStore(tmp_path)
        store.save_token('auto-created', 'analytics', 'an-tok')

        profile = store.get_profile('auto-created')
        assert profile.has_token('analytics')

    def test_save_token_all_saves_every_category(self, tmp_path):
        """save_token with ALL_CATEGORY stores token under every real category."""
        store = ProfileStore(tmp_path)
        store.create_profile('p')
        store.save_token('p', ALL_CATEGORY, 'my-token')
        profile = store.get_profile('p')
        for cat in TOKEN_CATEGORIES:
            assert profile.get_token(cat) == 'my-token'

    def test_set_token_rejects_all_sentinel(self):
        """Profile.set_token must not accept the 'all' sentinel directly."""
        profile = Profile(name='p')
        with pytest.raises(ValidationError, match='Unknown token category'):
            profile.set_token(ALL_CATEGORY, 'tok')

    def test_delete_profile_removes(self, tmp_path):
        """delete_profile removes the profile from the store."""
        store = ProfileStore(tmp_path)
        store.create_profile('doomed')
        store.create_profile('survivor')
        store.set_active('survivor')

        store.delete_profile('doomed')
        names = [p.name for p in store.list_profiles()]
        assert 'doomed' not in names

    def test_delete_profile_nonexistent_raises(self, tmp_path):
        """delete_profile raises ConfigError for a missing profile."""
        store = ProfileStore(tmp_path)
        with pytest.raises(ConfigError, match='does not exist'):
            store.delete_profile('nope')

    def test_delete_active_profile_raises_validation_error(self, tmp_path):
        """Deleting the active profile raises ValidationError."""
        store = ProfileStore(tmp_path)
        store.create_profile('default')

        with pytest.raises(ValidationError, match='active profile'):
            store.delete_profile('default')

    def test_profiles_persist_across_instances(self, tmp_path):
        """Profiles survive construction of a new ProfileStore from the same dir."""
        store1 = ProfileStore(tmp_path)
        store1.create_profile('persist-me')
        store1.save_token('persist-me', 'promotion', 'my-token')
        store1.set_active('persist-me')

        store2 = ProfileStore(tmp_path)
        assert store2.active_profile_name == 'persist-me'
        profile = store2.get_profile('persist-me')
        assert profile.get_token('promotion') == 'my-token'

    def test_corrupted_profiles_file_raises_config_error(self, tmp_path):
        """A corrupted JSON profiles file raises ConfigError on load."""
        profiles_file = tmp_path / 'profiles.json'
        profiles_file.write_text('not-valid-json', encoding='utf-8')

        with pytest.raises(ConfigError, match='Corrupted profiles file'):
            ProfileStore(tmp_path)

    def test_save_portal_session_stores_session(self, tmp_path):
        """save_portal_session writes portal session into a profile."""
        store = ProfileStore(tmp_path)
        store.create_profile('portal-test')
        store.save_portal_session(
            profile_name='portal-test',
            authorizev3='key-abc',
            session_token='jwt-xyz',
            user_id='999',
        )
        profile = store.get_profile('portal-test')
        assert profile.has_portal_session() is True
        session = profile.get_portal_session()
        assert session['authorizev3'] == 'key-abc'
        assert session['session_token'] == 'jwt-xyz'

    def test_save_portal_session_creates_profile_if_needed(self, tmp_path):
        """save_portal_session auto-creates a profile when it does not exist."""
        store = ProfileStore(tmp_path)
        store.save_portal_session(
            profile_name='auto-portal',
            authorizev3='key',
        )
        profile = store.get_profile('auto-portal')
        assert profile.has_portal_session() is True

    def test_portal_session_persists_across_instances(self, tmp_path):
        """Portal session survives construction of a new ProfileStore."""
        store1 = ProfileStore(tmp_path)
        store1.create_profile('persist-portal')
        store1.save_portal_session(
            profile_name='persist-portal',
            authorizev3='my-key',
            session_token='my-jwt',
        )

        store2 = ProfileStore(tmp_path)
        profile = store2.get_profile('persist-portal')
        assert profile.has_portal_session() is True
        assert profile.get_portal_session()['authorizev3'] == 'my-key'

    def test_config_dir_created_on_save(self, tmp_path):
        """ProfileStore creates intermediate directories when saving."""
        nested_dir = tmp_path / 'deep' / 'nested'
        store = ProfileStore(nested_dir)
        store.create_profile('deep-profile')

        assert (nested_dir / 'profiles.json').exists()

    # ── set_token_type (R-5) ──────────────────────────────────────────

    def test_set_token_type_persists(self, tmp_path):
        """set_token_type writes to disk and reloads correctly."""
        store = ProfileStore(tmp_path)
        store.create_profile('typed')
        store.set_token_type('typed', 'personal')

        reloaded = ProfileStore(tmp_path).get_profile('typed')
        assert reloaded.token_type == 'personal'

    def test_set_token_type_rejects_unknown_value(self, tmp_path):
        """set_token_type raises ValidationError for unknown types."""
        store = ProfileStore(tmp_path)
        store.create_profile('p')
        with pytest.raises(ValidationError, match='Unknown token type'):
            store.set_token_type('p', 'super-base')

    def test_set_token_type_missing_profile_raises(self, tmp_path):
        """set_token_type raises ConfigError when the profile doesn't exist."""
        store = ProfileStore(tmp_path)
        with pytest.raises(ConfigError, match='does not exist'):
            store.set_token_type('ghost', 'base')

    # ── seller_id / token_expires_at (A-1) / portal_user_id (F-22) ───

    def test_save_portal_session_writes_portal_user_id_not_seller_id(self, tmp_path):
        """save_portal_session writes user_id to portal_user_id, not seller_id (F-22)."""
        store = ProfileStore(tmp_path)
        store.create_profile('p')
        store.save_portal_session('p', authorizev3='k', user_id='55555')
        profile = store.get_profile('p')
        assert profile.portal_user_id == '55555'
        assert profile.seller_id is None

    def test_save_portal_session_without_user_id_leaves_both_none(self, tmp_path):
        """When user_id is omitted, both seller_id and portal_user_id stay None."""
        store = ProfileStore(tmp_path)
        store.create_profile('p')
        store.save_portal_session('p', authorizev3='k')
        profile = store.get_profile('p')
        assert profile.seller_id is None
        assert profile.portal_user_id is None

    def test_save_portal_session_does_not_clobber_existing_seller_id(self, tmp_path):
        """F-22 regression: login-portal must not overwrite JWT-derived seller_id."""
        store = ProfileStore(tmp_path)
        store.create_profile('25169_personal')
        store.set_seller_id('25169_personal', '25169')

        store.save_portal_session(
            '25169_personal',
            authorizev3='k',
            user_id='10799201',
        )

        profile = store.get_profile('25169_personal')
        assert profile.seller_id == '25169'
        assert profile.portal_user_id == '10799201'

    def test_portal_user_id_persists_through_save_reload(self, tmp_path):
        """portal_user_id survives a ProfileStore reload (to_dict/from_dict roundtrip)."""
        store1 = ProfileStore(tmp_path)
        store1.create_profile('p')
        store1.save_portal_session('p', authorizev3='k', user_id='12345')

        store2 = ProfileStore(tmp_path)
        assert store2.get_profile('p').portal_user_id == '12345'

    def test_from_dict_back_fills_portal_user_id_from_portal_session(self):
        """Legacy on-disk profiles (pre-F-22) get portal_user_id from portal_session.user_id."""
        legacy = {
            'name': 'legacy',
            'tokens': {},
            'portal_session': {'authorizev3': 'k', 'user_id': '99'},
            'token_type': DEFAULT_TOKEN_TYPE,
            'created_at': '2026-05-23T00:00:00+00:00',
            'last_used': None,
        }
        profile = Profile.from_dict(legacy)
        assert profile.portal_user_id == '99'

    def test_find_all_by_seller_id_returns_multiple(self, tmp_path):
        """A seller with multiple profiles returns all of them."""
        store = ProfileStore(tmp_path)
        store.create_profile('p1')
        store.set_seller_id('p1', 'S1')
        store.create_profile('p2')
        store.set_seller_id('p2', 'S1')
        store.create_profile('p3')
        store.set_seller_id('p3', 'S2')

        matches = store.find_all_by_seller_id('S1')
        assert sorted(p.name for p in matches) == ['p1', 'p2']

    def test_find_all_by_seller_id_returns_empty_for_unknown(self, tmp_path):
        """Unknown seller_id returns an empty list, not None."""
        store = ProfileStore(tmp_path)
        store.create_profile('p')
        assert store.find_all_by_seller_id('no-such-seller') == []

    def test_set_seller_id_persists(self, tmp_path):
        """set_seller_id writes to disk and reloads correctly."""
        store = ProfileStore(tmp_path)
        store.create_profile('p')
        store.set_seller_id('p', '99')

        reloaded = ProfileStore(tmp_path).get_profile('p')
        assert reloaded.seller_id == '99'

    def test_set_seller_id_missing_profile_raises(self, tmp_path):
        """set_seller_id raises ConfigError when the profile doesn't exist."""
        store = ProfileStore(tmp_path)
        with pytest.raises(ConfigError, match='does not exist'):
            store.set_seller_id('ghost', 'S1')

    def test_set_token_expires_at_persists(self, tmp_path):
        """set_token_expires_at writes to disk and reloads correctly."""
        store = ProfileStore(tmp_path)
        store.create_profile('p')
        store.set_token_expires_at('p', 1790136818)

        reloaded = ProfileStore(tmp_path).get_profile('p')
        assert reloaded.token_expires_at == 1790136818

    def test_set_token_expires_at_missing_profile_raises(self, tmp_path):
        """set_token_expires_at raises ConfigError when the profile doesn't exist."""
        store = ProfileStore(tmp_path)
        with pytest.raises(ConfigError, match='does not exist'):
            store.set_token_expires_at('ghost', 123)

    def test_profile_token_expires_at_roundtrip(self, tmp_path):
        """token_expires_at survives to_dict → from_dict via the store."""
        store = ProfileStore(tmp_path)
        store.create_profile('p')
        store.set_token_expires_at('p', 1234567890)
        assert ProfileStore(tmp_path).get_profile('p').token_expires_at == 1234567890

    def test_to_dict_omits_token_expires_at_when_none(self, tmp_path):
        """to_dict does not include token_expires_at when unset."""
        profile = Profile(name='p')
        assert 'token_expires_at' not in profile.to_dict()
