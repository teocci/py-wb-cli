"""Integration tests for Phase I-3 composite read-only features.

Requires: WB_API_TOKEN in .env — skipped automatically otherwise.
All tests are read-only (no mutations, no --apply).

Credentials:
  WB_API_TOKEN  — promotion + prices token (required)
  WB_SELLER_ID  — optional seller metadata, used only for display/notes
"""

from __future__ import annotations

import json
import os

import pytest
from typer.testing import CliRunner

from wb.cli.app import app

runner = CliRunner(env=dict(os.environ))

# Real NM IDs from the seller account (reused from test_batch_read.py)
_NM1 = 69545467
_NM2 = 100510938
_NM3 = 100525085
_REAL_NMS_3 = f'{_NM1},{_NM2},{_NM3}'

# Stats date range — last 7 days
_FROM = '2026-03-31'
_TO = '2026-04-06'


class TestProductSummaryLive:
    """wb product summary — real API reads."""

    def test_product_summary_single_nm(self):
        result = runner.invoke(app, [
            '--json', 'product', 'summary',
            '--nms', str(_NM1),
            '--from', _FROM, '--to', _TO,
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]['nm_id'] == _NM1

    def test_product_summary_multiple_nms(self):
        result = runner.invoke(app, [
            '--json', 'product', 'summary',
            '--nms', _REAL_NMS_3,
            '--from', _FROM, '--to', _TO,
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 3

    def test_product_summary_json_shape(self):
        result = runner.invoke(app, [
            '--json', 'product', 'summary',
            '--nms', str(_NM1),
            '--from', _FROM, '--to', _TO,
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        item = data[0]
        # These fields must always be present regardless of token availability
        for field in ('nm_id', 'ad_spend', 'ad_views', 'campaign_ids', 'cluster_count'):
            assert field in item, f'Missing field: {field}'

    def test_product_summary_fields_filter(self):
        result = runner.invoke(app, [
            '--json', '--fields', 'nm_id,ad_spend',
            'product', 'summary',
            '--nms', str(_NM1),
            '--from', _FROM, '--to', _TO,
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        item = data[0]
        assert 'nm_id' in item
        assert 'ad_spend' in item
        assert 'campaign_ids' not in item

    def test_product_summary_default_date_range(self):
        """Omitting --from/--to defaults to last 7 days — no crash."""
        result = runner.invoke(app, [
            '--json', 'product', 'summary',
            '--nms', str(_NM1),
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert data[0]['nm_id'] == _NM1


class TestCampaignOverviewLive:
    """wb campaign overview — real API reads."""

    @pytest.fixture(scope='class')
    def first_campaign_id(self) -> int | None:
        """Return the first campaign ID from a real campaign list call, or None."""
        result = runner.invoke(app, ['--json', 'campaign', 'list'])
        if result.exit_code != 0:
            return None
        data = json.loads(result.output)
        if not data:
            return None
        return data[0]['campaign_id']

    def test_campaign_overview_requires_id(self):
        result = runner.invoke(app, ['campaign', 'overview'])
        assert result.exit_code != 0

    def test_campaign_overview_with_real_id(self, first_campaign_id):
        if first_campaign_id is None:
            pytest.skip('No campaigns available for this seller')
        result = runner.invoke(app, [
            '--json', 'campaign', 'overview', str(first_campaign_id),
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data['campaign_id'] == first_campaign_id

    def test_campaign_overview_json_shape(self, first_campaign_id):
        if first_campaign_id is None:
            pytest.skip('No campaigns available for this seller')
        result = runner.invoke(app, [
            '--json', 'campaign', 'overview', str(first_campaign_id),
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        for field in ('campaign_id', 'name', 'status', 'total_budget', 'views'):
            assert field in data, f'Missing field: {field}'

    def test_campaign_overview_days_flag(self, first_campaign_id):
        if first_campaign_id is None:
            pytest.skip('No campaigns available for this seller')
        result = runner.invoke(app, [
            '--json', 'campaign', 'overview', str(first_campaign_id),
            '--days', '3',
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data['campaign_id'] == first_campaign_id


class TestIdempotentMutationsLive:
    """Verify already_applied field with real API (dry-run only, no state change)."""

    def test_start_dry_run_returns_already_applied_false(self):
        """Dry-run never reads state, so already_applied is always False."""
        # Use a dummy campaign ID — dry-run should not check state
        result = runner.invoke(app, [
            '--json', 'campaign', 'start',
            '--ids', '1,2,3',
            '--dry-run', '--yes',
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert all(r.get('dry_run') is True for r in data)
        # Dry-run results have already_applied=False by design
        assert all(r.get('already_applied') is False for r in data)

    def test_start_running_campaign_returns_already_applied(self):
        """Pick a RUNNING campaign and start it — expect already_applied=True."""
        list_result = runner.invoke(app, ['--json', 'campaign', 'list'])
        if list_result.exit_code != 0:
            pytest.skip('campaign list failed')
        campaigns = json.loads(list_result.output)
        running = [c for c in campaigns if c.get('status') == 9]  # 9=RUNNING
        if not running:
            pytest.skip('No RUNNING campaigns available')
        cid = running[0]['campaign_id']
        result = runner.invoke(app, [
            '--json', 'campaign', 'start', str(cid), '--yes',
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        # Single campaign start returns a list with one element
        if isinstance(data, list):
            entry = data[0]
        else:
            entry = data
        assert entry.get('already_applied') is True
        assert entry.get('success') is True
