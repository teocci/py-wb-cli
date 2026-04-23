"""Tests for wb.core.exceptions module."""

import pytest

from wb.core.constants import ExitCode
from wb.core.exceptions import (
    ApiError,
    AuthenticationError,
    ConfigError,
    RateLimitError,
    UpstreamError,
    ValidationError,
    WbCliError,
)


class TestWbCliError:
    """Tests for the base WbCliError exception."""

    def test_stores_message(self) -> None:
        err = WbCliError('something went wrong')
        assert err.message == 'something went wrong'
        assert str(err) == 'something went wrong'

    def test_default_exit_code(self) -> None:
        err = WbCliError('oops')
        assert err.exit_code == ExitCode.API_ERROR

    def test_custom_exit_code(self) -> None:
        err = WbCliError('bad config', exit_code=ExitCode.CONFIG_ERROR)
        assert err.exit_code == ExitCode.CONFIG_ERROR

    def test_is_exception(self) -> None:
        assert issubclass(WbCliError, Exception)


class TestValidationError:
    """Tests for ValidationError."""

    def test_exit_code(self) -> None:
        err = ValidationError('invalid input')
        assert err.exit_code == ExitCode.VALIDATION_ERROR

    def test_message(self) -> None:
        err = ValidationError('field is required')
        assert err.message == 'field is required'


class TestAuthenticationError:
    """Tests for AuthenticationError."""

    def test_exit_code(self) -> None:
        err = AuthenticationError('token expired')
        assert err.exit_code == ExitCode.AUTH_FAILURE


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_exit_code(self) -> None:
        err = RateLimitError('slow down')
        assert err.exit_code == ExitCode.RATE_LIMITED

    def test_stores_retry_after(self) -> None:
        err = RateLimitError('slow down', retry_after=30.0)
        assert err.retry_after == 30.0

    def test_retry_after_defaults_to_none(self) -> None:
        err = RateLimitError('slow down')
        assert err.retry_after is None


class TestApiError:
    """Tests for ApiError."""

    def test_exit_code(self) -> None:
        err = ApiError('server error')
        assert err.exit_code == ExitCode.API_ERROR

    def test_stores_status_code(self) -> None:
        err = ApiError('not found', status_code=404)
        assert err.status_code == 404

    def test_stores_response_body(self) -> None:
        body = '{"error": "not found"}'
        err = ApiError('not found', status_code=404, response_body=body)
        assert err.response_body == body

    def test_defaults_to_none(self) -> None:
        err = ApiError('fail')
        assert err.status_code is None
        assert err.response_body is None


class TestUpstreamError:
    """Tests for UpstreamError (retried 5xx exhaustion)."""

    def test_is_api_error_subclass(self) -> None:
        assert issubclass(UpstreamError, ApiError)

    def test_exit_code_matches_api_error(self) -> None:
        err = UpstreamError('bad gateway', status_code=502)
        assert err.exit_code == ExitCode.API_ERROR

    def test_error_code_is_upstream(self) -> None:
        err = UpstreamError('bad gateway', status_code=502)
        assert err.error_code == 'UPSTREAM_ERROR'
        assert err.to_dict()['error']['code'] == 'UPSTREAM_ERROR'

    def test_stores_status_code(self) -> None:
        err = UpstreamError('timeout', status_code=504, response_body='<html/>')
        assert err.status_code == 504
        assert err.response_body == '<html/>'


class TestConfigError:
    """Tests for ConfigError."""

    def test_exit_code(self) -> None:
        err = ConfigError('missing config file')
        assert err.exit_code == ExitCode.CONFIG_ERROR


class TestExceptionChaining:
    """Tests for exception chaining with raise ... from."""

    def test_chaining_preserves_cause(self) -> None:
        original = ValueError('original cause')
        with pytest.raises(WbCliError) as exc_info:
            try:
                raise original
            except ValueError as e:
                raise WbCliError('wrapped') from e
        assert exc_info.value.__cause__ is original

    def test_chaining_with_subclass(self) -> None:
        original = ConnectionError('network down')
        with pytest.raises(ApiError) as exc_info:
            try:
                raise original
            except ConnectionError as e:
                raise ApiError('api unreachable', status_code=503) from e
        assert exc_info.value.__cause__ is original
        assert exc_info.value.status_code == 503
