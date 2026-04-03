"""Tests for wb.services.cache — CacheService."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wb.domain.cache_models import BudgetEvent, CampaignSnapshot, ClusterRecord, StatsRecord
from wb.domain.enums import CampaignStatus, CampaignType, PaymentType
from wb.domain.models import Campaign, CampaignStats, SearchCluster
from wb.services.cache import CacheService
from wb.storage.cache import CacheStore


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture()
def store(tmp_path: Path) -> CacheStore:
    return CacheStore(tmp_path / 'cache.db')


def _mock_campaign(campaign_id: int = 111) -> Campaign:
    return Campaign(
        campaign_id=campaign_id,
        name='Test Campaign',
        status=CampaignStatus.RUNNING,
        campaign_type=CampaignType.AUTO,
        payment_type=PaymentType.CPM,
        daily_budget=10000,
    )


def _mock_stats(campaign_id: int = 111) -> CampaignStats:
    return CampaignStats(
        campaign_id=campaign_id,
        views=500,
        clicks=25,
        ctr=5.0,
        orders=5,
        spend=12500.0,
    )


def _mock_cluster(norm_query: str = 'blue jeans') -> SearchCluster:
    return SearchCluster(norm_query=norm_query, bid=300, nm_id=999)


def _make_svc(store: CacheStore, campaign=None, stats=None, clusters=None) -> CacheService:
    campaign_svc = MagicMock()
    campaign_svc.get_campaign.return_value = campaign or _mock_campaign()
    campaign_svc.list_campaigns.return_value = [_mock_campaign()]

    stats_svc = MagicMock()
    stats_svc.get_campaign_stats.return_value = stats or _mock_stats()

    cluster_svc = MagicMock()
    cluster_svc.list_clusters.return_value = clusters or [_mock_cluster()]

    return CacheService(
        store=store,
        campaign_svc=campaign_svc,
        stats_svc=stats_svc,
        cluster_svc=cluster_svc,
    )


# ── snapshot_campaign ─────────────────────────────────────────────────

class TestSnapshotCampaign:

    def test_stores_campaign(self, store: CacheStore) -> None:
        svc = _make_svc(store)
        counts = svc.snapshot_campaign(111, 'test')
        assert counts['campaigns'] == 1
        snaps = store.list_campaigns('test', 111)
        assert len(snaps) == 1
        assert snaps[0].name == 'Test Campaign'

    def test_stores_stats_by_default(self, store: CacheStore) -> None:
        svc = _make_svc(store)
        counts = svc.snapshot_campaign(111, 'test')
        assert counts['stats'] == 1
        recs = store.list_stats('test', 111)
        assert len(recs) == 1
        assert recs[0].views == 500

    def test_skip_stats_when_disabled(self, store: CacheStore) -> None:
        svc = _make_svc(store)
        counts = svc.snapshot_campaign(111, 'test', with_stats=False)
        assert counts['stats'] == 0
        assert store.list_stats('test', 111) == []

    def test_stores_clusters_when_nm_given(self, store: CacheStore) -> None:
        svc = _make_svc(store, clusters=[_mock_cluster('sneakers')])
        counts = svc.snapshot_campaign(111, 'test', nm_id=999)
        assert counts['clusters'] == 1
        recs = store.list_clusters('test', 111)
        assert recs[0].norm_query == 'sneakers'

    def test_no_clusters_without_nm_id(self, store: CacheStore) -> None:
        svc = _make_svc(store)
        counts = svc.snapshot_campaign(111, 'test', nm_id=None)
        assert counts['clusters'] == 0

    def test_skip_clusters_when_disabled(self, store: CacheStore) -> None:
        svc = _make_svc(store)
        counts = svc.snapshot_campaign(111, 'test', nm_id=999, with_clusters=False)
        assert counts['clusters'] == 0

    def test_stats_error_is_swallowed(self, store: CacheStore) -> None:
        """Stats fetch failure should not abort the snapshot."""
        svc = _make_svc(store)
        svc._stats_svc.get_campaign_stats.side_effect = RuntimeError('boom')
        counts = svc.snapshot_campaign(111, 'test')
        assert counts['campaigns'] == 1
        assert counts['stats'] == 0

    def test_cluster_error_is_swallowed(self, store: CacheStore) -> None:
        svc = _make_svc(store)
        svc._cluster_svc.list_clusters.side_effect = RuntimeError('boom')
        counts = svc.snapshot_campaign(111, 'test', nm_id=999)
        assert counts['campaigns'] == 1
        assert counts['clusters'] == 0


# ── snapshot_all ──────────────────────────────────────────────────────

class TestSnapshotAll:

    def test_snapshots_active_campaigns(self, store: CacheStore) -> None:
        svc = _make_svc(store)
        counts = svc.snapshot_all('test')
        assert counts['campaigns'] == 1

    def test_skips_inactive_campaigns(self, store: CacheStore) -> None:
        inactive = Campaign(
            campaign_id=99,
            name='Paused',
            status=CampaignStatus.PAUSED,  # type: ignore[arg-type]
            campaign_type=CampaignType.AUTO,
            payment_type=PaymentType.CPM,
        )
        svc = _make_svc(store)
        svc._campaign_svc.list_campaigns.return_value = [inactive]
        counts = svc.snapshot_all('test')
        assert counts['campaigns'] == 0


# ── History queries ───────────────────────────────────────────────────

class TestHistoryQueries:

    def test_history_campaigns_delegates(self, store: CacheStore) -> None:
        svc = _make_svc(store)
        store.save_campaign(CampaignSnapshot(
            campaign_id=111, profile='test',
            snapshot_time='2026-04-01T00:00:00+00:00',
            name='X', status=9, campaign_type=9, daily_budget=0, payload_json='{}',
        ))
        results = svc.history_campaigns('test')
        assert len(results) == 1

    def test_history_stats_delegates(self, store: CacheStore) -> None:
        svc = _make_svc(store)
        store.save_stats(StatsRecord(
            campaign_id=1, profile='test', date='2026-04-01',
            views=100, clicks=5, ctr=5.0, spend=0, orders=0, payload_json='{}',
        ))
        results = svc.history_stats('test', 1)
        assert len(results) == 1

    def test_history_clusters_delegates(self, store: CacheStore) -> None:
        svc = _make_svc(store)
        store.save_cluster(ClusterRecord(
            campaign_id=1, nm_id=99, norm_query='q', profile='test',
            snapshot_time='2026-04-01T00:00:00+00:00', bid=100,
        ))
        results = svc.history_clusters('test', 1)
        assert len(results) == 1

    def test_history_budget_delegates(self, store: CacheStore) -> None:
        svc = _make_svc(store)
        store.save_budget_event(BudgetEvent(
            profile='test', campaign_id=1, event_type='topup',
            amount=500, balance_after=0,
            created_at='2026-04-01T00:00:00+00:00', payload_json='{}',
        ))
        results = svc.history_budget('test')
        assert len(results) == 1

    def test_clear_delegates(self, store: CacheStore) -> None:
        store.save_campaign(CampaignSnapshot(
            campaign_id=1, profile='test',
            snapshot_time='2026-04-01T00:00:00+00:00',
            name='X', status=9, campaign_type=9, daily_budget=0, payload_json='{}',
        ))
        svc = _make_svc(store)
        counts = svc.clear('test')
        assert counts['campaigns'] == 1
        assert store.list_campaigns('test') == []

    def test_summary_delegates(self, store: CacheStore) -> None:
        svc = _make_svc(store)
        totals = svc.summary('test')
        assert 'campaigns' in totals
