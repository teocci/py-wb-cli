"""Tests for report caching — CacheStore.report_cache + ReportsService cache logic."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wb.core.constants import REPORT_CACHE_TTL_HOURS
from wb.domain.cache_models import ReportCacheEntry
from wb.domain.report_models import (
    SaleRecord,
    WarehouseRemainItem,
    WarehouseStock,
)
from wb.services.reports import (
    ReportsService,
    _load_sale_records,
    _load_stock_items,
    _sale_record_from_dict,
    _stock_item_from_dict,
)
from wb.storage.cache import CacheStore


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def db(tmp_path):
    """In-memory (tmp) CacheStore."""
    return CacheStore(tmp_path / 'cache.db')


@pytest.fixture()
def reports_dir(tmp_path):
    """Temporary directory for cached report files."""
    d = tmp_path / 'reports'
    d.mkdir()
    return d


@pytest.fixture()
def mock_client():
    return MagicMock()


@pytest.fixture()
def svc(mock_client, db, reports_dir):
    """ReportsService with cache enabled."""
    return ReportsService(
        mock_client,
        reports_dir=reports_dir,
        cache_store=db,
        profile_name='test_profile',
    )


@pytest.fixture()
def svc_no_cache(mock_client):
    """ReportsService with no cache configured."""
    return ReportsService(mock_client)


# ── ReportCacheEntry round-trip ───────────────────────────────────────


class TestReportCacheStore:
    """Tests for CacheStore report_cache table."""

    def test_save_and_get(self, db, tmp_path):
        entry = ReportCacheEntry(
            profile_name='alice',
            seller_id=None,
            report_type='warehouse_remains',
            date='2026-04-04',
            payload_path=str(tmp_path / 'f.json'),
            computed_at='2026-04-04T10:00:00',
        )
        db.save_report_cache(entry)
        result = db.get_report_cache('alice', 'warehouse_remains', '2026-04-04')
        assert result is not None
        assert result.profile_name == 'alice'
        assert result.report_type == 'warehouse_remains'
        assert result.date == '2026-04-04'
        assert result.payload_path == str(tmp_path / 'f.json')
        assert result.computed_at == '2026-04-04T10:00:00'

    def test_get_miss_returns_none(self, db):
        result = db.get_report_cache('nobody', 'warehouse_remains', '2026-01-01')
        assert result is None

    def test_upsert_replaces_existing(self, db, tmp_path):
        entry1 = ReportCacheEntry(
            profile_name='bob',
            seller_id=None,
            report_type='warehouse_remains',
            date='2026-04-04',
            payload_path=str(tmp_path / 'old.json'),
            computed_at='2026-04-04T09:00:00',
        )
        entry2 = ReportCacheEntry(
            profile_name='bob',
            seller_id=None,
            report_type='warehouse_remains',
            date='2026-04-04',
            payload_path=str(tmp_path / 'new.json'),
            computed_at='2026-04-04T10:00:00',
        )
        db.save_report_cache(entry1)
        db.save_report_cache(entry2)
        result = db.get_report_cache('bob', 'warehouse_remains', '2026-04-04')
        assert result is not None
        assert result.payload_path == str(tmp_path / 'new.json')
        assert result.computed_at == '2026-04-04T10:00:00'

    def test_list_returns_entries_desc(self, db, tmp_path):
        for i in range(3):
            db.save_report_cache(ReportCacheEntry(
                profile_name='carol',
                seller_id=None,
                report_type=f'type_{i}',
                date='2026-04-04',
                payload_path=str(tmp_path / f'f{i}.json'),
                computed_at=f'2026-04-04T0{i}:00:00',
            ))
        entries = db.list_report_cache('carol')
        assert len(entries) == 3
        # ordered by computed_at desc
        assert entries[0].computed_at > entries[1].computed_at

    def test_multi_profile_isolation(self, db, tmp_path):
        for name in ('alice', 'bob'):
            db.save_report_cache(ReportCacheEntry(
                profile_name=name,
                seller_id=None,
                report_type='warehouse_remains',
                date='2026-04-04',
                payload_path=str(tmp_path / f'{name}.json'),
                computed_at='2026-04-04T10:00:00',
            ))
        alice_entries = db.list_report_cache('alice')
        bob_entries = db.list_report_cache('bob')
        assert len(alice_entries) == 1
        assert len(bob_entries) == 1
        assert alice_entries[0].profile_name == 'alice'
        assert bob_entries[0].profile_name == 'bob'

    def test_seller_id_stored(self, db, tmp_path):
        entry = ReportCacheEntry(
            profile_name='dave',
            seller_id='seller_42',
            report_type='warehouse_remains',
            date='2026-04-04',
            payload_path=str(tmp_path / 'f.json'),
            computed_at='2026-04-04T10:00:00',
        )
        db.save_report_cache(entry)
        result = db.get_report_cache('dave', 'warehouse_remains', '2026-04-04')
        assert result is not None
        assert result.seller_id == 'seller_42'


# ── Deserialisation helpers ───────────────────────────────────────────


class TestDeserialisation:
    """Tests for cache-format deserialisation helpers."""

    def test_stock_item_from_dict_roundtrip(self):
        from dataclasses import asdict
        item = WarehouseRemainItem(
            brand='Nike',
            subject_name='Shoes',
            vendor_code='NK-001',
            nm_id=12345,
            barcode='1234567890',
            tech_size='42',
            volume=2.5,
            warehouses=[WarehouseStock('WH-A', 50)],
        )
        d = asdict(item)
        restored = _stock_item_from_dict(d)
        assert restored.nm_id == 12345
        assert restored.brand == 'Nike'
        assert restored.warehouses[0].warehouse_name == 'WH-A'
        assert restored.warehouses[0].quantity == 50

    def test_sale_record_from_dict_roundtrip(self):
        from dataclasses import asdict
        rec = SaleRecord(nm_id=99, date='2026-04-01', quantity=5)
        d = asdict(rec)
        restored = _sale_record_from_dict(d)
        assert restored.nm_id == 99
        assert restored.date == '2026-04-01'
        assert restored.quantity == 5

    def test_load_stock_items(self, tmp_path):
        from dataclasses import asdict
        items = [
            WarehouseRemainItem(
                brand='X', subject_name='Y', vendor_code='Z',
                nm_id=7, barcode='', tech_size='', volume=0.0,
                warehouses=[WarehouseStock('WH', 10)],
            ),
        ]
        path = tmp_path / 'stock.json'
        path.write_text(json.dumps([asdict(i) for i in items]))
        loaded = _load_stock_items(path)
        assert len(loaded) == 1
        assert loaded[0].nm_id == 7

    def test_load_sale_records(self, tmp_path):
        from dataclasses import asdict
        recs = [SaleRecord(nm_id=1, date='2026-04-01', quantity=3)]
        path = tmp_path / 'sales.json'
        path.write_text(json.dumps([asdict(r) for r in recs]))
        loaded = _load_sale_records(path)
        assert len(loaded) == 1
        assert loaded[0].nm_id == 1


# ── _cache_hit TTL logic ──────────────────────────────────────────────


class TestCacheHitTTL:
    """Tests for ReportsService._cache_hit TTL behaviour."""

    def _make_entry(self, db, reports_dir, computed_at: str) -> Path:
        path = reports_dir / 'warehouse_remains_2026-04-04.json'
        path.write_text('[]')
        db.save_report_cache(ReportCacheEntry(
            profile_name='test_profile',
            seller_id=None,
            report_type='warehouse_remains',
            date='2026-04-04',
            payload_path=str(path),
            computed_at=computed_at,
        ))
        return path

    def test_hit_within_ttl(self, svc, db, reports_dir):
        recent = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
        self._make_entry(db, reports_dir, recent)
        path, hit = svc._cache_hit('warehouse_remains', '2026-04-04')
        assert hit is True
        assert path is not None

    def test_miss_expired_ttl(self, svc, db, reports_dir):
        old_ts = (
            datetime.now(timezone.utc) - timedelta(hours=REPORT_CACHE_TTL_HOURS + 1)
        ).strftime('%Y-%m-%dT%H:%M:%S')
        self._make_entry(db, reports_dir, old_ts)
        path, hit = svc._cache_hit('warehouse_remains', '2026-04-04')
        assert hit is False
        assert path is None

    def test_miss_no_entry(self, svc):
        path, hit = svc._cache_hit('warehouse_remains', '1999-01-01')
        assert hit is False
        assert path is None

    def test_miss_file_deleted(self, svc, db, reports_dir):
        recent = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
        path = self._make_entry(db, reports_dir, recent)
        path.unlink()
        _, hit = svc._cache_hit('warehouse_remains', '2026-04-04')
        assert hit is False


# ── get_warehouse_top with cache ─────────────────────────────────────


class TestGetWarehouseTopCached:
    """Tests for get_warehouse_top cache integration."""

    def _setup_api(self, mock_client):
        mock_client.create_warehouse_remains.return_value = {'data': {'taskId': 't1'}}
        mock_client.get_warehouse_remains_status.return_value = {
            'data': {'id': 't1', 'status': 'done'},
        }
        mock_client.download_warehouse_remains.return_value = [
            {
                'nmId': 100, 'brand': 'B', 'subjectName': 'S',
                'vendorCode': 'V', 'barcode': '', 'techSize': '', 'volume': 0.0,
                'warehouses': [{'warehouseName': 'WH', 'quantity': 10}],
            },
        ]

    @patch('wb.services.reports.time.sleep')
    def test_first_call_hits_api_from_cache_false(self, mock_sleep, svc, mock_client):
        self._setup_api(mock_client)
        _, from_cache = svc.get_warehouse_top(limit=1)
        assert from_cache is False
        mock_client.create_warehouse_remains.assert_called_once()

    @patch('wb.services.reports.time.sleep')
    def test_second_call_returns_from_cache(self, mock_sleep, svc, mock_client):
        self._setup_api(mock_client)
        svc.get_warehouse_top(limit=1)
        _, from_cache = svc.get_warehouse_top(limit=1)
        assert from_cache is True
        # API called only once total
        assert mock_client.create_warehouse_remains.call_count == 1

    @patch('wb.services.reports.time.sleep')
    def test_no_cache_flag_always_hits_api(self, mock_sleep, svc, mock_client):
        self._setup_api(mock_client)
        svc.get_warehouse_top(limit=1)
        _, from_cache = svc.get_warehouse_top(limit=1, use_cache=False)
        assert from_cache is False
        assert mock_client.create_warehouse_remains.call_count == 2

    @patch('wb.services.reports.time.sleep')
    def test_no_cache_configured_returns_api_result(
            self, mock_sleep, svc_no_cache, mock_client,
    ):
        self._setup_api(mock_client)
        result, from_cache = svc_no_cache.get_warehouse_top(limit=1)
        assert from_cache is False
        assert len(result) == 1


# ── Settings.reports_dir ──────────────────────────────────────────────


class TestSettingsReportsDir:
    """Tests for Settings.reports_dir() helper."""

    def test_creates_directory(self, tmp_path):
        from wb.core.config import Settings
        settings = Settings(config_dir=tmp_path)
        path = settings.reports_dir('my_profile')
        assert path.exists()
        assert path.is_dir()

    def test_path_is_scoped_to_profile(self, tmp_path):
        from wb.core.config import Settings
        settings = Settings(config_dir=tmp_path)
        path_a = settings.reports_dir('alpha')
        path_b = settings.reports_dir('beta')
        assert path_a != path_b
        assert 'alpha' in str(path_a)
        assert 'beta' in str(path_b)
