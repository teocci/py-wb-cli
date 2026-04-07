"""HTTP client for Wildberries API with retry and rate-limit handling."""

from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING, Any

import httpx

from wb.core.constants import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BASE_DELAY,
    DEFAULT_TIMEOUT,
)
from wb.core.exceptions import (
    ApiError,
    AuthenticationError,
    RateLimitError,
)

if TYPE_CHECKING:
    from wb.core.rate_limiter import RateLimiter

__all__ = ['WbHttpClient']

logger = logging.getLogger(__name__)

# Status codes that trigger retry
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# Jitter fraction applied to exponential backoff delay
_JITTER_FRACTION = 0.5


class WbHttpClient:
    """Low-level HTTP client for WB API with retry and rate-limit support.

    Supports optional per-path preemptive rate limiting via ``path_limiters``.
    When a limiter is registered for a path, :meth:`acquire` is called before
    the first attempt — preventing 429 responses rather than reacting to them.

    Attributes:
        base_url: API base URL.
        token: Bearer token for authentication.
    """

    def __init__(
            self,
            base_url: str,
            token: str,
            timeout: float = DEFAULT_TIMEOUT,
            max_retries: int = DEFAULT_MAX_RETRIES,
            retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY,
            path_limiters: dict[str, 'RateLimiter'] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip('/')
        self._token = token
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
        self._path_limiters: dict[str, RateLimiter] = path_limiters or {}
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                'Authorization': token,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            timeout=self._timeout,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> WbHttpClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def request(
            self,
            method: str,
            path: str,
            *,
            params: dict[str, Any] | None = None,
            json_body: Any | None = None,
    ) -> Any:
        """Make an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API endpoint path.
            params: Query parameters.
            json_body: JSON request body.

        Returns:
            Parsed JSON response body, or None for empty responses.

        Raises:
            AuthenticationError: On 401 responses.
            RateLimitError: On 429 after all retries exhausted.
            ApiError: On other non-success responses after retries.
        """
        last_exception: Exception | None = None

        if limiter := self._path_limiters.get(path):
            limiter.acquire()

        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.request(
                    method,
                    path,
                    params=params,
                    json=json_body,
                )
                return self._handle_response(response)
            except RateLimitError as exc:
                last_exception = exc
                self._retry_or_raise(
                    attempt, exc, exc.retry_after, 'Rate limited'
                )
            except ApiError as exc:
                if exc.status_code not in _RETRYABLE_STATUS_CODES:
                    raise
                last_exception = exc
                self._retry_or_raise(
                    attempt,
                    exc,
                    None,
                    f'Retryable error {exc.status_code}',
                )
            except httpx.TimeoutException as exc:
                last_exception = exc
                self._retry_or_raise(attempt, exc, None, 'Timeout')

        # Unreachable in normal flow, but satisfies the type checker
        raise ApiError(
            'Max retries exhausted',
            status_code=None,
            response_body=None,
        ) from last_exception

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        """HTTP GET request.

        Args:
            path: API endpoint path.
            params: Query parameters.

        Returns:
            Parsed JSON response body, or None for empty responses.
        """
        return self.request('GET', path, params=params)

    def post(
            self,
            path: str,
            *,
            params: dict[str, Any] | None = None,
            json_body: Any | None = None,
    ) -> Any:
        """HTTP POST request.

        Args:
            path: API endpoint path.
            params: Query parameters.
            json_body: JSON request body.

        Returns:
            Parsed JSON response body, or None for empty responses.
        """
        return self.request('POST', path, params=params, json_body=json_body)

    def put(
            self,
            path: str,
            *,
            params: dict[str, Any] | None = None,
            json_body: Any | None = None,
    ) -> Any:
        """HTTP PUT request.

        Args:
            path: API endpoint path.
            params: Query parameters.
            json_body: JSON request body.

        Returns:
            Parsed JSON response body, or None for empty responses.
        """
        return self.request('PUT', path, params=params, json_body=json_body)

    def patch(
            self,
            path: str,
            *,
            params: dict[str, Any] | None = None,
            json_body: Any | None = None,
    ) -> Any:
        """HTTP PATCH request.

        Args:
            path: API endpoint path.
            params: Query parameters.
            json_body: JSON request body.

        Returns:
            Parsed JSON response body, or None for empty responses.
        """
        return self.request('PATCH', path, params=params, json_body=json_body)

    def delete(
            self,
            path: str,
            *,
            params: dict[str, Any] | None = None,
            json_body: Any | None = None,
    ) -> Any:
        """HTTP DELETE request.

        Args:
            path: API endpoint path.
            params: Query parameters.
            json_body: JSON request body.

        Returns:
            Parsed JSON response body, or None for empty responses.
        """
        return self.request('DELETE', path, params=params, json_body=json_body)

    def request_raw(
            self,
            method: str,
            path: str,
            *,
            params: dict[str, Any] | None = None,
    ) -> bytes:
        """Make an HTTP request returning raw response bytes.

        Used for binary downloads (ZIP files, etc.). Reuses the
        same retry logic as ``request()``.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API endpoint path.
            params: Query parameters.

        Returns:
            Raw response content as bytes.

        Raises:
            AuthenticationError: On 401 responses.
            RateLimitError: On 429 after all retries exhausted.
            ApiError: On other non-success responses after retries.
        """
        last_exception: Exception | None = None

        if limiter := self._path_limiters.get(path):
            limiter.acquire()

        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.request(
                    method,
                    path,
                    params=params,
                    headers={'Accept': 'application/octet-stream'},
                )
                self._check_error_status(response)
                return response.content
            except RateLimitError as exc:
                last_exception = exc
                self._retry_or_raise(
                    attempt, exc, exc.retry_after, 'Rate limited'
                )
            except ApiError as exc:
                if exc.status_code not in _RETRYABLE_STATUS_CODES:
                    raise
                last_exception = exc
                self._retry_or_raise(
                    attempt, exc, None,
                    f'Retryable error {exc.status_code}',
                )
            except httpx.TimeoutException as exc:
                last_exception = exc
                self._retry_or_raise(attempt, exc, None, 'Timeout')

        raise ApiError(
            'Max retries exhausted',
            status_code=None,
            response_body=None,
        ) from last_exception

    def _check_error_status(self, response: httpx.Response) -> None:
        """Check response status and raise on errors.

        Args:
            response: The httpx Response object.

        Raises:
            AuthenticationError: On 401.
            RateLimitError: On 429.
            ApiError: On other error status codes.
        """
        if response.status_code == 401:
            raise AuthenticationError(
                'Authentication failed - check your API token'
            )
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After')
            retry_seconds = float(retry_after) if retry_after else None
            raise RateLimitError(
                'Rate limited by WB API',
                retry_after=retry_seconds,
            )
        if response.status_code >= 400:
            raise ApiError(
                f'WB API error: HTTP {response.status_code}',
                status_code=response.status_code,
                response_body=response.text,
            )

    def _retry_or_raise(
            self,
            attempt: int,
            exc: Exception,
            retry_after: float | None,
            label: str,
    ) -> None:
        """Sleep-and-retry if attempts remain, otherwise re-raise.

        Args:
            attempt: Zero-based attempt index.
            exc: The exception that triggered the retry.
            retry_after: Server-suggested wait time, if any.
            label: Short description for log messages.

        Raises:
            ApiError: When all retries are exhausted on a timeout.
            Exception: Re-raises the original exception when retries
                are exhausted.
        """
        if attempt >= self._max_retries:
            if isinstance(exc, httpx.TimeoutException):
                raise ApiError(
                    f'Request timed out after {self._max_retries + 1} attempts',
                    status_code=None,
                    response_body=None,
                ) from exc
            raise

        delay = retry_after or self._calculate_delay(attempt)
        logger.warning(
            '%s (attempt %d/%d), retrying in %.1fs',
            label,
            attempt + 1,
            self._max_retries + 1,
            delay,
        )
        time.sleep(delay)

    def _handle_response(self, response: httpx.Response) -> Any:
        """Process HTTP response, raising appropriate exceptions.

        Args:
            response: The httpx Response object.

        Returns:
            Parsed JSON body or None.

        Raises:
            AuthenticationError: On 401.
            RateLimitError: On 429.
            ApiError: On other error status codes.
        """
        self._check_error_status(response)

        if response.status_code == 204 or not response.content:
            return None

        return response.json()

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter.

        Args:
            attempt: Zero-based attempt index.

        Returns:
            Delay in seconds.
        """
        base = self._retry_base_delay * (2 ** attempt)
        jitter = random.uniform(0, base * _JITTER_FRACTION)  # noqa: S311
        return base + jitter
