"""Tests for `scripts/generate_daily_wb_report.py`."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def _load_script_module():
    """Load the script as a module without running its main()."""
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / 'scripts' / 'generate_daily_wb_report.py'
    spec = importlib.util.spec_from_file_location(
        'generate_daily_wb_report', script_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules['generate_daily_wb_report'] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script_module():
    return _load_script_module()


class _FakeProc:
    """Minimal stand-in for subprocess.CompletedProcess."""

    def __init__(self, returncode: int, stdout: str = '', stderr: str = '') -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestRunWbCommandFastFail:
    """`run_wb_command` parses the JSON envelope on exit 5 and fails fast."""

    def test_exit_5_with_envelope_raises_with_retry_after(
            self, script_module,
    ) -> None:
        envelope = (
            '{"status":"error","error":{"code":"RATE_LIMITED",'
            '"message":"Endpoint /adv/v3/fullstats locked for ~3518s",'
            '"exit_code":5,"retry_after":3518.0}}'
        )
        with patch.object(
            script_module.subprocess, 'run',
            return_value=_FakeProc(5, stdout=envelope),
        ) as mock_run:
            with pytest.raises(script_module.RateLimitedError) as exc_info:
                script_module.run_wb_command(['wb', '--json', 'stats', 'daily-report'])

        assert exc_info.value.retry_after == 3518.0
        assert mock_run.call_count == 1

    def test_exit_5_with_unparseable_stdout_raises_without_retry_after(
            self, script_module,
    ) -> None:
        with patch.object(
            script_module.subprocess, 'run',
            return_value=_FakeProc(5, stdout='not json'),
        ):
            with pytest.raises(script_module.RateLimitedError) as exc_info:
                script_module.run_wb_command(['wb', 'stats', 'daily-report'])

        assert exc_info.value.retry_after is None

    def test_exit_5_envelope_in_stderr_is_picked_up(
            self, script_module,
    ) -> None:
        envelope = (
            '{"status":"error","error":{"code":"RATE_LIMITED",'
            '"message":"locked","exit_code":5,"retry_after":120.0}}'
        )
        with patch.object(
            script_module.subprocess, 'run',
            return_value=_FakeProc(5, stdout='', stderr=envelope),
        ):
            with pytest.raises(script_module.RateLimitedError) as exc_info:
                script_module.run_wb_command(['wb', 'stats', 'daily-report'])

        assert exc_info.value.retry_after == 120.0

    def test_exit_5_envelope_without_retry_after_returns_none(
            self, script_module,
    ) -> None:
        envelope = (
            '{"status":"error","error":{"code":"RATE_LIMITED",'
            '"message":"locked","exit_code":5}}'
        )
        with patch.object(
            script_module.subprocess, 'run',
            return_value=_FakeProc(5, stdout=envelope),
        ):
            with pytest.raises(script_module.RateLimitedError) as exc_info:
                script_module.run_wb_command(['wb', 'stats', 'daily-report'])

        assert exc_info.value.retry_after is None


class TestRunWbCommandSuccess:
    def test_exit_0_returns_parsed_payload(self, script_module) -> None:
        payload = '[{"nm_id":1,"name":"x","orders":2}]'
        with patch.object(
            script_module.subprocess, 'run',
            return_value=_FakeProc(0, stdout=payload),
        ):
            result, raw = script_module.run_wb_command(['wb', 'stats', 'daily-report'])
        assert raw == payload
        assert result == [{'nm_id': 1, 'name': 'x', 'orders': 2}]

    def test_exit_0_empty_stdout_raises(self, script_module) -> None:
        with patch.object(
            script_module.subprocess, 'run',
            return_value=_FakeProc(0, stdout=''),
        ):
            with pytest.raises(RuntimeError, match='Empty stdout'):
                script_module.run_wb_command(['wb', 'x'])


class TestRunWbCommandOtherErrors:
    def test_non_5_exit_raises_runtime_error(self, script_module) -> None:
        with patch.object(
            script_module.subprocess, 'run',
            return_value=_FakeProc(2, stderr='validation failed'),
        ):
            with pytest.raises(RuntimeError) as exc_info:
                script_module.run_wb_command(['wb', 'x'])
        assert 'exit=2' in str(exc_info.value)


class TestResolveDateRange:
    """resolve_date_range normalises three date modes to (from, to) strings."""

    def test_default_no_flags_yields_yesterday(self, script_module) -> None:
        from datetime import date, timedelta
        args = argparse.Namespace(date=None, days=None, from_date=None, to_date=None)
        from_date, to_date = script_module.resolve_date_range(args)
        yesterday = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        assert from_date == yesterday
        assert to_date == yesterday

    def test_date_flag_single_past_date(self, script_module) -> None:
        args = argparse.Namespace(date='2025-05-01', days=None, from_date=None, to_date=None)
        from_date, to_date = script_module.resolve_date_range(args)
        assert from_date == '2025-05-01'
        assert to_date == '2025-05-01'

    def test_days_flag_returns_range_ending_yesterday(self, script_module) -> None:
        from datetime import date, timedelta
        args = argparse.Namespace(date=None, days=3, from_date=None, to_date=None)
        from_date, to_date = script_module.resolve_date_range(args)
        yesterday = date.today() - timedelta(days=1)
        assert to_date == yesterday.strftime('%Y-%m-%d')
        expected_from = (yesterday - timedelta(days=2)).strftime('%Y-%m-%d')
        assert from_date == expected_from

    def test_from_to_flags_absolute_range(self, script_module) -> None:
        args = argparse.Namespace(
            date=None, days=None, from_date='2025-04-29', to_date='2025-05-05',
        )
        from_date, to_date = script_module.resolve_date_range(args)
        assert from_date == '2025-04-29'
        assert to_date == '2025-05-05'

    def test_days_1_yields_yesterday_both_sides(self, script_module) -> None:
        from datetime import date, timedelta
        args = argparse.Namespace(date=None, days=1, from_date=None, to_date=None)
        from_date, to_date = script_module.resolve_date_range(args)
        yesterday = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        assert from_date == yesterday
        assert to_date == yesterday

    def test_future_date_exits_2(self, script_module) -> None:
        args = argparse.Namespace(date='2099-01-01', days=None, from_date=None, to_date=None)
        with pytest.raises(SystemExit) as exc_info:
            script_module.resolve_date_range(args)
        assert exc_info.value.code == 2

    def test_days_0_exits_2(self, script_module) -> None:
        args = argparse.Namespace(date=None, days=0, from_date=None, to_date=None)
        with pytest.raises(SystemExit) as exc_info:
            script_module.resolve_date_range(args)
        assert exc_info.value.code == 2

    def test_days_8_exits_2(self, script_module) -> None:
        args = argparse.Namespace(date=None, days=8, from_date=None, to_date=None)
        with pytest.raises(SystemExit) as exc_info:
            script_module.resolve_date_range(args)
        assert exc_info.value.code == 2

    def test_from_without_to_exits_2(self, script_module) -> None:
        args = argparse.Namespace(date=None, days=None, from_date='2025-05-01', to_date=None)
        with pytest.raises(SystemExit) as exc_info:
            script_module.resolve_date_range(args)
        assert exc_info.value.code == 2

    def test_to_without_from_exits_2(self, script_module) -> None:
        args = argparse.Namespace(date=None, days=None, from_date=None, to_date='2025-05-01')
        with pytest.raises(SystemExit) as exc_info:
            script_module.resolve_date_range(args)
        assert exc_info.value.code == 2

    def test_from_after_to_exits_2(self, script_module) -> None:
        args = argparse.Namespace(
            date=None, days=None, from_date='2025-05-05', to_date='2025-05-01',
        )
        with pytest.raises(SystemExit) as exc_info:
            script_module.resolve_date_range(args)
        assert exc_info.value.code == 2

    def test_range_exceeds_7_days_exits_2(self, script_module) -> None:
        args = argparse.Namespace(
            date=None, days=None, from_date='2025-04-01', to_date='2025-04-09',
        )
        with pytest.raises(SystemExit) as exc_info:
            script_module.resolve_date_range(args)
        assert exc_info.value.code == 2

    def test_to_with_days_exits_2(self, script_module) -> None:
        args = argparse.Namespace(date=None, days=3, from_date=None, to_date='2025-05-01')
        with pytest.raises(SystemExit) as exc_info:
            script_module.resolve_date_range(args)
        assert exc_info.value.code == 2


class TestBuildReportRows:
    """build_report_rows maps DailyReportRow JSON to CSV dicts."""

    def _make_item(self, **overrides) -> dict:
        base = {
            'nm_id': 123, 'name': 'Test Product', 'views': 1000, 'clicks': 50,
            'ad_orders': 5, 'spend': 100.0, 'avg_position': 3.5, 'opens': 400,
            'cart_adds': 30, 'orders': 20, 'order_sum': 10000, 'buyouts': 18,
        }
        base.update(overrides)
        return base

    def test_field_mapping(self, script_module) -> None:
        rows = script_module.build_report_rows([self._make_item()])
        assert len(rows) == 1
        row = rows[0]
        assert row['article_number'] == '123'
        assert row['product_name'] == 'Test Product'
        assert row['orders'] == '20'
        assert row['advertising_costs'] == '100.00'
        assert row['ad_views'] == '1000'
        assert row['ad_clicks'] == '50'
        assert row['ad_orders'] == '5'
        assert row['opens'] == '400'
        assert row['cart_adds'] == '30'
        assert row['buyouts'] == '18'

    def test_computed_cpo(self, script_module) -> None:
        rows = script_module.build_report_rows([self._make_item(spend=100.0, orders=4)])
        assert rows[0]['cpo_rub'] == '25.00'

    def test_computed_drr(self, script_module) -> None:
        rows = script_module.build_report_rows(
            [self._make_item(spend=100.0, order_sum=1000)],
        )
        assert rows[0]['drr_percent'] == '10.00'

    def test_computed_cpc(self, script_module) -> None:
        rows = script_module.build_report_rows([self._make_item(spend=100.0, clicks=10)])
        assert rows[0]['cpc_rub'] == '10.00'

    def test_computed_ad_attribution(self, script_module) -> None:
        rows = script_module.build_report_rows(
            [self._make_item(ad_orders=2, orders=10)],
        )
        assert rows[0]['ad_attribution_percent'] == '20.0'

    def test_zero_denominator_yields_empty_string(self, script_module) -> None:
        rows = script_module.build_report_rows(
            [self._make_item(orders=0, order_sum=0, clicks=0)],
        )
        assert rows[0]['cpo_rub'] == ''
        assert rows[0]['drr_percent'] == ''
        assert rows[0]['cpc_rub'] == ''

    def test_sorted_by_spend_descending(self, script_module) -> None:
        items = [
            self._make_item(nm_id=1, spend=50.0),
            self._make_item(nm_id=2, spend=200.0),
            self._make_item(nm_id=3, spend=100.0),
        ]
        rows = script_module.build_report_rows(items)
        spends = [float(r['advertising_costs']) for r in rows]
        assert spends == sorted(spends, reverse=True)

    def test_avg_position_zero_yields_empty(self, script_module) -> None:
        rows = script_module.build_report_rows([self._make_item(avg_position=0)])
        assert rows[0]['avg_position'] == ''

    def test_avg_position_nonzero_formatted(self, script_module) -> None:
        rows = script_module.build_report_rows([self._make_item(avg_position=3.55)])
        assert rows[0]['avg_position'] == '3.6'


class TestBuildOrdersRows:
    """build_orders_rows derives the orders-only CSV from DailyReportRow."""

    def test_basic_mapping(self, script_module) -> None:
        payload = [{'nm_id': 42, 'name': 'Prod A', 'orders': 15}]
        rows = script_module.build_orders_rows(payload)
        assert rows == [
            {
                'article_number': '42',
                'product_name': 'Prod A',
                'sales-funnel order_count': '15',
            },
        ]

    def test_missing_orders_defaults_to_zero(self, script_module) -> None:
        payload = [{'nm_id': 1, 'name': 'X'}]
        rows = script_module.build_orders_rows(payload)
        assert rows[0]['sales-funnel order_count'] == '0'


class TestRateLimitedError:
    def test_carries_retry_after(self, script_module) -> None:
        exc = script_module.RateLimitedError('locked', retry_after=3500.0)
        assert exc.retry_after == 3500.0
        assert 'locked' in str(exc)

    def test_retry_after_optional(self, script_module) -> None:
        exc = script_module.RateLimitedError('locked')
        assert exc.retry_after is None


class TestNoHomeIsolation:
    def test_no_home_isolation_constants(self, script_module) -> None:
        # F-16 dropped HOME isolation; I-19 dropped rate-status helpers.
        assert not hasattr(script_module, 'WB_HOME_DIR')
        assert not hasattr(script_module, 'WB_CONFIG_DIR')
        assert not hasattr(script_module, 'build_wb_env')
        assert not hasattr(script_module, 'SPEND_RELEVANT_ENDPOINTS')
        assert not hasattr(script_module, 'find_active_lock_for')
        assert not hasattr(script_module, 'read_rate_status')
