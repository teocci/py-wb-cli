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
    UPSTREAM_RETRY_BASE_DELAY,
    UPSTREAM_RETRY_MULTIPLIER,
)
from wb.core.exceptions import (
    ApiError,
    AuthenticationError,
    RateLimitError,
    UpstreamError,
)

if TYPE_CHECKING:
    from wb.core.rate_limiter import RateLimiter

__all__ = ['WbHttpClient']

logger = logging.getLogger(__name__)

# Status codes that trigger retry (429 handled as RateLimitError separately).
_RETRYABLE_UPSTREAM_STATUS_CODES = frozenset({500, 502, 503, 504})
_RETRYABLE_STATUS_CODES = _RETRYABLE_UPSTREAM_STATUS_CODES | {429}

# Jitter fraction applied to exponential backoff delay
_JITTER_FRACTION = 0.5

# Substring in a WB 429 response body that identifies a seller-scope global
# throttle. WB's gateway returns HTTP 429 with a JSON body of the form
# ``{"title":"too many requests","detail":"Limited by global limiter, per
# seller <uuid>; See …"}``. When this string appears, the per-endpoint
# backoff (1/2/4 s) is too short because the seller-wide window needs
# multiple seconds to clear — we switch to the UPSTREAM schedule instead.
_SELLER_GLOBAL_THROTTLE_MARKER = 'global limiter'

# Undocumented headers WB sends on 429 (not in swagger). When present, the
# value is seconds until the cooldown window clears — authoritative, so we
# prefer it over the standard `Retry-After` fallback. Both header names
# carry the same value; we read whichever shows up.
_RATELIMIT_RESET_HEADERS = ('Retry-After', 'x-ratelimit-reset', 'x-ratelimit-retry')

# Threshold for F-12's bail-out vs. retry split. Any `retry_after` larger
# than this is almost certainly a seller-scope penalty — retrying would
# only extend WB's leaky-bucket cooldown. Values ≤ threshold represent
# genuine per-endpoint windows (e.g. fullstats 20 s, funnel 60 s) that
# retry successfully after one sleep.
_RETRY_AFTER_BAIL_OUT_SECONDS = 60.0


def _parse_rate_limit_reset(response: 'httpx.Response') -> float | None:
    """Return the first header value that parses as a positive number.

    Prefers ``Retry-After`` (the HTTP standard) but falls back to WB's
    undocumented ``x-ratelimit-reset`` / ``x-ratelimit-retry`` headers,
    which are what the gateway actually sends on seller-scope 429s.
    """
    for name in _RATELIMIT_RESET_HEADERS:
        raw = response.headers.get(name)
        if not raw:
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        if value > 0:
            return value
    return None


def _is_upstream_error(exc: Exception | None) -> bool:
    """True when ``exc`` is a retryable 5xx :class:`ApiError`."""
    return (
        isinstance(exc, ApiError)
        and exc.status_code in _RETRYABLE_UPSTREAM_STATUS_CODES
    )


def _is_seller_global_throttle(exc: Exception | None) -> bool:
    """True when ``exc`` is a 429 carrying WB's seller-scope throttle body."""
    if not isinstance(exc, RateLimitError):
        return False
    body = exc.response_body or ''
    return _SELLER_GLOBAL_THROTTLE_MARKER in body.lower()


class WbHttpClient:
    """Low-level HTTP client for WB API with retry and rate-limit support.

    Supports two layers of preemptive rate limiting, both acquired before
    the first attempt to prevent 429 responses rather than react to them:

    1. ``seller_limiter`` — acquired first, for every request. Coordinates
       against WB's gateway-enforced per-seller global budget across all
       advert + analytics endpoints for the seller, keyed by the JWT
       ``sid`` claim so tokens of the same seller share one window.
    2. ``path_limiters`` — acquired second, per endpoint path. Enforces
       the per-endpoint budgets documented in WB's swagger.

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
            seller_limiter: 'RateLimiter | None' = None,
    ) -> None:
        self._base_url = base_url.rstrip('/')
        self._token = token
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
        self._path_limiters: dict[str, RateLimiter] = path_limiters or {}
        self._seller_limiter: RateLimiter | None = seller_limiter
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

        if self._seller_limiter is not None:
            self._seller_limiter.acquire()
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

        if self._seller_limiter is not None:
            self._seller_limiter.acquire()
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
            retry_seconds = _parse_rate_limit_reset(response)
            raise RateLimitError(
                'Rate limited by WB API',
                retry_after=retry_seconds,
                response_body=response.text,
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

        On exhaustion, a retried 5xx ``ApiError`` is converted to
        :class:`UpstreamError` (exit 6) so callers can distinguish WB
        infrastructure stress from a 429 rate-limit event (exit 5).

        F-12 bail-out: when ``retry_after`` exceeds
        ``_RETRY_AFTER_BAIL_OUT_SECONDS`` (60 s), skip retries and
        re-raise immediately. A reset that large almost always signals
        a seller-scope penalty; retrying into it would only extend WB's
        leaky-bucket cooldown, so we let the caller see the real
        ``retry_after`` in the error JSON and move on.

        Args:
            attempt: Zero-based attempt index.
            exc: The exception that triggered the retry.
            retry_after: Server-suggested wait time, if any.
            label: Short description for log messages.

        Raises:
            ApiError: When all retries are exhausted on a timeout.
            UpstreamError: On exhausted retries of a 5xx response.
            Exception: Re-raises the original exception when retries
                are exhausted for non-5xx cases (e.g. 429).
        """
        if (
            retry_after is not None
            and retry_after > _RETRY_AFTER_BAIL_OUT_SECONDS
        ):
            logger.warning(
                '%s; cooldown too large to retry (reset=%.0fs > %.0fs), '
                'bailing out with retry_after=%.0f',
                label, retry_after, _RETRY_AFTER_BAIL_OUT_SECONDS, retry_after,
            )
            raise exc

        if attempt >= self._max_retries:
            if isinstance(exc, httpx.TimeoutException):
                raise ApiError(
                    f'Request timed out after {self._max_retries + 1} attempts',
                    status_code=None,
                    response_body=None,
                ) from exc
            if _is_upstream_error(exc):
                raise UpstreamError(
                    f'WB API upstream error after '
                    f'{self._max_retries + 1} attempts: HTTP {exc.status_code}',
                    status_code=exc.status_code,
                    response_body=exc.response_body,
                ) from exc
            raise

        delay = retry_after or self._calculate_delay(attempt, exc)
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

    def _calculate_delay(
            self,
            attempt: int,
            exc: Exception | None = None,
    ) -> float:
        """Calculate backoff delay with jitter, scaled by error class.

        Three schedules:

        - **Timeouts and per-endpoint 429s** use the standard exponential
          schedule (``retry_base_delay * 2^attempt`` ≈ 1 / 2 / 4 s).
        - **5xx upstream errors** and **seller-scope 429s** (WB gateway's
          ``"Limited by global limiter, per seller …"`` response) use the
          patient UPSTREAM schedule (``UPSTREAM_RETRY_BASE_DELAY *
          UPSTREAM_RETRY_MULTIPLIER^attempt`` ≈ 5 / 15 / 45 s). Both
          signals represent stress that rarely clears in a couple of
          seconds, so short retries just amplify the storm.

        A server-supplied ``Retry-After`` overrides this entirely — see
        :meth:`_retry_or_raise`.

        Args:
            attempt: Zero-based attempt index.
            exc: The exception that triggered the retry, used to pick
                the schedule. Defaults to the exponential schedule.

        Returns:
            Delay in seconds.
        """
        if _is_upstream_error(exc) or _is_seller_global_throttle(exc):
            base = UPSTREAM_RETRY_BASE_DELAY * (UPSTREAM_RETRY_MULTIPLIER ** attempt)
        else:
            base = self._retry_base_delay * (2 ** attempt)
        jitter = random.uniform(0, base * _JITTER_FRACTION)  # noqa: S311
        return base + jitter
