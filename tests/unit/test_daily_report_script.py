"""Tests for `scripts/generate_daily_wb_report.py` rate-limit handling (F-16)."""

from __future__ import annotations

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
            '"message":"Endpoint /api/advert/v2/adverts locked for ~3518s",'
            '"exit_code":5,"retry_after":3518.0}}'
        )
        with patch.object(
            script_module.subprocess, 'run',
            return_value=_FakeProc(5, stdout=envelope),
        ) as mock_run:
            with pytest.raises(script_module.RateLimitedError) as exc_info:
                script_module.run_wb_command(['wb', '--json', 'stats', 'product-spend'])

        assert exc_info.value.retry_after == 3518.0
        # No retry — single subprocess invocation only.
        assert mock_run.call_count == 1

    def test_exit_5_with_unparseable_stdout_raises_without_retry_after(
            self, script_module,
    ) -> None:
        with patch.object(
            script_module.subprocess, 'run',
            return_value=_FakeProc(5, stdout='not json'),
        ):
            with pytest.raises(script_module.RateLimitedError) as exc_info:
                script_module.run_wb_command(['wb', 'stats', 'product-spend'])

        assert exc_info.value.retry_after is None

    def test_exit_5_envelope_in_stderr_is_picked_up(
            self, script_module,
    ) -> None:
        # Human-mode CLI writes the envelope to stderr (no --json flag);
        # the helper still tries stderr as a fallback.
        envelope = (
            '{"status":"error","error":{"code":"RATE_LIMITED",'
            '"message":"locked","exit_code":5,"retry_after":120.0}}'
        )
        with patch.object(
            script_module.subprocess, 'run',
            return_value=_FakeProc(5, stdout='', stderr=envelope),
        ):
            with pytest.raises(script_module.RateLimitedError) as exc_info:
                script_module.run_wb_command(['wb', 'stats', 'product-spend'])

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
                script_module.run_wb_command(['wb', 'stats', 'product-spend'])

        assert exc_info.value.retry_after is None


class TestRunWbCommandSuccess:
    def test_exit_0_returns_parsed_payload(self, script_module) -> None:
        payload = '[{"nm_id":1,"title":"x","order_count":2}]'
        with patch.object(
            script_module.subprocess, 'run',
            return_value=_FakeProc(0, stdout=payload),
        ):
            result, raw = script_module.run_wb_command(['wb', 'analytics'])
        assert raw == payload
        assert result == [{'nm_id': 1, 'title': 'x', 'order_count': 2}]

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


class TestFindActiveLockFor:
    def test_filters_by_endpoint(self, script_module) -> None:
        status = {
            'sellers': [{
                'tokens': [{
                    'endpoints': [
                        {
                            'endpoint': '/api/advert/v2/adverts',
                            'locked': True,
                            'reset_in_s': 1800.0,
                        },
                        {
                            'endpoint': '/some/other/path',
                            'locked': True,
                            'reset_in_s': 60.0,
                        },
                    ],
                }],
            }],
        }
        is_locked, cooldown, ep = script_module.find_active_lock_for(
            status, endpoints=script_module.SPEND_RELEVANT_ENDPOINTS,
        )
        assert is_locked is True
        assert cooldown == 1800.0
        assert ep == '/api/advert/v2/adverts'

    def test_unrelated_lock_ignored(self, script_module) -> None:
        status = {
            'sellers': [{
                'tokens': [{
                    'endpoints': [{
                        'endpoint': '/api/v3/sales-funnel/products',
                        'locked': True,
                        'reset_in_s': 1800.0,
                    }],
                }],
            }],
        }
        is_locked, cooldown, ep = script_module.find_active_lock_for(
            status, endpoints=script_module.SPEND_RELEVANT_ENDPOINTS,
        )
        assert is_locked is False
        assert ep is None

    def test_none_endpoints_matches_any(self, script_module) -> None:
        status = {
            'sellers': [{
                'tokens': [{
                    'endpoints': [{
                        'endpoint': '/anything',
                        'locked': True,
                        'reset_in_s': 100.0,
                    }],
                }],
            }],
        }
        is_locked, cooldown, ep = script_module.find_active_lock_for(
            status, endpoints=None,
        )
        assert is_locked is True
        assert ep == '/anything'

    def test_returns_longest_lock(self, script_module) -> None:
        status = {
            'sellers': [{
                'tokens': [{
                    'endpoints': [
                        {
                            'endpoint': '/adv/v3/fullstats',
                            'locked': True,
                            'reset_in_s': 600.0,
                        },
                        {
                            'endpoint': '/api/advert/v2/adverts',
                            'locked': True,
                            'reset_in_s': 3500.0,
                        },
                    ],
                }],
            }],
        }
        _, cooldown, ep = script_module.find_active_lock_for(
            status, endpoints=script_module.SPEND_RELEVANT_ENDPOINTS,
        )
        assert cooldown == 3500.0
        assert ep == '/api/advert/v2/adverts'

    def test_unlocked_endpoints_dont_count(self, script_module) -> None:
        status = {
            'sellers': [{
                'tokens': [{
                    'endpoints': [{
                        'endpoint': '/api/advert/v2/adverts',
                        'locked': False,
                        'reset_in_s': 100.0,
                    }],
                }],
            }],
        }
        is_locked, _, _ = script_module.find_active_lock_for(
            status, endpoints=script_module.SPEND_RELEVANT_ENDPOINTS,
        )
        assert is_locked is False

    def test_empty_status_returns_unlocked(self, script_module) -> None:
        is_locked, cooldown, ep = script_module.find_active_lock_for(
            {}, endpoints=script_module.SPEND_RELEVANT_ENDPOINTS,
        )
        assert is_locked is False
        assert cooldown == 0.0
        assert ep is None


class TestRateLimitedError:
    def test_carries_retry_after(self, script_module) -> None:
        exc = script_module.RateLimitedError('locked', retry_after=3500.0)
        assert exc.retry_after == 3500.0
        assert 'locked' in str(exc)

    def test_retry_after_optional(self, script_module) -> None:
        exc = script_module.RateLimitedError('locked')
        assert exc.retry_after is None


class TestSpendRelevantEndpoints:
    def test_contains_expected_endpoints(self, script_module) -> None:
        # F-16: the script's mid-run check scopes to these.
        assert '/api/advert/v2/adverts' in script_module.SPEND_RELEVANT_ENDPOINTS
        assert '/adv/v3/fullstats' in script_module.SPEND_RELEVANT_ENDPOINTS

    def test_does_not_include_funnel(self, script_module) -> None:
        # Sales-funnel locks shouldn't abort the spend phase.
        assert (
            '/api/analytics/v3/sales-funnel/products'
            not in script_module.SPEND_RELEVANT_ENDPOINTS
        )


class TestNoHomeIsolation:
    def test_no_home_isolation_constants(self, script_module) -> None:
        # F-16 dropped HOME isolation. These names should no longer
        # exist on the module.
        assert not hasattr(script_module, 'WB_HOME_DIR')
        assert not hasattr(script_module, 'WB_CONFIG_DIR')
        assert not hasattr(script_module, 'build_wb_env')
