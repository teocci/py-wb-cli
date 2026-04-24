"""Tests for I-13 (`wb rate status`) and I-14 (`wb rate probe`)."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx
from typer.testing import CliRunner

from wb.cli.app import app

runner = CliRunner()

TOKEN = '.'.join([
    'eyJhbGciOiJIUzI1NiJ9',
    # base64url({"sid":"seller-under-test","iid":1,"exp":9999999999})
    'eyJzaWQiOiJzZWxsZXItdW5kZXItdGVzdCIsImlpZCI6MSwiZXhwIjo5OTk5OTk5OTk5fQ',
    'sig',
])


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Redirect config dir to a temp path; no network calls in these tests."""
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('WB_API_TOKEN', TOKEN)
    yield tmp_path


def _insert_rate_log_row(db: Path, token_fp: str, endpoint: str, age_s: float) -> None:
    conn = sqlite3.connect(str(db))
    conn.execute('''
        CREATE TABLE IF NOT EXISTS rate_limit_log (
            token TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            ts REAL NOT NULL
        );
    ''')
    conn.execute(
        'INSERT INTO rate_limit_log VALUES (?, ?, ?)',
        (token_fp, endpoint, time.time() - age_s),
    )
    conn.commit()
    conn.close()


class TestRateStatus:
    """I-13: read-only diagnostic; asserts output shape for clear & locked states."""

    def test_help(self):
        result = runner.invoke(app, ['rate', 'status', '--help'])
        assert result.exit_code == 0
        assert 'seller cooldown' in result.output.lower()

    def test_json_output_clean_state(self, isolated_home):
        """No DB rows → `locked=false` and empty activity list."""
        result = runner.invoke(app, ['--json', 'rate', 'status'])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload['locked'] is False
        assert payload['seller_cooldown_seconds'] == 0.0
        assert payload['endpoint_activity_5min'] == []
        assert payload['seller_fingerprint']  # non-empty — derived from token

    def test_json_output_locked_state(self, isolated_home):
        """After recording a cooldown, `locked=true` and remaining > 0."""
        from wb.core.rate_limiter import SellerCooldownLock, compute_seller_fingerprint
        db = isolated_home / '.wb-cli' / 'rate_limits.db'
        db.parent.mkdir(parents=True, exist_ok=True)
        lock = SellerCooldownLock(db_path=db)
        fp = compute_seller_fingerprint(TOKEN)
        lock.record(fp, cooldown_seconds=45.0)

        result = runner.invoke(app, ['--json', 'rate', 'status'])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload['locked'] is True
        assert 44.0 < payload['seller_cooldown_seconds'] <= 45.0
        assert payload['seller_fingerprint'] == fp

    def test_endpoint_activity_summarised(self, isolated_home):
        """Rows in the last 5 min are grouped by endpoint and age-ordered."""
        db = isolated_home / '.wb-cli' / 'rate_limits.db'
        db.parent.mkdir(parents=True, exist_ok=True)
        _insert_rate_log_row(db, 'tokfp', '/adv/v3/fullstats', age_s=10)
        _insert_rate_log_row(db, 'tokfp', '/adv/v3/fullstats', age_s=120)
        _insert_rate_log_row(db, 'tokfp', '/api/advert/v2/adverts', age_s=5)

        result = runner.invoke(app, ['--json', 'rate', 'status'])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        activity = payload['endpoint_activity_5min']
        by_ep = {row['endpoint']: row for row in activity}
        assert by_ep['/api/advert/v2/adverts']['count'] == 1
        assert by_ep['/adv/v3/fullstats']['count'] == 2
        # Ordered newest-first
        assert activity[0]['endpoint'] == '/api/advert/v2/adverts'

    def test_old_rows_excluded_from_activity(self, isolated_home):
        """Rows older than 5 min don't appear in the summary."""
        db = isolated_home / '.wb-cli' / 'rate_limits.db'
        db.parent.mkdir(parents=True, exist_ok=True)
        _insert_rate_log_row(db, 'tokfp', '/old/endpoint', age_s=1000)

        result = runner.invoke(app, ['--json', 'rate', 'status'])
        payload = json.loads(result.output)
        assert payload['endpoint_activity_5min'] == []

    def test_table_output_contains_key_fields(self, isolated_home):
        """Table mode (default) prints profile, fingerprint, lock status."""
        result = runner.invoke(app, ['rate', 'status'])
        assert result.exit_code == 0
        assert 'Seller fingerprint' in result.output
        assert 'Seller cooldown' in result.output
        # Clean-state prints the literal 'clear' word
        assert 'clear' in result.output.lower()

    def test_compact_json_is_single_line(self, isolated_home):
        """--compact produces single-line JSON."""
        result = runner.invoke(app, ['--json', '--compact', 'rate', 'status'])
        assert result.exit_code == 0
        # Single line means no indent newlines between braces
        assert '\n' not in result.output.strip()
        payload = json.loads(result.output)
        assert 'locked' in payload

    def test_no_token_no_crash(self, tmp_path, monkeypatch):
        """Runs cleanly even when no token is available."""
        monkeypatch.setattr(Path, 'home', lambda: tmp_path)
        monkeypatch.delenv('WB_API_TOKEN', raising=False)
        monkeypatch.delenv('WB_ANALYTICS_TOKEN', raising=False)
        # Isolate from any .env in cwd by pointing the settings at tmp_path
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(app, ['--json', 'rate', 'status'])
        # Should complete (exit 0) with an empty fingerprint, not crash.
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload['seller_cooldown_seconds'] == 0.0
        assert payload['locked'] is False


class TestRateProbe:
    """I-14: single-call probe that respects the F-13 cooldown lock."""

    PROBE_URL = 'https://advert-api.wildberries.ru/adv/v1/balance'

    def test_help(self, isolated_home):
        result = runner.invoke(app, ['rate', 'probe', '--help'])
        assert result.exit_code == 0
        assert 'probe' in result.output.lower()

    def test_skips_network_when_lock_active(self, isolated_home):
        """Active lock → no HTTP call, outcome='lock-active', exit 5."""
        from wb.core.rate_limiter import (
            SellerCooldownLock, compute_seller_fingerprint,
        )

        db = isolated_home / '.wb-cli' / 'rate_limits.db'
        db.parent.mkdir(parents=True, exist_ok=True)
        lock = SellerCooldownLock(db_path=db)
        fp = compute_seller_fingerprint(TOKEN)
        lock.record(fp, cooldown_seconds=60.0)

        with respx.mock:
            route = respx.get(self.PROBE_URL).mock(
                return_value=httpx.Response(200)
            )
            result = runner.invoke(app, ['--json', 'rate', 'probe'])

        assert result.exit_code == 5
        assert route.call_count == 0  # critical: no HTTP call
        payload = json.loads(result.output)
        assert payload['outcome'] == 'lock-active'
        assert payload['locked'] is True
        assert 59.0 < payload['cooldown_seconds'] <= 60.0

    def test_200_reports_calls_remaining(self, isolated_home):
        """Clear state + 200 with `x-ratelimit-remaining` → outcome='ok'."""
        with respx.mock:
            respx.get(self.PROBE_URL).mock(
                return_value=httpx.Response(
                    200,
                    json={'balance': 1000},
                    headers={'x-ratelimit-remaining': '27'},
                )
            )
            result = runner.invoke(app, ['--json', 'rate', 'probe'])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload['outcome'] == 'ok'
        assert payload['locked'] is False
        assert payload['calls_remaining'] == 27
        assert payload['http_status'] == 200

    def test_200_without_remaining_header(self, isolated_home):
        """200 without the header → calls_remaining=null, still exit 0."""
        with respx.mock:
            respx.get(self.PROBE_URL).mock(
                return_value=httpx.Response(200, json={'balance': 1000})
            )
            result = runner.invoke(app, ['--json', 'rate', 'probe'])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload['outcome'] == 'ok'
        assert payload['calls_remaining'] is None

    def test_429_updates_lock_and_exits(self, isolated_home):
        """429 → reset written to lock, outcome='429', exit 5."""
        from wb.core.rate_limiter import (
            SellerCooldownLock, compute_seller_fingerprint,
        )

        with respx.mock:
            respx.get(self.PROBE_URL).mock(
                return_value=httpx.Response(
                    429,
                    headers={'x-ratelimit-reset': '120'},
                    json={'detail': 'Limited by global limiter'},
                )
            )
            result = runner.invoke(app, ['--json', 'rate', 'probe'])

        assert result.exit_code == 5
        payload = json.loads(result.output)
        assert payload['outcome'] == '429'
        assert payload['locked'] is True
        assert payload['cooldown_seconds'] == 120.0

        # Lock was persisted
        db = isolated_home / '.wb-cli' / 'rate_limits.db'
        lock = SellerCooldownLock(db_path=db)
        fp = compute_seller_fingerprint(TOKEN)
        remaining = lock.read_remaining(fp)
        assert remaining is not None and 119.0 < remaining <= 120.0

    def test_500_does_not_touch_lock(self, isolated_home):
        """Non-429 error → lock not written, outcome='error', exit 6."""
        from wb.core.rate_limiter import (
            SellerCooldownLock, compute_seller_fingerprint,
        )

        with respx.mock:
            respx.get(self.PROBE_URL).mock(
                return_value=httpx.Response(500, text='boom')
            )
            result = runner.invoke(app, ['--json', 'rate', 'probe'])

        assert result.exit_code == 6
        payload = json.loads(result.output)
        assert payload['outcome'] == 'error'
        assert payload['locked'] is False

        # Lock unchanged
        db = isolated_home / '.wb-cli' / 'rate_limits.db'
        if db.exists():
            lock = SellerCooldownLock(db_path=db)
            fp = compute_seller_fingerprint(TOKEN)
            assert lock.read_remaining(fp) is None

    def test_no_token_exits_config_error(self, tmp_path, monkeypatch):
        """No token → outcome='no-token', exit 7 (CONFIG_ERROR)."""
        monkeypatch.setattr(Path, 'home', lambda: tmp_path)
        monkeypatch.delenv('WB_API_TOKEN', raising=False)
        monkeypatch.delenv('WB_ANALYTICS_TOKEN', raising=False)
        monkeypatch.chdir(tmp_path)

        with respx.mock:
            route = respx.get(self.PROBE_URL).mock(
                return_value=httpx.Response(200)
            )
            result = runner.invoke(app, ['--json', 'rate', 'probe'])

        assert result.exit_code == 7
        assert route.call_count == 0
        payload = json.loads(result.output)
        assert payload['outcome'] == 'no-token'
