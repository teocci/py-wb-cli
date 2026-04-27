"""Tests for `wb api-cache status` and `wb api-cache clear`."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.core.constants import EP_CAMPAIGN_INFO, REQUEST_CACHE_DB_FILE
from wb.storage.request_cache import RequestCache


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ~/.wb-cli at a tmp dir for the duration of the test."""
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('USERPROFILE', str(tmp_path))
    config_dir = tmp_path / '.wb-cli'
    config_dir.mkdir()
    return config_dir


def _populate_cache(config_dir: Path, **rows: tuple[str, str, bytes]) -> None:
    """Helper: insert rows directly into the on-disk cache."""
    cache = RequestCache(db_path=config_dir / REQUEST_CACHE_DB_FILE)
    for params_hash, (token_fp, endpoint, payload) in rows.items():
        cache.put(token_fp, endpoint, params_hash, payload, ttl_seconds=3600)


class TestApiCacheStatus:
    def test_empty_returns_no_cached_responses(
            self, runner: CliRunner, isolated_config: Path,
    ) -> None:
        result = runner.invoke(app, ['api-cache', 'status'])
        assert result.exit_code == 0
        assert 'No cached responses yet.' in result.output

    def test_empty_json_returns_empty_sellers(
            self, runner: CliRunner, isolated_config: Path,
    ) -> None:
        result = runner.invoke(app, ['--json', 'api-cache', 'status'])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload['sellers'] == []
        assert 'now_epoch' in payload

    def test_populated_status_groups_by_token(
            self, runner: CliRunner, isolated_config: Path,
    ) -> None:
        _populate_cache(
            isolated_config,
            h1=('fp_alice', EP_CAMPAIGN_INFO, b'{"adverts":[]}'),
            h2=('fp_alice', EP_CAMPAIGN_INFO, b'{"adverts":[{"id":1}]}'),
            h3=('fp_bob', EP_CAMPAIGN_INFO, b'{"adverts":[]}'),
        )
        result = runner.invoke(app, ['--json', 'api-cache', 'status'])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert len(payload['sellers']) == 1  # both tokens unknown seller
        sellers = payload['sellers'][0]
        assert sellers['seller_id'] is None
        token_fps = {tok['token_fp'] for tok in sellers['tokens']}
        assert token_fps == {'fp_alice', 'fp_bob'}

    def test_status_reports_row_counts_and_bytes(
            self, runner: CliRunner, isolated_config: Path,
    ) -> None:
        _populate_cache(
            isolated_config,
            h1=('fp', EP_CAMPAIGN_INFO, b'a' * 100),
            h2=('fp', EP_CAMPAIGN_INFO, b'b' * 200),
        )
        result = runner.invoke(app, ['--json', 'api-cache', 'status'])
        payload = json.loads(result.output)
        ep = payload['sellers'][0]['tokens'][0]['endpoints'][0]
        assert ep['endpoint'] == EP_CAMPAIGN_INFO
        assert ep['rows'] == 2
        assert ep['bytes'] == 300
        assert ep['fresh'] is True


class TestApiCacheClear:
    def test_clear_all_with_yes_flag(
            self, runner: CliRunner, isolated_config: Path,
    ) -> None:
        _populate_cache(
            isolated_config,
            h1=('fp1', EP_CAMPAIGN_INFO, b'a'),
            h2=('fp2', EP_CAMPAIGN_INFO, b'b'),
        )
        result = runner.invoke(app, ['--json', 'api-cache', 'clear', '--all', '--yes'])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload['deleted'] == 2
        assert payload['scope']['all'] is True

    def test_clear_all_in_json_mode_skips_prompt(
            self, runner: CliRunner, isolated_config: Path,
    ) -> None:
        # JSON mode auto-confirms (operators can't supply stdin).
        _populate_cache(isolated_config, h=('fp', EP_CAMPAIGN_INFO, b'x'))
        result = runner.invoke(app, ['--json', 'api-cache', 'clear', '--all'])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload['deleted'] == 1

    def test_clear_by_endpoint_scoped(
            self, runner: CliRunner, isolated_config: Path,
    ) -> None:
        from wb.core.constants import EP_FUNNEL_PRODUCTS
        _populate_cache(
            isolated_config,
            h1=('fp', EP_CAMPAIGN_INFO, b'a'),
            h2=('fp', EP_FUNNEL_PRODUCTS, b'b'),
        )
        result = runner.invoke(app, [
            '--json', 'api-cache', 'clear',
            '--all',  # scope to all tokens
            '--endpoint', EP_CAMPAIGN_INFO,
            '--yes',
        ])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload['deleted'] == 1

        # Funnel entry survived.
        cache = RequestCache(db_path=isolated_config / REQUEST_CACHE_DB_FILE)
        rows = cache.read_all()
        endpoints = {r.endpoint for r in rows}
        assert EP_FUNNEL_PRODUCTS in endpoints
        assert EP_CAMPAIGN_INFO not in endpoints

    def test_clear_without_token_scope_refuses(
            self, runner: CliRunner, isolated_config: Path,
    ) -> None:
        # No profiles registered, no --all, no --token → refuse to wipe.
        _populate_cache(isolated_config, h=('fp', EP_CAMPAIGN_INFO, b'x'))
        result = runner.invoke(app, ['api-cache', 'clear'])
        assert result.exit_code == 2
        assert 'Cannot resolve a token' in result.output

    def test_clear_with_explicit_token_fp(
            self, runner: CliRunner, isolated_config: Path,
    ) -> None:
        _populate_cache(
            isolated_config,
            h1=('fp_alice', EP_CAMPAIGN_INFO, b'a'),
            h2=('fp_bob', EP_CAMPAIGN_INFO, b'b'),
        )
        result = runner.invoke(app, [
            '--json', 'api-cache', 'clear',
            '--token', 'fp_alice',
        ])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload['deleted'] == 1

        # Bob's row survived.
        cache = RequestCache(db_path=isolated_config / REQUEST_CACHE_DB_FILE)
        rows = cache.read_all()
        token_fps = {r.token_fp for r in rows}
        assert token_fps == {'fp_bob'}


class TestNoCacheFlag:
    def test_no_cache_flag_sets_env_var(
            self, runner: CliRunner, isolated_config: Path,
            monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # The flag should set WB_REQUEST_CACHE=disabled before any client
        # is constructed. We verify by invoking a no-op command with the
        # flag and checking the env var landed.
        monkeypatch.delenv('WB_REQUEST_CACHE', raising=False)
        result = runner.invoke(app, ['--no-cache', 'version'])
        assert result.exit_code == 0
        # The env var was set during the callback.
        import os
        assert os.environ.get('WB_REQUEST_CACHE') == 'disabled'
