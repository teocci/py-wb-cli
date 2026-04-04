"""Tests for wb.storage.cache — CacheStore SQLite operations."""

from __future__ import annotations

from pathlib import Path

import pytest

from wb.domain.cache_models import (
    BudgetEvent,
    CampaignSnapshot,
    ClusterRecord,
    StatsRecord,
)
from wb.storage.cache import CacheStore


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture()
def store(tmp_path: Path) -> CacheStore:
    """CacheStore backed by a temporary file."""
    return CacheStore(tmp_path / 'test_cache.db')


def _campaign_snap(
        campaign_id: int = 111,
        profile: str = 'test',
        name: str = 'Test Camp',
) -> CampaignSnapshot:
    return CampaignSnapshot(
        campaign_id=campaign_id,
        profile=profile,
        snapshot_time='2026-04-01T12:00:00+00:00',
        name=name,
        status=9,
        campaign_type=9,
        daily_budget=10000,
        payload_json='{}',
    )


def _stats_rec(
        campaign_id: int = 111,
        profile: str = 'test',
        date: str = '2026-04-01',
) -> StatsRecord:
    return StatsRecord(
        campaign_id=campaign_id,
        profile=profile,
        date=date,
        views=1000,
        clicks=50,
        ctr=5.0,
        spend=25000,
        orders=10,
        payload_json='{}',
    )


def _cluster_rec(
        campaign_id: int = 111,
        nm_id: int = 999,
        norm_query: str = 'test shoes',
        profile: str = 'test',
) -> ClusterRecord:
    return ClusterRecord(
        campaign_id=campaign_id,
        nm_id=nm_id,
        norm_query=norm_query,
        profile=profile,
        snapshot_time='2026-04-01T12:00:00+00:00',
        bid=500,
    )


def _budget_evt(
        profile: str = 'test',
        campaign_id: int = 111,
        amount: int = 5000,
) -> BudgetEvent:
    return BudgetEvent(
        profile=profile,
        campaign_id=campaign_id,
        event_type='topup',
        amount=amount,
        balance_after=0,
        created_at='2026-04-01T12:00:00+00:00',
        payload_json='{}',
    )


# ── Schema ────────────────────────────────────────────────────────────

class TestSchema:
    """Schema initialisation tests."""

    def test_db_file_created(self, tmp_path: Path) -> None:
        """CacheStore creates the db file on init."""
        db = tmp_path / 'sub' / 'cache.db'
        CacheStore(db)
        assert db.exists()

    def test_schema_version_set(self, tmp_path: Path) -> None:
        """PRAGMA user_version is set to 2 after init."""
        import sqlite3
        db = tmp_path / 'cache.db'
        CacheStore(db)
        conn = sqlite3.connect(db)
        version = conn.execute('PRAGMA user_version').fetchone()[0]
        conn.close()
        assert version == 2

    def test_reinit_idempotent(self, tmp_path: Path) -> None:
        """Creating two CacheStore instances on the same file is safe."""
        db = tmp_path / 'cache.db'
        CacheStore(db)
        CacheStore(db)  # should not raise


# ── Campaign snapshots ────────────────────────────────────────────────

class TestCampaignSnapshots:
    """Tests for campaign save/list operations."""

    def test_save_returns_row_id(self, store: CacheStore) -> None:
        row_id = store.save_campaign(_campaign_snap())
        assert row_id >= 1

    def test_round_trip(self, store: CacheStore) -> None:
        snap = _campaign_snap(campaign_id=42, name='Shoes')
        store.save_campaign(snap)
        results = store.list_campaigns('test', campaign_id=42)
        assert len(results) == 1
        assert results[0].campaign_id == 42
        assert results[0].name == 'Shoes'

    def test_filter_by_profile(self, store: CacheStore) -> None:
        store.save_campaign(_campaign_snap(profile='p1'))
        store.save_campaign(_campaign_snap(profile='p2'))
        r1 = store.list_campaigns('p1')
        r2 = store.list_campaigns('p2')
        assert len(r1) == 1 and len(r2) == 1

    def test_filter_by_campaign_id(self, store: CacheStore) -> None:
        store.save_campaign(_campaign_snap(campaign_id=1))
        store.save_campaign(_campaign_snap(campaign_id=2))
        results = store.list_campaigns('test', campaign_id=1)
        assert len(results) == 1
        assert results[0].campaign_id == 1

    def test_limit_respected(self, store: CacheStore) -> None:
        for _ in range(5):
            store.save_campaign(_campaign_snap())
        results = store.list_campaigns('test', limit=3)
        assert len(results) == 3

    def test_ordered_desc(self, store: CacheStore) -> None:
        snap_a = CampaignSnapshot(
            campaign_id=1, profile='test', snapshot_time='2026-01-01T00:00:00+00:00',
            name='A', status=9, campaign_type=9, daily_budget=0, payload_json='{}',
        )
        snap_b = CampaignSnapshot(
            campaign_id=1, profile='test', snapshot_time='2026-03-01T00:00:00+00:00',
            name='B', status=9, campaign_type=9, daily_budget=0, payload_json='{}',
        )
        store.save_campaign(snap_a)
        store.save_campaign(snap_b)
        results = store.list_campaigns('test', campaign_id=1)
        assert results[0].name == 'B'  # most recent first


# ── Stats records ─────────────────────────────────────────────────────

class TestStatsRecords:
    """Tests for stats save/list/upsert operations."""

    def test_save_returns_row_id(self, store: CacheStore) -> None:
        assert store.save_stats(_stats_rec()) >= 1

    def test_round_trip(self, store: CacheStore) -> None:
        store.save_stats(_stats_rec(campaign_id=5, date='2026-04-01'))
        results = store.list_stats('test', 5)
        assert len(results) == 1
        assert results[0].date == '2026-04-01'
        assert results[0].views == 1000

    def test_upsert_same_date(self, store: CacheStore) -> None:
        """Same campaign/profile/date replaces the existing row."""
        store.save_stats(_stats_rec(campaign_id=5, date='2026-04-01'))
        updated = StatsRecord(
            campaign_id=5, profile='test', date='2026-04-01',
            views=9999, clicks=100, ctr=1.0, spend=0, orders=0, payload_json='{}',
        )
        store.save_stats(updated)
        results = store.list_stats('test', 5)
        assert len(results) == 1
        assert results[0].views == 9999

    def test_filter_date_range(self, store: CacheStore) -> None:
        for day in ['2026-01-01', '2026-02-01', '2026-03-01']:
            store.save_stats(_stats_rec(campaign_id=7, date=day))
        results = store.list_stats(
            'test', 7, date_from='2026-01-15', date_to='2026-02-28',
        )
        assert len(results) == 1
        assert results[0].date == '2026-02-01'

    def test_ordered_asc(self, store: CacheStore) -> None:
        store.save_stats(_stats_rec(date='2026-03-01'))
        store.save_stats(_stats_rec(date='2026-01-01'))
        results = store.list_stats('test', 111)
        assert results[0].date == '2026-01-01'


# ── Cluster records ───────────────────────────────────────────────────

class TestClusterRecords:
    """Tests for cluster save/list operations."""

    def test_save_returns_row_id(self, store: CacheStore) -> None:
        assert store.save_cluster(_cluster_rec()) >= 1

    def test_round_trip(self, store: CacheStore) -> None:
        store.save_cluster(_cluster_rec(nm_id=77, norm_query='red shoes'))
        results = store.list_clusters('test', 111, nm_id=77)
        assert len(results) == 1
        assert results[0].norm_query == 'red shoes'
        assert results[0].bid == 500

    def test_filter_by_nm_id(self, store: CacheStore) -> None:
        store.save_cluster(_cluster_rec(nm_id=1))
        store.save_cluster(_cluster_rec(nm_id=2))
        results = store.list_clusters('test', 111, nm_id=1)
        assert len(results) == 1
        assert results[0].nm_id == 1

    def test_no_nm_filter_returns_all(self, store: CacheStore) -> None:
        store.save_cluster(_cluster_rec(nm_id=1))
        store.save_cluster(_cluster_rec(nm_id=2))
        results = store.list_clusters('test', 111)
        assert len(results) == 2


# ── Budget events ─────────────────────────────────────────────────────

class TestBudgetEvents:
    """Tests for budget event save/list operations."""

    def test_save_returns_row_id(self, store: CacheStore) -> None:
        assert store.save_budget_event(_budget_evt()) >= 1

    def test_round_trip(self, store: CacheStore) -> None:
        store.save_budget_event(_budget_evt(amount=9999))
        results = store.list_budget_events('test')
        assert len(results) == 1
        assert results[0].amount == 9999
        assert results[0].event_type == 'topup'

    def test_filter_by_campaign(self, store: CacheStore) -> None:
        store.save_budget_event(_budget_evt(campaign_id=1))
        store.save_budget_event(_budget_evt(campaign_id=2))
        results = store.list_budget_events('test', campaign_id=1)
        assert len(results) == 1
        assert results[0].campaign_id == 1

    def test_filter_by_profile(self, store: CacheStore) -> None:
        store.save_budget_event(_budget_evt(profile='a'))
        store.save_budget_event(_budget_evt(profile='b'))
        assert len(store.list_budget_events('a')) == 1
        assert len(store.list_budget_events('b')) == 1

    def test_ordered_desc(self, store: CacheStore) -> None:
        e1 = BudgetEvent(
            profile='test', campaign_id=1, event_type='topup',
            amount=100, balance_after=0, created_at='2026-01-01T00:00:00+00:00',
            payload_json='{}',
        )
        e2 = BudgetEvent(
            profile='test', campaign_id=1, event_type='topup',
            amount=200, balance_after=0, created_at='2026-03-01T00:00:00+00:00',
            payload_json='{}',
        )
        store.save_budget_event(e1)
        store.save_budget_event(e2)
        results = store.list_budget_events('test')
        assert results[0].amount == 200  # most recent first


# ── Maintenance ───────────────────────────────────────────────────────

class TestMaintenance:
    """Tests for clear() and summary()."""

    def test_summary_empty(self, store: CacheStore) -> None:
        counts = store.summary('nobody')
        assert all(v == 0 for v in counts.values())

    def test_summary_after_inserts(self, store: CacheStore) -> None:
        store.save_campaign(_campaign_snap())
        store.save_stats(_stats_rec())
        store.save_cluster(_cluster_rec())
        store.save_budget_event(_budget_evt())
        counts = store.summary('test')
        assert counts['campaigns'] == 1
        assert counts['campaign_stats'] == 1
        assert counts['cluster_snapshots'] == 1
        assert counts['budget_events'] == 1

    def test_clear_all(self, store: CacheStore) -> None:
        store.save_campaign(_campaign_snap())
        store.save_stats(_stats_rec())
        store.clear('test')
        assert store.summary('test') == {
            'campaigns': 0,
            'campaign_stats': 0,
            'cluster_snapshots': 0,
            'budget_events': 0,
        }

    def test_clear_by_campaign(self, store: CacheStore) -> None:
        store.save_campaign(_campaign_snap(campaign_id=1))
        store.save_campaign(_campaign_snap(campaign_id=2))
        store.clear('test', campaign_id=1)
        remaining = store.list_campaigns('test')
        assert len(remaining) == 1
        assert remaining[0].campaign_id == 2

    def test_clear_returns_counts(self, store: CacheStore) -> None:
        store.save_campaign(_campaign_snap())
        store.save_stats(_stats_rec())
        counts = store.clear('test')
        assert counts['campaigns'] == 1
        assert counts['campaign_stats'] == 1
