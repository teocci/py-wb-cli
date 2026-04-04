"""SQLite-backed local cache for WB CLI snapshots.

Stores campaign configs, daily stats, cluster states, and budget
events captured from the WB API. All writes are explicit — the cache
is never populated automatically without user intent.

Schema version is stored in SQLite's PRAGMA user_version for
forward-compatible migrations.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from wb.domain.cache_models import (
    BudgetEvent,
    CampaignSnapshot,
    ClusterRecord,
    ReportCacheEntry,
    StatsRecord,
)

__all__ = ['CacheStore']

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 2


class CacheStore:
    """Persistent SQLite cache for WB CLI data snapshots.

    Attributes:
        db_path: Absolute path to the SQLite database file.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._init_db()

    # ── Initialisation ────────────────────────────────────────────────

    def _init_db(self) -> None:
        """Create tables and run schema migrations if needed."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            version = conn.execute('PRAGMA user_version').fetchone()[0]
            if version < _SCHEMA_VERSION:
                self._create_schema(conn)
                conn.execute(f'PRAGMA user_version = {_SCHEMA_VERSION}')

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        """Create all tables for schema version 2."""
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS campaigns (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id   INTEGER NOT NULL,
                profile       TEXT    NOT NULL,
                snapshot_time TEXT    NOT NULL,
                name          TEXT    NOT NULL,
                status        INTEGER NOT NULL,
                campaign_type INTEGER NOT NULL,
                daily_budget  INTEGER NOT NULL DEFAULT 0,
                payload_json  TEXT    NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_campaigns_id
                ON campaigns (campaign_id, profile, snapshot_time);

            CREATE TABLE IF NOT EXISTS campaign_stats (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id  INTEGER NOT NULL,
                profile      TEXT    NOT NULL,
                date         TEXT    NOT NULL,
                views        INTEGER NOT NULL DEFAULT 0,
                clicks       INTEGER NOT NULL DEFAULT 0,
                ctr          REAL    NOT NULL DEFAULT 0.0,
                spend        INTEGER NOT NULL DEFAULT 0,
                orders       INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT    NOT NULL DEFAULT '{}'
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_stats_date
                ON campaign_stats (campaign_id, profile, date);

            CREATE TABLE IF NOT EXISTS cluster_snapshots (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id   INTEGER NOT NULL,
                nm_id         INTEGER NOT NULL,
                norm_query    TEXT    NOT NULL,
                profile       TEXT    NOT NULL,
                snapshot_time TEXT    NOT NULL,
                bid           INTEGER NOT NULL DEFAULT 0,
                views         INTEGER NOT NULL DEFAULT 0,
                clicks        INTEGER NOT NULL DEFAULT 0,
                spend         INTEGER NOT NULL DEFAULT 0,
                orders        INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_clusters_key
                ON cluster_snapshots (campaign_id, nm_id, profile, snapshot_time);

            CREATE TABLE IF NOT EXISTS budget_events (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                profile       TEXT    NOT NULL,
                campaign_id   INTEGER,
                event_type    TEXT    NOT NULL,
                amount        INTEGER NOT NULL DEFAULT 0,
                balance_after INTEGER NOT NULL DEFAULT 0,
                created_at    TEXT    NOT NULL,
                payload_json  TEXT    NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_budget_profile
                ON budget_events (profile, created_at);

            CREATE TABLE IF NOT EXISTS report_cache (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_name  TEXT NOT NULL,
                seller_id     TEXT,
                report_type   TEXT NOT NULL,
                date          TEXT NOT NULL,
                payload_path  TEXT NOT NULL,
                computed_at   TEXT NOT NULL,
                UNIQUE (profile_name, report_type, date) ON CONFLICT REPLACE
            );
            CREATE INDEX IF NOT EXISTS idx_report_cache_key
                ON report_cache (profile_name, report_type, date);
        ''')

    def _connect(self) -> sqlite3.Connection:
        """Open and configure a SQLite connection."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        return conn

    # ── Campaign snapshots ────────────────────────────────────────────

    def save_campaign(self, snap: CampaignSnapshot) -> int:
        """Insert a campaign snapshot row.

        Args:
            snap: CampaignSnapshot to persist.

        Returns:
            The new row ID.
        """
        sql = '''
            INSERT INTO campaigns
              (campaign_id, profile, snapshot_time, name, status,
               campaign_type, daily_budget, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        '''
        with self._connect() as conn:
            cur = conn.execute(sql, (
                snap.campaign_id, snap.profile, snap.snapshot_time,
                snap.name, snap.status, snap.campaign_type,
                snap.daily_budget, snap.payload_json,
            ))
            return cur.lastrowid

    def list_campaigns(
            self,
            profile: str,
            campaign_id: int | None = None,
            limit: int = 50,
    ) -> list[CampaignSnapshot]:
        """Query campaign snapshots.

        Args:
            profile: Profile to filter by.
            campaign_id: Optional campaign ID filter.
            limit: Maximum rows to return.

        Returns:
            List of CampaignSnapshot ordered by snapshot_time desc.
        """
        where = 'profile = ?'
        params: list = [profile]
        if campaign_id is not None:
            where += ' AND campaign_id = ?'
            params.append(campaign_id)
        sql = (
            f'SELECT * FROM campaigns WHERE {where} '
            f'ORDER BY snapshot_time DESC LIMIT ?'
        )
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_campaign(r) for r in rows]

    # ── Stats records ─────────────────────────────────────────────────

    def save_stats(self, rec: StatsRecord) -> int:
        """Insert or replace a campaign stats row (upsert by date).

        Args:
            rec: StatsRecord to persist.

        Returns:
            The new or replaced row ID.
        """
        sql = '''
            INSERT OR REPLACE INTO campaign_stats
              (campaign_id, profile, date, views, clicks, ctr,
               spend, orders, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        with self._connect() as conn:
            cur = conn.execute(sql, (
                rec.campaign_id, rec.profile, rec.date,
                rec.views, rec.clicks, rec.ctr,
                rec.spend, rec.orders, rec.payload_json,
            ))
            return cur.lastrowid

    def list_stats(
            self,
            profile: str,
            campaign_id: int,
            date_from: str | None = None,
            date_to: str | None = None,
            limit: int = 90,
    ) -> list[StatsRecord]:
        """Query stats for a campaign.

        Args:
            profile: Profile to filter by.
            campaign_id: Campaign to filter by.
            date_from: Optional start date (YYYY-MM-DD), inclusive.
            date_to: Optional end date (YYYY-MM-DD), inclusive.
            limit: Maximum rows to return.

        Returns:
            List of StatsRecord ordered by date asc.
        """
        where = 'profile = ? AND campaign_id = ?'
        params: list = [profile, campaign_id]
        if date_from:
            where += ' AND date >= ?'
            params.append(date_from)
        if date_to:
            where += ' AND date <= ?'
            params.append(date_to)
        sql = (
            f'SELECT * FROM campaign_stats WHERE {where} '
            f'ORDER BY date ASC LIMIT ?'
        )
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_stats(r) for r in rows]

    # ── Cluster records ───────────────────────────────────────────────

    def save_cluster(self, rec: ClusterRecord) -> int:
        """Insert a cluster snapshot row.

        Args:
            rec: ClusterRecord to persist.

        Returns:
            The new row ID.
        """
        sql = '''
            INSERT INTO cluster_snapshots
              (campaign_id, nm_id, norm_query, profile, snapshot_time,
               bid, views, clicks, spend, orders)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        with self._connect() as conn:
            cur = conn.execute(sql, (
                rec.campaign_id, rec.nm_id, rec.norm_query,
                rec.profile, rec.snapshot_time, rec.bid,
                rec.views, rec.clicks, rec.spend, rec.orders,
            ))
            return cur.lastrowid

    def list_clusters(
            self,
            profile: str,
            campaign_id: int,
            nm_id: int | None = None,
            limit: int = 200,
    ) -> list[ClusterRecord]:
        """Query cluster snapshots.

        Args:
            profile: Profile to filter by.
            campaign_id: Campaign to filter by.
            nm_id: Optional product nm_id filter.
            limit: Maximum rows to return.

        Returns:
            List of ClusterRecord ordered by snapshot_time desc.
        """
        where = 'profile = ? AND campaign_id = ?'
        params: list = [profile, campaign_id]
        if nm_id is not None:
            where += ' AND nm_id = ?'
            params.append(nm_id)
        sql = (
            f'SELECT * FROM cluster_snapshots WHERE {where} '
            f'ORDER BY snapshot_time DESC LIMIT ?'
        )
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_cluster(r) for r in rows]

    # ── Budget events ─────────────────────────────────────────────────

    def save_budget_event(self, evt: BudgetEvent) -> int:
        """Insert a budget event row.

        Args:
            evt: BudgetEvent to persist.

        Returns:
            The new row ID.
        """
        sql = '''
            INSERT INTO budget_events
              (profile, campaign_id, event_type, amount,
               balance_after, created_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        with self._connect() as conn:
            cur = conn.execute(sql, (
                evt.profile, evt.campaign_id, evt.event_type,
                evt.amount, evt.balance_after, evt.created_at,
                evt.payload_json,
            ))
            return cur.lastrowid

    def list_budget_events(
            self,
            profile: str,
            campaign_id: int | None = None,
            limit: int = 100,
    ) -> list[BudgetEvent]:
        """Query budget events.

        Args:
            profile: Profile to filter by.
            campaign_id: Optional campaign ID filter.
            limit: Maximum rows to return.

        Returns:
            List of BudgetEvent ordered by created_at desc.
        """
        where = 'profile = ?'
        params: list = [profile]
        if campaign_id is not None:
            where += ' AND campaign_id = ?'
            params.append(campaign_id)
        sql = (
            f'SELECT * FROM budget_events WHERE {where} '
            f'ORDER BY created_at DESC LIMIT ?'
        )
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_budget_event(r) for r in rows]

    # ── Report cache ─────────────────────────────────────────────────

    def save_report_cache(self, entry: ReportCacheEntry) -> None:
        """Insert or replace a report cache metadata row.

        Args:
            entry: ReportCacheEntry to persist.
        """
        sql = '''
            INSERT OR REPLACE INTO report_cache
              (profile_name, seller_id, report_type, date,
               payload_path, computed_at)
            VALUES (?, ?, ?, ?, ?, ?)
        '''
        with self._connect() as conn:
            conn.execute(sql, (
                entry.profile_name, entry.seller_id, entry.report_type,
                entry.date, entry.payload_path, entry.computed_at,
            ))

    def get_report_cache(
            self,
            profile_name: str,
            report_type: str,
            date: str,
    ) -> ReportCacheEntry | None:
        """Retrieve a single report cache entry by key.

        Args:
            profile_name: Profile that owns the entry.
            report_type: Type key (e.g. 'warehouse_remains').
            date: Date string (YYYY-MM-DD).

        Returns:
            ReportCacheEntry if found, otherwise None.
        """
        sql = '''
            SELECT * FROM report_cache
            WHERE profile_name = ? AND report_type = ? AND date = ?
        '''
        with self._connect() as conn:
            row = conn.execute(sql, (profile_name, report_type, date)).fetchone()
        if row is None:
            return None
        return _row_to_report_cache(row)

    def list_report_cache(
            self,
            profile_name: str,
            limit: int = 50,
    ) -> list[ReportCacheEntry]:
        """List report cache entries for a profile.

        Args:
            profile_name: Profile to filter by.
            limit: Maximum rows to return.

        Returns:
            List of ReportCacheEntry ordered by computed_at desc.
        """
        sql = '''
            SELECT * FROM report_cache
            WHERE profile_name = ?
            ORDER BY computed_at DESC LIMIT ?
        '''
        with self._connect() as conn:
            rows = conn.execute(sql, (profile_name, limit)).fetchall()
        return [_row_to_report_cache(r) for r in rows]

    # ── Maintenance ───────────────────────────────────────────────────

    def clear(
            self,
            profile: str,
            campaign_id: int | None = None,
    ) -> dict[str, int]:
        """Delete cached rows for the given profile/campaign.

        Args:
            profile: Profile whose data to clear.
            campaign_id: If given, clear only that campaign's rows.

        Returns:
            Dict with deleted row counts per table.
        """
        tables = [
            'campaigns', 'campaign_stats',
            'cluster_snapshots', 'budget_events',
        ]
        counts: dict[str, int] = {}
        with self._connect() as conn:
            for table in tables:
                where, params = _build_clear_where(table, profile, campaign_id)
                cur = conn.execute(
                    f'DELETE FROM {table} WHERE {where}', params
                )
                counts[table] = cur.rowcount
        return counts

    def summary(self, profile: str) -> dict[str, int]:
        """Count rows per table for a profile.

        Args:
            profile: Profile to summarize.

        Returns:
            Dict mapping table name to row count.
        """
        tables = [
            'campaigns', 'campaign_stats',
            'cluster_snapshots', 'budget_events',
        ]
        with self._connect() as conn:
            return {
                t: conn.execute(
                    f'SELECT COUNT(*) FROM {t} WHERE profile = ?', [profile]
                ).fetchone()[0]
                for t in tables
            }


# ── Helpers ───────────────────────────────────────────────────────────

def _build_clear_where(
        table: str,
        profile: str,
        campaign_id: int | None,
) -> tuple[str, list]:
    """Build WHERE clause for clear() DELETE statements."""
    where = 'profile = ?'
    params: list = [profile]
    if campaign_id is not None:
        where += ' AND campaign_id = ?'
        params.append(campaign_id)
    return where, params


# ── Row mappers ───────────────────────────────────────────────────────

def _row_to_campaign(row: sqlite3.Row) -> CampaignSnapshot:
    return CampaignSnapshot(
        id=row['id'],
        campaign_id=row['campaign_id'],
        profile=row['profile'],
        snapshot_time=row['snapshot_time'],
        name=row['name'],
        status=row['status'],
        campaign_type=row['campaign_type'],
        daily_budget=row['daily_budget'],
        payload_json=row['payload_json'],
    )


def _row_to_stats(row: sqlite3.Row) -> StatsRecord:
    return StatsRecord(
        id=row['id'],
        campaign_id=row['campaign_id'],
        profile=row['profile'],
        date=row['date'],
        views=row['views'],
        clicks=row['clicks'],
        ctr=row['ctr'],
        spend=row['spend'],
        orders=row['orders'],
        payload_json=row['payload_json'],
    )


def _row_to_cluster(row: sqlite3.Row) -> ClusterRecord:
    return ClusterRecord(
        id=row['id'],
        campaign_id=row['campaign_id'],
        nm_id=row['nm_id'],
        norm_query=row['norm_query'],
        profile=row['profile'],
        snapshot_time=row['snapshot_time'],
        bid=row['bid'],
        views=row['views'],
        clicks=row['clicks'],
        spend=row['spend'],
        orders=row['orders'],
    )


def _row_to_budget_event(row: sqlite3.Row) -> BudgetEvent:
    return BudgetEvent(
        id=row['id'],
        profile=row['profile'],
        campaign_id=row['campaign_id'],
        event_type=row['event_type'],
        amount=row['amount'],
        balance_after=row['balance_after'],
        created_at=row['created_at'],
        payload_json=row['payload_json'],
    )


def _row_to_report_cache(row: sqlite3.Row) -> ReportCacheEntry:
    return ReportCacheEntry(
        id=row['id'],
        profile_name=row['profile_name'],
        seller_id=row['seller_id'],
        report_type=row['report_type'],
        date=row['date'],
        payload_path=row['payload_path'],
        computed_at=row['computed_at'],
    )
