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
    """

    def __init__(
            self,
            message: str,
            exit_code: ExitCode = ExitCode.API_ERROR,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


class ValidationError(WbCliError):
    """Raised when input validation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=ExitCode.VALIDATION_ERROR)


class AuthenticationError(WbCliError):
    """Raised when authentication credentials are invalid or expired."""

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=ExitCode.AUTH_FAILURE)


class AuthorizationError(WbCliError):
    """Raised when the token lacks a required permission scope."""

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=ExitCode.AUTH_MISSING_SCOPE)


class RateLimitError(WbCliError):
    """Raised when the API rate limit is exceeded.

    Attributes:
        retry_after: Seconds to wait before retrying, if provided by the API.
    """

    def __init__(
            self,
            message: str,
            retry_after: float | None = None,
    ) -> None:
        super().__init__(message, exit_code=ExitCode.RATE_LIMITED)
        self.retry_after = retry_after


class ApiError(WbCliError):
    """Raised on a general API error response.

    Attributes:
        status_code: HTTP status code returned by the API.
        response_body: Raw response body text, if available.
    """

    def __init__(
            self,
            message: str,
            status_code: int | None = None,
            response_body: str | None = None,
    ) -> None:
        super().__init__(message, exit_code=ExitCode.API_ERROR)
        self.status_code = status_code
        self.response_body = response_body


class ConfigError(WbCliError):
    """Raised on configuration file or value errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=ExitCode.CONFIG_ERROR)
