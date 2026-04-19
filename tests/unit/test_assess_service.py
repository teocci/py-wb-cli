"""Unit tests for AssessService and PulseService."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from wb.cli.app import app
from wb.core.exceptions import WbCliError
from wb.domain.assess_models import AssessSnapshot, CampaignPulse, PulseReport
from wb.domain.enums import CampaignStatus, CampaignType, PaymentType
from wb.domain.models import AccountBalance, BudgetSnapshot, Campaign, NmStats, RecommendedBid
from wb.services.assess import AssessService, default_date_window
from wb.services.bids import BidService
from wb.services.budgets import BudgetService
from wb.services.campaigns import CampaignService
from wb.services.pulse import PulseService, _compute_alerts, _compute_drift
from wb.services.stats import StatsService

runner = CliRunner()

ASSESS_FACTORY = 'wb.services._factory.create_assess_service'
PULSE_FACTORY = 'wb.services._factory.create_pulse_service'


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_campaign(
        campaign_id: int = 1,
        status: CampaignStatus = CampaignStatus.RUNNING,
        nm_ids: list[int] | None = None,
) -> Campaign:
    return Campaign(
        campaign_id=campaign_id,
        name=f'[test] Campaign {campaign_id}',
        status=status,
        campaign_type=CampaignType.STANDARD,
        payment_type=PaymentType.CPM,
        nm_ids=nm_ids or [100],
    )


def _make_balance(balance: int = 500_000) -> AccountBalance:
    return AccountBalance(balance=balance, currency='RUB')


def _make_nm_stats(nm_id: int = 100, spend: float = 840.0) -> NmStats:
    return NmStats(nm_id=nm_id, spend=spend, views=1200, clicks=50, orders=10)


def _make_budget(campaign_id: int = 1, total: int = 1000) -> BudgetSnapshot:
    return BudgetSnapshot(campaign_id=campaign_id, total=total, cash=1000)


def _make_recommended_bid(
        campaign_id: int = 1, nm_id: int = 100, recommended: int = 2000, minimum: int = 800,
) -> RecommendedBid:
    return RecommendedBid(
        campaign_id=campaign_id, nm_id=nm_id, recommended=recommended, minimum=minimum,
    )


def _make_assess_service(
        campaigns: list[Campaign] | None = None,
        balance: AccountBalance | None = None,
        nm_stats: list[NmStats] | None = None,
) -> AssessService:
    campaign_svc = MagicMock(spec=CampaignService)
    all_campaigns = campaigns or []

    def _list_by_status(status=None, type_=None):
        if status is None:
            return all_campaigns
        return [c for c in all_campaigns if c.status == status]

    campaign_svc.list_campaigns.side_effect = _list_by_status
    budget_svc = MagicMock(spec=BudgetService)
    budget_svc.get_balance.return_value = balance or _make_balance()
    stats_svc = MagicMock(spec=StatsService)
    stats_svc.get_product_spend.return_value = nm_stats or []
    return AssessService(campaign_svc, budget_svc, stats_svc)


def _make_pulse_service(
        campaign: Campaign | None = None,
        budget: BudgetSnapshot | None = None,
        bids: list[RecommendedBid] | None = None,
        config_dir: Path | None = None,
) -> PulseService:
    campaign_svc = MagicMock(spec=CampaignService)
    campaign_svc.get_campaign.return_value = campaign or _make_campaign()
    budget_svc = MagicMock(spec=BudgetService)
    budget_svc.get_budget.return_value = budget or _make_budget()
    bid_svc = MagicMock(spec=BidService)
    bid_svc.get_recommended_bids.return_value = bids or [_make_recommended_bid()]
    path = config_dir or Path(tempfile.mkdtemp())
    return PulseService(campaign_svc, budget_svc, bid_svc, path)


# ── AssessService ─────────────────────────────────────────────────────────────


class TestAssessService:
    """AssessService.get_snapshot unit tests."""

    def test_balance_converted_from_kopecks_to_rub(self) -> None:
        svc = _make_assess_service(balance=_make_balance(balance=500_000))
        snapshot = svc.get_snapshot('2026-04-10', '2026-04-17')
        assert snapshot.balance_rub == pytest.approx(5000.0)

    def test_running_campaigns_categorised_correctly(self) -> None:
        running = [_make_campaign(1, CampaignStatus.RUNNING)]
        paused = [_make_campaign(2, CampaignStatus.PAUSED)]
        svc = _make_assess_service(campaigns=running + paused)
        snapshot = svc.get_snapshot('2026-04-10', '2026-04-17')
        assert len(snapshot.running) == 1
        assert snapshot.running[0].campaign_id == 1
        assert len(snapshot.paused) == 1
        assert snapshot.paused[0].campaign_id == 2

    def test_nm_id_extracted_from_first_element(self) -> None:
        camp = _make_campaign(nm_ids=[789, 111])
        svc = _make_assess_service(campaigns=[camp])
        snapshot = svc.get_snapshot('2026-04-10', '2026-04-17')
        assert snapshot.running[0].nm_id == 789

    def test_quick_mode_skips_product_spend(self) -> None:
        running = [_make_campaign()]
        svc = _make_assess_service(campaigns=[running[0]])
        snapshot = svc.get_snapshot('2026-04-10', '2026-04-17', quick=True)
        svc._stats.get_product_spend.assert_not_called()
        assert snapshot.product_spend_7d == []

    def test_full_mode_calls_product_spend(self) -> None:
        running = [_make_campaign(nm_ids=[100])]
        nm_stats = [_make_nm_stats()]
        svc = _make_assess_service(campaigns=[running[0]], nm_stats=nm_stats)
        snapshot = svc.get_snapshot('2026-04-10', '2026-04-17', quick=False)
        svc._stats.get_product_spend.assert_called_once_with(
            [100], '2026-04-10', '2026-04-17',
        )
        assert len(snapshot.product_spend_7d) == 1

    def test_balance_error_returns_zero(self) -> None:
        svc = _make_assess_service()
        svc._budget.get_balance.side_effect = WbCliError('unavailable')
        snapshot = svc.get_snapshot('2026-04-10', '2026-04-17')
        assert snapshot.balance_rub == 0.0

    def test_campaign_list_error_returns_empty(self) -> None:
        svc = _make_assess_service()
        svc._campaigns.list_campaigns.side_effect = WbCliError('unavailable')
        snapshot = svc.get_snapshot('2026-04-10', '2026-04-17')
        assert snapshot.running == []
        assert snapshot.paused == []

    def test_data_as_of_is_iso_string(self) -> None:
        svc = _make_assess_service()
        snapshot = svc.get_snapshot('2026-04-10', '2026-04-17')
        assert 'T' in snapshot.data_as_of  # ISO format


class TestDefaultDateWindow:
    """default_date_window helper tests."""

    def test_returns_correct_span(self) -> None:
        date_from, date_to = default_date_window(7)
        from datetime import date, timedelta
        today = date.today().strftime('%Y-%m-%d')
        assert date_to == today
        assert date_from < date_to

    def test_custom_days(self) -> None:
        date_from, date_to = default_date_window(30)
        from datetime import date, timedelta
        expected_from = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
        assert date_from == expected_from


# ── PulseService ──────────────────────────────────────────────────────────────


class TestPulseService:
    """PulseService.get_pulse unit tests."""

    def test_healthy_campaign_has_no_alerts(self) -> None:
        svc = _make_pulse_service(
            budget=_make_budget(total=2000),
            bids=[_make_recommended_bid(recommended=2000, minimum=800)],
        )
        report = svc.get_pulse([1])
        assert report.action_needed is False
        assert report.campaigns[0].alerts == []

    def test_budget_low_alert_fires_below_threshold(self) -> None:
        svc = _make_pulse_service(
            budget=_make_budget(total=400),  # 400 RUB < 500 threshold
        )
        report = svc.get_pulse([1])
        assert 'budget_low' in report.campaigns[0].alerts

    def test_campaign_paused_alert_fires(self) -> None:
        paused = _make_campaign(status=CampaignStatus.PAUSED)
        svc = _make_pulse_service(campaign=paused)
        report = svc.get_pulse([1])
        assert 'campaign_paused' in report.campaigns[0].alerts

    def test_competitor_surge_detected_from_baseline(self, tmp_path) -> None:
        baseline = {
            'saved_at': '2026-04-17T09:00:00',
            'campaigns': {'1': {'recommend_kopecks': 1000, 'minimum_kopecks': 400, 'budget_rub': 2000}},
        }
        (tmp_path / 'pulse_baseline.json').write_text(
            json.dumps(baseline), encoding='utf-8',
        )
        svc = _make_pulse_service(
            bids=[_make_recommended_bid(recommended=1250, minimum=400)],
            config_dir=tmp_path,
        )
        report = svc.get_pulse([1])
        # 1250 vs 1000 = +25% > 15% threshold
        assert 'competitor_surge' in report.campaigns[0].alerts

    def test_bid_floor_rising_detected(self, tmp_path) -> None:
        baseline = {
            'saved_at': '2026-04-17T09:00:00',
            'campaigns': {'1': {'recommend_kopecks': 2000, 'minimum_kopecks': 800, 'budget_rub': 2000}},
        }
        (tmp_path / 'pulse_baseline.json').write_text(
            json.dumps(baseline), encoding='utf-8',
        )
        svc = _make_pulse_service(
            bids=[_make_recommended_bid(recommended=2000, minimum=1000)],
            config_dir=tmp_path,
        )
        report = svc.get_pulse([1])
        # 1000 vs 800 = +25% > 10% threshold
        assert 'bid_floor_rising' in report.campaigns[0].alerts

    def test_no_baseline_file_returns_zero_drift(self, tmp_path) -> None:
        svc = _make_pulse_service(config_dir=tmp_path)
        report = svc.get_pulse([1])
        assert report.campaigns[0].bid_recommend_drift_pct == pytest.approx(0.0)

    def test_action_needed_true_when_any_alert(self) -> None:
        svc = _make_pulse_service(budget=_make_budget(total=400))
        report = svc.get_pulse([1])
        assert report.action_needed is True

    def test_action_needed_false_when_no_alerts(self) -> None:
        svc = _make_pulse_service(budget=_make_budget(total=200_000))
        report = svc.get_pulse([1])
        assert report.action_needed is False

    def test_bid_values_converted_to_rub(self) -> None:
        svc = _make_pulse_service(
            bids=[_make_recommended_bid(recommended=2500, minimum=1000)],
            budget=_make_budget(total=2000),
        )
        report = svc.get_pulse([1])
        assert report.campaigns[0].bid_recommend_rub == pytest.approx(25.0)
        assert report.campaigns[0].bid_minimum_rub == pytest.approx(10.0)

    def test_budget_converted_to_rub(self) -> None:
        svc = _make_pulse_service(budget=_make_budget(total=7500))
        report = svc.get_pulse([1])
        assert report.campaigns[0].budget_remaining_rub == pytest.approx(7500.0)

    def test_save_baseline_writes_file(self, tmp_path) -> None:
        svc = _make_pulse_service(config_dir=tmp_path)
        svc.save_baseline([1])
        baseline_file = tmp_path / 'pulse_baseline.json'
        assert baseline_file.exists()
        data = json.loads(baseline_file.read_text(encoding='utf-8'))
        assert '1' in data['campaigns']


# ── Pure helper functions ─────────────────────────────────────────────────────


class TestComputeDrift:
    """_compute_drift pure function tests."""

    def test_positive_drift(self) -> None:
        assert _compute_drift(1200, 1000) == pytest.approx(20.0)

    def test_negative_drift(self) -> None:
        assert _compute_drift(800, 1000) == pytest.approx(-20.0)

    def test_zero_baseline_returns_zero(self) -> None:
        assert _compute_drift(1000, 0) == pytest.approx(0.0)

    def test_no_change(self) -> None:
        assert _compute_drift(1000, 1000) == pytest.approx(0.0)


class TestComputeAlerts:
    """_compute_alerts pure function tests."""

    def test_no_alerts_for_healthy_state(self) -> None:
        alerts = _compute_alerts(
            status='running', budget_rub=1000.0,
            baseline_budget_rub=2000.0,
            bid_drift_pct=5.0, floor_drift_pct=3.0,
        )
        assert alerts == []

    def test_campaign_paused_alert(self) -> None:
        alerts = _compute_alerts(
            status='paused', budget_rub=1000.0,
            baseline_budget_rub=2000.0,
            bid_drift_pct=0.0, floor_drift_pct=0.0,
        )
        assert 'campaign_paused' in alerts

    def test_budget_low_absolute(self) -> None:
        alerts = _compute_alerts(
            status='running', budget_rub=400.0,
            baseline_budget_rub=2000.0,
            bid_drift_pct=0.0, floor_drift_pct=0.0,
        )
        assert 'budget_low' in alerts

    def test_competitor_surge_at_threshold(self) -> None:
        alerts = _compute_alerts(
            status='running', budget_rub=1000.0,
            baseline_budget_rub=2000.0,
            bid_drift_pct=15.0, floor_drift_pct=0.0,
        )
        assert 'competitor_surge' in alerts

    def test_bid_floor_rising_at_threshold(self) -> None:
        alerts = _compute_alerts(
            status='running', budget_rub=1000.0,
            baseline_budget_rub=2000.0,
            bid_drift_pct=0.0, floor_drift_pct=10.0,
        )
        assert 'bid_floor_rising' in alerts


# ── CLI command tests ─────────────────────────────────────────────────────────


class TestAssessCommand:
    """CLI tests for wb assess."""

    def test_assess_json_output(self) -> None:
        mock_svc = MagicMock(spec=AssessService)
        mock_svc.get_snapshot.return_value = AssessSnapshot(
            data_as_of='2026-04-17T09:00:00+00:00',
            balance_rub=5000.0,
            running=[],
            paused=[],
            ready=[],
            product_spend_7d=[],
        )
        with patch(ASSESS_FACTORY, return_value=mock_svc):
            with patch(PULSE_FACTORY):
                result = runner.invoke(app, ['--json', 'assess', '--quick'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['balance_rub'] == 5000.0

    def test_assess_quick_skips_spend(self) -> None:
        mock_svc = MagicMock(spec=AssessService)
        mock_svc.get_snapshot.return_value = AssessSnapshot(
            data_as_of='2026-04-17T09:00:00+00:00',
        )
        with patch(ASSESS_FACTORY, return_value=mock_svc):
            with patch(PULSE_FACTORY):
                runner.invoke(app, ['--json', 'assess', '--quick'])
        mock_svc.get_snapshot.assert_called_once()
        _, kwargs = mock_svc.get_snapshot.call_args
        assert kwargs.get('quick') is True


class TestPulseCommand:
    """CLI tests for wb pulse."""

    def test_pulse_json_output(self) -> None:
        mock_svc = MagicMock(spec=PulseService)
        mock_svc.get_pulse.return_value = PulseReport(
            timestamp='2026-04-17T14:00:00+00:00',
            campaigns=[
                CampaignPulse(campaign_id=123, status='running', alerts=[]),
            ],
            action_needed=False,
        )
        with patch(PULSE_FACTORY, return_value=mock_svc):
            result = runner.invoke(app, ['--json', 'pulse', '--campaigns', '123'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['action_needed'] is False
        assert len(data['campaigns']) == 1

    def test_pulse_invalid_campaigns_exits_with_error(self) -> None:
        result = runner.invoke(app, ['pulse', '--campaigns', 'not-an-int'])
        assert result.exit_code != 0

    def test_pulse_requires_campaigns_option(self) -> None:
        result = runner.invoke(app, ['pulse'])
        assert result.exit_code != 0
