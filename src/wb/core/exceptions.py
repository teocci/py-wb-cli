"""Custom exception hierarchy for the WB CLI.

All application-specific exceptions inherit from WbCliError, which
carries an exit code so the CLI entry point can translate failures
into appropriate process return codes.
"""

__all__ = [
    'WbCliError',
    'ValidationError',
    'AuthenticationError',
    'AuthorizationError',
    'RateLimitError',
    'ApiError',
    'ConfigError',
]

from wb.core.constants import ExitCode


class WbCliError(Exception):
    """Base exception for all WB CLI errors.

    Attributes:
        message: Human-readable error description.
        exit_code: Process exit code associated with this error.
        error_code: Machine-readable error code for programmatic matching.
    """

    error_code: str = 'CLI_ERROR'

    def __init__(
            self,
            message: str,
            exit_code: ExitCode = ExitCode.API_ERROR,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code

    def to_dict(self) -> dict:
        """Serialize to a structured error dict for JSON output."""
        return {
            'status': 'error',
            'error': {
                'code': self.error_code,
                'message': self.message,
                'exit_code': int(self.exit_code),
            },
        }


class ValidationError(WbCliError):
    """Raised when input validation fails."""

    error_code: str = 'VALIDATION_ERROR'

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=ExitCode.VALIDATION_ERROR)


class AuthenticationError(WbCliError):
    """Raised when authentication credentials are invalid or expired."""

    error_code: str = 'AUTH_FAILURE'

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=ExitCode.AUTH_FAILURE)


class AuthorizationError(WbCliError):
    """Raised when the token lacks a required permission scope."""

    error_code: str = 'AUTH_MISSING_SCOPE'

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=ExitCode.AUTH_MISSING_SCOPE)


class RateLimitError(WbCliError):
    """Raised when the API rate limit is exceeded.

    Attributes:
        retry_after: Seconds to wait before retrying, if provided by the API.
    """

    error_code: str = 'RATE_LIMITED'

    def __init__(
            self,
            message: str,
            retry_after: float | None = None,
    ) -> None:
        super().__init__(message, exit_code=ExitCode.RATE_LIMITED)
        self.retry_after = retry_after

    def to_dict(self) -> dict:
        """Serialize with retry_after hint."""
        result = super().to_dict()
        if self.retry_after is not None:
            result['error']['retry_after'] = self.retry_after
        return result


class ApiError(WbCliError):
    """Raised on a general API error response.

    Attributes:
        status_code: HTTP status code returned by the API.
        response_body: Raw response body text, if available.
    """

    error_code: str = 'API_ERROR'

    def __init__(
            self,
            message: str,
            status_code: int | None = None,
            response_body: str | None = None,
    ) -> None:
        super().__init__(message, exit_code=ExitCode.API_ERROR)
        self.status_code = status_code
        self.response_body = response_body

    def to_dict(self) -> dict:
        """Serialize with HTTP status code."""
        result = super().to_dict()
        if self.status_code is not None:
            result['error']['status_code'] = self.status_code
        return result


class ConfigError(WbCliError):
    """Raised on configuration file or value errors."""

    error_code: str = 'CONFIG_ERROR'

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=ExitCode.CONFIG_ERROR)
