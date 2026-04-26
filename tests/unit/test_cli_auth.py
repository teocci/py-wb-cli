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
    for var in ('WB_API_TOKEN', 'WB_ANALYTICS_TOKEN'):
        monkeypatch.delenv(var, raising=False)
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
