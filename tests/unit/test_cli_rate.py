"""Tests for I-13 + R-3 + R-5 (`wb rate status`)."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.services._factory import ServiceContainer

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
    ServiceContainer.reset()  # endpoint_budget is cached per-process
    yield tmp_path
    ServiceContainer.reset()


def _seed_budget_row(
        db: Path,
        *,
        token_fp: str,
        endpoint: str,
        seller_id: str | None,
        bucket_limit: int | None,
        remaining: int | None,
        reset_in_s: float,
        last_seen_age_s: float = 0.0,
) -> None:
    """Insert one ``endpoint_budget`` row directly. Mirrors observe()'s output."""
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS endpoint_budget (
                token_fp     TEXT NOT NULL,
                endpoint     TEXT NOT NULL,
                seller_id    TEXT,
                bucket_limit INTEGER,
                remaining    INTEGER,
                reset_at     REAL NOT NULL,
                last_seen    REAL NOT NULL,
                PRIMARY KEY (token_fp, endpoint)
            );
        ''')
        now = time.time()
        conn.execute(
            'INSERT OR REPLACE INTO endpoint_budget '
            '(token_fp, endpoint, seller_id, bucket_limit, remaining, reset_at, last_seen) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (
                token_fp, endpoint, seller_id, bucket_limit, remaining,
                now + reset_in_s, now - last_seen_age_s,
            ),
        )
        conn.commit()
    finally:
        conn.close()


class TestRateStatus:
    """R-3: per-(seller, token, endpoint) view from the endpoint_budget table."""

    def test_help(self):
        result = runner.invoke(app, ['rate', 'status', '--help'])
        assert result.exit_code == 0
        # The help text describes the new budget-state view
        assert 'rate-limit budget' in result.output.lower()

    def test_json_output_clean_state(self, isolated_home):
        """No DB rows → ``sellers`` is an empty list."""
        result = runner.invoke(app, ['--json', 'rate', 'status'])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload['sellers'] == []
        assert isinstance(payload['now_epoch'], (int, float))
        assert payload['profile']

    def test_locked_endpoint_surfaces(self, isolated_home):
        """A row with remaining=0 and reset_at > now is marked locked."""
        db = isolated_home / '.wb-cli' / 'rate_limits.db'
        _seed_budget_row(
            db,
            token_fp='aabbccdd11223344',
            endpoint='/adv/v3/fullstats',
            seller_id='seller-under-test',
            bucket_limit=3,
            remaining=0,
            reset_in_s=3499.0,
        )

        result = runner.invoke(app, ['--json', 'rate', 'status'])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert len(payload['sellers']) == 1

        seller = payload['sellers'][0]
        assert seller['seller_id'] == 'seller-under-test'
        assert len(seller['tokens']) == 1

        token = seller['tokens'][0]
        assert token['token_fp'] == 'aabbccdd11223344'

        ep = token['endpoints'][0]
        assert ep['endpoint'] == '/adv/v3/fullstats'
        assert ep['locked'] is True
        assert ep['remaining'] == 0
        assert ep['bucket_limit'] == 3
        assert 3490 <= ep['reset_in_s'] <= 3499

    def test_unlocked_endpoint_not_marked_locked(self, isolated_home):
        """remaining > 0 → locked=false even when reset_at is in the future."""
        db = isolated_home / '.wb-cli' / 'rate_limits.db'
        _seed_budget_row(
            db,
            token_fp='aabbccdd11223344',
            endpoint='/adv/v1/balance',
            seller_id='seller-under-test',
            bucket_limit=1,
            remaining=1,
            reset_in_s=15.0,
        )

        result = runner.invoke(app, ['--json', 'rate', 'status'])
        ep = json.loads(result.output)['sellers'][0]['tokens'][0]['endpoints'][0]
        assert ep['locked'] is False
        assert ep['remaining'] == 1

    def test_lock_visible_from_unrelated_token_shell(self, isolated_home, monkeypatch):
        """The original F-14 bug: a lock under one token must surface from
        a shell currently configured with a different token. R-3 makes this
        impossible by construction — read_all() ignores token gating.
        """
        db = isolated_home / '.wb-cli' / 'rate_limits.db'
        _seed_budget_row(
            db,
            token_fp='locked_token_fp1',
            endpoint='/adv/v3/fullstats',
            seller_id='seller-A',
            bucket_limit=3,
            remaining=0,
            reset_in_s=1800.0,
        )

        # Switch the env to a *different* token before invoking. Pre-R-3
        # this would have hidden the lock; R-3 surfaces it.
        unrelated_token = '.'.join([
            'eyJhbGciOiJIUzI1NiJ9',
            'eyJzaWQiOiJvdGhlci1zZWxsZXIiLCJpaWQiOjJ9',  # sid: other-seller
            'sig',
        ])
        monkeypatch.setenv('WB_API_TOKEN', unrelated_token)

        result = runner.invoke(app, ['--json', 'rate', 'status'])
        payload = json.loads(result.output)
        seller_ids = [s['seller_id'] for s in payload['sellers']]
        assert 'seller-A' in seller_ids
        ep = payload['sellers'][0]['tokens'][0]['endpoints'][0]
        assert ep['locked'] is True

    def test_grouping_by_seller_and_token(self, isolated_home):
        """Two tokens for the same seller appear under one seller block."""
        db = isolated_home / '.wb-cli' / 'rate_limits.db'
        _seed_budget_row(
            db, token_fp='token_A', endpoint='/adv/v3/fullstats',
            seller_id='seller-1', bucket_limit=3, remaining=2, reset_in_s=20.0,
        )
        _seed_budget_row(
            db, token_fp='token_B', endpoint='/api/v3/sales-funnel',
            seller_id='seller-1', bucket_limit=3, remaining=3, reset_in_s=10.0,
        )
        _seed_budget_row(
            db, token_fp='token_C', endpoint='/adv/v1/balance',
            seller_id='seller-2', bucket_limit=1, remaining=1, reset_in_s=5.0,
        )

        result = runner.invoke(app, ['--json', 'rate', 'status'])
        payload = json.loads(result.output)
        sellers_by_id = {s['seller_id']: s for s in payload['sellers']}
        assert set(sellers_by_id) == {'seller-1', 'seller-2'}
        assert len(sellers_by_id['seller-1']['tokens']) == 2
        assert len(sellers_by_id['seller-2']['tokens']) == 1

    def test_unknown_seller_id_falls_through(self, isolated_home):
        """Rows with NULL seller_id render as a separate group with seller_id=null."""
        db = isolated_home / '.wb-cli' / 'rate_limits.db'
        _seed_budget_row(
            db, token_fp='lonely', endpoint='/some/path',
            seller_id=None, bucket_limit=None, remaining=None, reset_in_s=0.0,
        )

        result = runner.invoke(app, ['--json', 'rate', 'status'])
        payload = json.loads(result.output)
        assert len(payload['sellers']) == 1
        assert payload['sellers'][0]['seller_id'] is None

    def test_table_output_contains_key_fields(self, isolated_home):
        """Table mode prints profile and one block per seller."""
        db = isolated_home / '.wb-cli' / 'rate_limits.db'
        _seed_budget_row(
            db, token_fp='aabbcc', endpoint='/adv/v3/fullstats',
            seller_id='seller-under-test', bucket_limit=3, remaining=0,
            reset_in_s=600.0,
        )

        result = runner.invoke(app, ['rate', 'status'])
        assert result.exit_code == 0
        assert 'Profile' in result.output
        assert 'seller-under-test' in result.output
        assert 'aabbcc' in result.output
        assert 'LOCKED' in result.output

    def test_table_output_clean_state(self, isolated_home):
        """Table mode with no rows tells the user nothing is recorded."""
        result = runner.invoke(app, ['rate', 'status'])
        assert result.exit_code == 0
        assert 'No rate-limit state recorded' in result.output

    def test_compact_json_is_single_line(self, isolated_home):
        """--compact produces single-line JSON."""
        result = runner.invoke(app, ['--json', '--compact', 'rate', 'status'])
        assert result.exit_code == 0
        assert '\n' not in result.output.strip()
        payload = json.loads(result.output)
        assert 'sellers' in payload

    def test_no_token_no_crash(self, tmp_path, monkeypatch):
        """Runs cleanly even when no token is available."""
        monkeypatch.setattr(Path, 'home', lambda: tmp_path)
        monkeypatch.delenv('WB_API_TOKEN', raising=False)
        monkeypatch.delenv('WB_ANALYTICS_TOKEN', raising=False)
        monkeypatch.chdir(tmp_path)
        ServiceContainer.reset()

        result = runner.invoke(app, ['--json', 'rate', 'status'])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload['sellers'] == []
        ServiceContainer.reset()


class TestRateProbeRemoved:
    """R-5 removed `wb rate probe` — verify it's gone."""

    def test_probe_subcommand_no_longer_registered(self, isolated_home):
        """`wb rate probe` should now exit with usage error (unknown command)."""
        result = runner.invoke(app, ['rate', 'probe'])
        assert result.exit_code != 0
        assert 'probe' in result.output.lower()  # error mentions the unknown name

    def test_rate_help_lists_only_status(self, isolated_home):
        """`wb rate --help` lists only the `status` subcommand."""
        result = runner.invoke(app, ['rate', '--help'])
        assert result.exit_code == 0
        assert 'status' in result.output
        assert 'probe' not in result.output


class TestRateStatusTokenType:
    """R-5: rate status surfaces token_type per token group."""

    def test_token_type_in_payload_for_known_profile(self, isolated_home, monkeypatch):
        """A token recorded for a known profile gets the persisted type."""
        from wb.auth.profiles import ProfileStore
        from wb.core.rate_limiter import compute_token_fingerprint

        monkeypatch.delenv('WB_API_TOKEN', raising=False)
        ServiceContainer.reset()
        store = ProfileStore(isolated_home / '.wb-cli')
        store.create_profile('default')
        store.save_token('default', 'promotion', TOKEN)
        store.set_token_type('default', 'personal')

        token_fp = compute_token_fingerprint(TOKEN)
        db = isolated_home / '.wb-cli' / 'rate_limits.db'
        _seed_budget_row(
            db, token_fp=token_fp, endpoint='/adv/v3/fullstats',
            seller_id='seller-under-test', bucket_limit=3, remaining=2,
            reset_in_s=20.0,
        )

        result = runner.invoke(app, ['--json', 'rate', 'status'])
        payload = json.loads(result.output)
        token = payload['sellers'][0]['tokens'][0]
        assert token['token_type'] == 'personal'

    def test_token_type_null_for_unknown_token(self, isolated_home):
        """A budget row whose fingerprint matches no profile carries token_type=null."""
        db = isolated_home / '.wb-cli' / 'rate_limits.db'
        _seed_budget_row(
            db, token_fp='unknown_fp', endpoint='/adv/v3/fullstats',
            seller_id='seller-x', bucket_limit=3, remaining=1,
            reset_in_s=15.0,
        )

        result = runner.invoke(app, ['--json', 'rate', 'status'])
        payload = json.loads(result.output)
        token = payload['sellers'][0]['tokens'][0]
        assert token['token_type'] is None
