"""Tests for per-product ad spend: NmStats model, StatsService, and CLI."""

from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import MagicMock, call, patch

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.domain.models import (
    CampaignStats,
    DayStats,
    NmStats,
    _aggregate_nm_totals,
    _apply_booster_stats,
)
from wb.services.stats import StatsService

runner = CliRunner()

FACTORY_PATH = 'wb.services._factory.create_stats_service'

# ── Fixtures ──────────────────────────────────────────────────────────


def _make_client(
        campaigns: list[dict] | None = None,
        fullstats: list[dict] | None = None,
) -> MagicMock:
    client = MagicMock()
    client.list_campaigns.return_value = campaigns or []
    client.get_campaign_stats.return_value = fullstats or []
    return client


def _fullstats_payload(
        advert_id: int = 1,
        nm_id: int = 100,
        spend: float = 500.0,
        views: int = 1000,
        avg_position: float = 0.0,
) -> dict:
    """Minimal fullstats payload with one NM."""
    payload: dict = {
        'advertId': advert_id,
        'views': views,
        'clicks': 50,
        'ctr': 5.0,
        'orders': 10,
        'sum': spend,
        'cpc': 10.0,
        'cr': 1.0,
        'atbs': 20,
        'shks': 8,
        'currency': 'RUB',
        'days': [
            {
                'date': '2026-04-01',
                'views': views,
                'clicks': 50,
                'orders': 10,
                'sum': spend,
                'apps': [
                    {
                        'nms': [
                            {
                                'nmId': nm_id,
                                'name': f'Product {nm_id}',
                                'views': views,
                                'clicks': 50,
                                'ctr': 5.0,
                                'orders': 10,
                                'sum': spend,
                                'cpc': 10.0,
                                'cr': 1.0,
                                'atbs': 20,
                                'shks': 8,
                            }
                        ]
                    }
                ],
            }
        ],
    }
    if avg_position:
        payload['boosterStats'] = [{'nm': nm_id, 'avg_position': avg_position}]
    return payload


# ── NmStats model ─────────────────────────────────────────────────────


class TestNmStatsAvgPosition:
    """avg_position field defaults and serialisation."""

    def test_default_avg_position_zero(self) -> None:
        nm = NmStats(nm_id=123)
        assert nm.avg_position == 0.0

    def test_avg_position_in_asdict(self) -> None:
        nm = NmStats(nm_id=123, avg_position=3.7)
        d = asdict(nm)
        assert d['avg_position'] == 3.7

    def test_from_api_does_not_set_avg_position(self) -> None:
        """from_api() leaves avg_position at 0; booster is set separately."""
        nm = NmStats.from_api({'nmId': 5, 'views': 10, 'sum': 100.0})
        assert nm.avg_position == 0.0


# ── Booster stats helpers ─────────────────────────────────────────────


class TestBoosterStatsHelpers:
    """_aggregate_nm_totals and _apply_booster_stats module helpers."""

    def _make_day(self, nm_id: int, spend: float) -> DayStats:
        return DayStats(
            date='2026-04-01',
            spend=spend,
            nm_stats=[NmStats(nm_id=nm_id, spend=spend)],
        )

    def test_aggregate_sums_across_days(self) -> None:
        days = [self._make_day(10, 100.0), self._make_day(10, 200.0)]
        totals = _aggregate_nm_totals(days)
        assert totals[10].spend == 300.0

    def test_apply_booster_sets_avg_position(self) -> None:
        totals = {5: NmStats(nm_id=5, spend=100.0)}
        _apply_booster_stats(totals, [{'nm': 5, 'avg_position': 4.2}])
        assert totals[5].avg_position == pytest.approx(4.2)

    def test_apply_booster_fallback_nm_id_key(self) -> None:
        """'nm_id' key is accepted as fallback when 'nm' is absent."""
        totals = {7: NmStats(nm_id=7)}
        _apply_booster_stats(totals, [{'nm_id': 7, 'avg_position': 2.0}])
        assert totals[7].avg_position == pytest.approx(2.0)

    def test_apply_booster_ignores_unknown_nm(self) -> None:
        totals = {5: NmStats(nm_id=5)}
        _apply_booster_stats(totals, [{'nm': 99, 'avg_position': 1.0}])
        assert totals[5].avg_position == 0.0


# ── CampaignStats.from_api booster stats ─────────────────────────────


class TestCampaignStatsBoosterParsing:
    """CampaignStats.from_api() integrates boosterStats."""

    def test_booster_stats_applied_to_nm_stats(self) -> None:
        payload = _fullstats_payload(nm_id=100, spend=300.0, avg_position=5.5)
        cs = CampaignStats.from_api(payload)
        assert len(cs.nm_stats) == 1
        assert cs.nm_stats[0].avg_position == pytest.approx(5.5)

    def test_no_booster_stats_leaves_zero(self) -> None:
        payload = _fullstats_payload(nm_id=100)
        cs = CampaignStats.from_api(payload)
        assert cs.nm_stats[0].avg_position == 0.0

    def test_booster_stats_missing_key_is_ignored(self) -> None:
        payload = _fullstats_payload(nm_id=100)
        payload['boosterStats'] = [{'nm': 999, 'avg_position': 3.0}]
        cs = CampaignStats.from_api(payload)
        assert cs.nm_stats[0].avg_position == 0.0


# ── StatsService.get_product_spend ───────────────────────────────────


class TestGetProductSpend:
    """StatsService.get_product_spend() unit tests."""

    def test_returns_spend_for_matching_nm(self) -> None:
        client = _make_client(
            campaigns=[
                {'id': 1, 'nm_settings': [{'nm_id': 100}]},
            ],
            fullstats=[_fullstats_payload(advert_id=1, nm_id=100, spend=500.0)],
        )
        svc = StatsService(client)
        result = svc.get_product_spend([100], '2026-04-01', '2026-04-01')
        assert len(result) == 1
        assert result[0].nm_id == 100
        assert result[0].spend == pytest.approx(500.0)

    def test_zero_row_when_nm_not_in_any_campaign(self) -> None:
        client = _make_client(campaigns=[])
        svc = StatsService(client)
        result = svc.get_product_spend([999], '2026-04-01', '2026-04-01')
        assert result == [NmStats(nm_id=999)]

    def test_aggregates_across_campaigns(self) -> None:
        client = _make_client(
            campaigns=[
                {'id': 1, 'nm_settings': [{'nm_id': 100}]},
                {'id': 2, 'nm_settings': [{'nm_id': 100}]},
            ],
            fullstats=[
                _fullstats_payload(advert_id=1, nm_id=100, spend=300.0),
                _fullstats_payload(advert_id=2, nm_id=100, spend=200.0),
            ],
        )
        svc = StatsService(client)
        result = svc.get_product_spend([100], '2026-04-01', '2026-04-01')
        assert result[0].spend == pytest.approx(500.0)

    def test_sorted_by_spend_descending(self) -> None:
        client = _make_client(
            campaigns=[
                {'id': 1, 'nm_settings': [{'nm_id': 10}, {'nm_id': 20}]},
            ],
            fullstats=[
                _fullstats_payload(advert_id=1, nm_id=10, spend=100.0),
                # nm 20 not in fullstats → zero
            ],
        )
        # Patch so the client returns two NM rows from fullstats
        raw_fullstats = {
            'advertId': 1,
            'views': 1000,
            'clicks': 0,
            'ctr': 0.0,
            'orders': 0,
            'sum': 350.0,
            'cpc': 0.0,
            'cr': 0.0,
            'atbs': 0,
            'shks': 0,
            'currency': 'RUB',
            'days': [
                {
                    'date': '2026-04-01',
                    'views': 1000,
                    'clicks': 0,
                    'orders': 0,
                    'sum': 350.0,
                    'apps': [
                        {
                            'nms': [
                                {'nmId': 10, 'name': 'P10', 'views': 500,
                                 'clicks': 0, 'ctr': 0, 'orders': 0,
                                 'sum': 150.0, 'cpc': 0, 'cr': 0, 'atbs': 0, 'shks': 0},
                                {'nmId': 20, 'name': 'P20', 'views': 500,
                                 'clicks': 0, 'ctr': 0, 'orders': 0,
                                 'sum': 200.0, 'cpc': 0, 'cr': 0, 'atbs': 0, 'shks': 0},
                            ]
                        }
                    ],
                }
            ],
        }
        client2 = _make_client(
            campaigns=[{'id': 1, 'nm_settings': [{'nm_id': 10}, {'nm_id': 20}]}],
            fullstats=[raw_fullstats],
        )
        svc = StatsService(client2)
        result = svc.get_product_spend([10, 20], '2026-04-01', '2026-04-01')
        assert result[0].nm_id == 20
        assert result[0].spend == pytest.approx(200.0)
        assert result[1].nm_id == 10
        assert result[1].spend == pytest.approx(150.0)

    def test_filters_out_unrelated_nms_from_stats(self) -> None:
        """Stats for NMs not in the requested list are excluded."""
        raw_fullstats = {
            'advertId': 1,
            'views': 0, 'clicks': 0, 'ctr': 0, 'orders': 0,
            'sum': 0, 'cpc': 0, 'cr': 0, 'atbs': 0, 'shks': 0,
            'currency': 'RUB',
            'days': [{
                'date': '2026-04-01',
                'views': 0, 'clicks': 0, 'orders': 0, 'sum': 0,
                'apps': [{'nms': [
                    {'nmId': 100, 'name': '', 'views': 0, 'clicks': 0,
                     'ctr': 0, 'orders': 0, 'sum': 300.0, 'cpc': 0,
                     'cr': 0, 'atbs': 0, 'shks': 0},
                    {'nmId': 999, 'name': '', 'views': 0, 'clicks': 0,
                     'ctr': 0, 'orders': 0, 'sum': 9999.0, 'cpc': 0,
                     'cr': 0, 'atbs': 0, 'shks': 0},
                ]}],
            }],
        }
        client = _make_client(
            campaigns=[{'id': 1, 'nm_settings': [{'nm_id': 100}]}],
            fullstats=[raw_fullstats],
        )
        svc = StatsService(client)
        result = svc.get_product_spend([100], '2026-04-01', '2026-04-01')
        nm_ids = {r.nm_id for r in result}
        assert 999 not in nm_ids

    def test_chunks_campaigns_when_over_batch_size(self) -> None:
        """get_campaigns_stats sends multiple API calls for >50 campaign IDs."""
        campaigns = [
            {'id': i, 'nm_settings': [{'nm_id': 100}]} for i in range(1, 52)
        ]
        client = _make_client(campaigns=campaigns, fullstats=[])
        svc = StatsService(client)
        svc.get_product_spend([100], '2026-04-01', '2026-04-01')
        # 51 campaigns → 2 chunks (50 + 1)
        assert client.get_campaign_stats.call_count == 2

    def test_validation_error_on_bad_date(self) -> None:
        from wb.core.exceptions import ValidationError
        svc = StatsService(_make_client())
        with pytest.raises(ValidationError):
            svc.get_product_spend([100], 'not-a-date', '2026-04-01')

    def test_cache_write_through_called(self) -> None:
        """When CacheStore is injected, save_stats is called per day."""
        client = _make_client(
            campaigns=[{'id': 1, 'nm_settings': [{'nm_id': 100}]}],
            fullstats=[_fullstats_payload(advert_id=1, nm_id=100, spend=100.0)],
        )
        cache = MagicMock()
        svc = StatsService(client, cache_store=cache, profile_name='test')
        svc.get_product_spend([100], '2026-04-01', '2026-04-01')
        assert cache.save_stats.called


# ── CLI product-spend command ─────────────────────────────────────────


class TestCliProductSpend:
    """CLI tests for 'stats product-spend'."""

    def test_help(self) -> None:
        result = runner.invoke(app, ['stats', 'product-spend', '--help'])
        assert result.exit_code == 0

    @patch(FACTORY_PATH)
    def test_json_output(self, mock_factory: MagicMock) -> None:
        svc = MagicMock()
        svc.get_product_spend.return_value = [
            NmStats(nm_id=100, spend=500.0, views=1000, clicks=50, orders=10),
        ]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'stats', 'product-spend',
            '--nms', '100',
            '--from', '2026-04-01',
            '--to', '2026-04-06',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]['nm_id'] == 100
        assert parsed[0]['spend'] == 500.0

    @patch(FACTORY_PATH)
    def test_empty_result_shows_message(self, mock_factory: MagicMock) -> None:
        svc = MagicMock()
        svc.get_product_spend.return_value = []
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'stats', 'product-spend',
            '--nms', '100',
            '--from', '2026-04-01',
            '--to', '2026-04-06',
        ])
        assert result.exit_code == 0
        assert 'No spend data found' in result.output

    @patch(FACTORY_PATH)
    def test_passes_parsed_nm_ids_to_service(self, mock_factory: MagicMock) -> None:
        svc = MagicMock()
        svc.get_product_spend.return_value = []
        mock_factory.return_value = svc

        runner.invoke(app, [
            '--json', 'stats', 'product-spend',
            '--nms', '100,200,300',
            '--from', '2026-04-01',
            '--to', '2026-04-06',
        ])
        svc.get_product_spend.assert_called_once_with(
            [100, 200, 300], '2026-04-01', '2026-04-06',
        )

    @patch(FACTORY_PATH)
    def test_avg_position_in_json_output(self, mock_factory: MagicMock) -> None:
        svc = MagicMock()
        svc.get_product_spend.return_value = [
            NmStats(nm_id=100, spend=200.0, avg_position=3.5),
        ]
        mock_factory.return_value = svc

        result = runner.invoke(app, [
            '--json', 'stats', 'product-spend',
            '--nms', '100',
            '--from', '2026-04-01',
            '--to', '2026-04-06',
        ])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed[0]['avg_position'] == pytest.approx(3.5)
