"""Integration tests for Phase 2 batch read-only features.

Requires: WB_API_TOKEN in .env — skipped automatically otherwise.
All tests are read-only (no mutations).
"""

from __future__ import annotations

import json
import os

import pytest
from typer.testing import CliRunner

from wb.cli.app import app

runner = CliRunner(env=dict(os.environ))

# Real NM IDs from the seller account — used for analytics history tests.
# Obtained via: wb prices list (top 3 results as of 2026-04-06)
_NM1 = 69545467
_NM2 = 100510938
_NM3 = 100525085
_REAL_NMS_3 = f'{_NM1},{_NM2},{_NM3}'


class TestCampaignListLive:
    """Verify campaign list still works after batch-command refactor."""

    def test_campaign_list_json(self):
        result = runner.invoke(app, ['--json', 'campaign', 'list'])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_campaign_list_fields_filter(self):
        result = runner.invoke(
            app, ['--json', '--fields', 'campaign_id,name', 'campaign', 'list'],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        if data:
            assert 'campaign_id' in data[0]
            assert 'status' not in data[0]


class TestBidReadLive:
    """Verify bid commands work after client refactor."""

    def test_bid_recommended_requires_campaign(self):
        result = runner.invoke(app, ['--json', 'bid', 'recommend'])
        assert result.exit_code != 0

    def test_bid_set_items_dry_run_inline(self):
        """Inline --bids with --dry-run must not touch the API."""
        result = runner.invoke(app, [
            '--json', 'bid', 'set-items',
            '--campaign', '1',
            '--bids', f'[{{"nm_id": {_NM1}, "bid_kopecks": 500}}]',
            '--dry-run', '--yes',
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]['dry_run'] is True


class TestAnalyticsAutoChunkLive:
    """Verify analytics history auto-chunks >20 NM IDs without errors.

    The history endpoint has strict per-minute rate limits, so we keep
    API calls to a minimum.  All tests accept rate-limit errors (exit 5)
    but must never see a client-side ValidationError (exit 2).
    """

    # 21 entries built from the 3 real NMs (cycled) to avoid API 400s.
    _NMS_21 = ','.join(str([_NM1, _NM2, _NM3][i % 3]) for i in range(21))

    # The history endpoint only accepts a short recent window (~7 days).
    _FROM = '2026-03-30'
    _TO = '2026-04-05'

    def test_history_with_real_nms_returns_data(self):
        """3 real NM IDs should return exit 0 and a non-empty list."""
        result = runner.invoke(app, [
            '--json', 'analytics', 'sales-funnel', 'history',
            '--from', self._FROM, '--to', self._TO,
            '--nm-ids', _REAL_NMS_3,
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_history_with_21_nms_no_validation_error(self):
        """21 NM IDs must NOT raise a client-side ValidationError (exit 2).

        Confirms the old 'At most 20 nm_ids' limit is removed — chunking is
        now transparent.  May be rate-limited (exit 5) if run immediately
        after another analytics call.
        """
        result = runner.invoke(app, [
            '--json', 'analytics', 'sales-funnel', 'history',
            '--from', self._FROM, '--to', self._TO,
            '--nm-ids', self._NMS_21,
        ])
        # exit 2 = our old ValidationError for >20 NMs — must NEVER happen
        # exit 5 = WB rate limit — transient, acceptable
        assert result.exit_code != 2, result.output


class TestFieldsFilterLive:
    """Verify --fields output filtering works on real API responses."""

    def test_fields_filter_on_products(self):
        """--fields on products keeps only requested keys."""
        result = runner.invoke(app, [
            '--json', '--fields', 'nm_id,order_count',
            'analytics', 'sales-funnel', 'products',
            '--from', '2026-03-30', '--to', '2026-04-05',
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        if data:
            assert 'nm_id' in data[0]
            assert 'order_count' in data[0]
            assert 'open_count' not in data[0]

    def test_fields_filter_on_campaign_list(self):
        """--fields on campaign list keeps only requested keys."""
        result = runner.invoke(app, [
            '--json', '--fields', 'campaign_id',
            'campaign', 'list',
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        if data:
            assert 'campaign_id' in data[0]
            assert 'name' not in data[0]


class TestMultiCampaignDryRunLive:
    """Verify --ids dry-run with real API token works end-to-end."""

    def test_campaign_start_dry_run_ids(self):
        result = runner.invoke(app, [
            '--json', 'campaign', 'start',
            '--ids', '1,2,3',
            '--dry-run', '--yes',
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 3
        assert all(r['dry_run'] for r in data)


class TestStatsByStatusLive:
    """Verify wb stats campaigns --status works end-to-end with a real API token.

    EP_CAMPAIGN_FULLSTATS has a 1/20s rate limit. Run this class in isolation
    or space it >=20s from other fullstats calls.
    """

    _FROM = '2026-04-14'
    _TO = '2026-04-21'

    def test_status_running_exit_0(self):
        result = runner.invoke(app, [
            '--json', 'stats', 'campaigns',
            '--status', 'running',
            '--from', self._FROM, '--to', self._TO,
        ])
        assert result.exit_code == 0, result.output

    def test_status_running_returns_list(self):
        result = runner.invoke(app, [
            '--json', 'stats', 'campaigns',
            '--status', 'running',
            '--from', self._FROM, '--to', self._TO,
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_status_running_fields_present(self):
        result = runner.invoke(app, [
            '--json', 'stats', 'campaigns',
            '--status', 'running',
            '--from', self._FROM, '--to', self._TO,
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        if data:
            assert 'campaign_id' in data[0]
            assert 'views' in data[0]
            assert 'clicks' in data[0]
            assert 'ctr' in data[0]

    def test_status_active_exit_0(self):
        result = runner.invoke(app, [
            '--json', 'stats', 'campaigns',
            '--status', 'active',
            '--from', self._FROM, '--to', self._TO,
        ])
        assert result.exit_code == 0, result.output

    def test_ids_and_status_mutually_exclusive(self):
        result = runner.invoke(app, [
            '--json', 'stats', 'campaigns',
            '--ids', '1,2',
            '--status', 'running',
            '--from', self._FROM, '--to', self._TO,
        ])
        assert result.exit_code == 2, result.output

    def test_neither_ids_nor_status_fails(self):
        result = runner.invoke(app, [
            '--json', 'stats', 'campaigns',
            '--from', self._FROM, '--to', self._TO,
        ])
        assert result.exit_code == 2, result.output
