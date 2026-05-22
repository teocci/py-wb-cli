"""HTTP client for WB Seller Portal endpoints.

Portal auth requires both cookie + authorizev3 headers together.
Neither works alone. The wb-seller-lk session token is optional.
See wb_portal_authentication_notes.md for test results.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from wb.core.constants import (
    EP_PORTAL_AUTH_TOKEN,
    EP_PORTAL_BIDS,
    EP_PORTAL_BIDS_CPC,
    EP_PORTAL_TABLE_LIST,
    EP_PORTAL_TOKENS_JRPC,
    PORTAL_AUTH_HEADER,
    SELLER_CONTENT_BASE_URL,
    SELLER_PORTAL_BASE_URL,
    WB_CMP_BASE_URL,
)
from wb.core.exceptions import ApiError, AuthenticationError, ValidationError
from wb.domain.enums import PaymentType

__all__ = ['PortalClient', 'PortalSession']

logger = logging.getLogger(__name__)

_DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/146.0.0.0 Safari/537.36'
)

_JRPC_ID_PREFIX = 'json-rpc'

# Default page size for product list
_DEFAULT_PRODUCT_PAGE_SIZE = 20


@dataclass(slots=True)
class PortalSession:
    """Session data returned by portal authentication.

    Attributes:
        token: Session JWT (short-lived, ~5 min).
        user_id: Seller user ID.
        exp: Token expiration timestamp (Unix epoch).
    """

    token: str
    user_id: int
    exp: int


class PortalClient:
    """Client for WB Seller Portal endpoints.

    Requires both authorizev3 and cookie for authentication.
    See wb_portal_authentication_notes.md for auth test results.

    Attributes:
        authorizev3: The authorizev3 header value from browser.
        cookie: The browser cookie string (required).
    """

    def __init__(
            self,
            authorizev3: str,
            cookie: str,
            timeout: float = 30.0,
    ) -> None:
        if not cookie:
            raise ValidationError(
                'Portal cookie is required. Both cookie and authorizev3 '
                'are needed for portal authentication.'
            )
        self._authorizev3 = authorizev3
        self._cookie = cookie
        self._timeout = timeout
        self._jrpc_counter = 0

    def authenticate(self) -> PortalSession:
        """Validate credentials by calling the portal auth endpoint.

        Returns:
            PortalSession with session JWT, user ID, and expiration.

        Raises:
            AuthenticationError: If portal rejects the credentials.
            ApiError: If the response format is unexpected.
        """
        payload = self._build_jrpc_payload(params={})
        response = self._post(
            SELLER_PORTAL_BASE_URL,
            EP_PORTAL_AUTH_TOKEN,
            payload,
        )
        return self._parse_auth_response(response)

    def generate_token(self) -> str:
        """Generate a render token via the portal JRPC endpoint.

        Returns:
            The generated token string (412 chars, alphanumeric).

        Raises:
            AuthenticationError: If credentials are invalid or expired.
            ApiError: If the response format is unexpected.
        """
        payload = self._build_jrpc_payload(
            method='generateToken',
            params={'team': 'render'},
        )
        response = self._post(
            SELLER_CONTENT_BASE_URL,
            EP_PORTAL_TOKENS_JRPC,
            payload,
        )
        return self._parse_token_response(response)

    def list_products(
            self,
            page_size: int = _DEFAULT_PRODUCT_PAGE_SIZE,
            search: str = '',
    ) -> list[dict[str, Any]]:
        """Fetch product cards from the seller portal.

        Args:
            page_size: Number of products per page.
            search: Optional search query to filter products.

        Returns:
            List of raw product card dicts from the portal.

        Raises:
            AuthenticationError: If credentials are invalid or expired.
            ApiError: If the response format is unexpected.
        """
        payload = {
            'sort': [{'columnID': 11, 'order': 'desc'}],
            'filter': {'search': search, 'paidOptions': {}},
            'cursor': {'n': page_size},
        }
        response = self._post(
            SELLER_CONTENT_BASE_URL,
            EP_PORTAL_TABLE_LIST,
            payload,
        )
        return self._parse_products_response(response)

    def fetch_bid_recommendations(
            self,
            nm_ids: list[int],
            payment_type: PaymentType | str,
            bid_type: int,
    ) -> dict[str, Any] | list[Any]:
        """Fetch bid recommendations from the campaign-management portal.

        Picks endpoint by ``payment_type`` — CPC hits ``/bids-cpc``
        (placement-split response), CPM hits ``/bids`` (flat list).
        Both shapes are returned as-is; the caller normalizes via
        :func:`wb.domain.models.parse_portal_bids_response`.

        Args:
            nm_ids: NM IDs to query (passed as a comma-separated ``nms`` param).
            payment_type: ``'cpm'`` or ``'cpc'``.
            bid_type: New-typology bid mode — ``1`` (manual) or ``2`` (unified).

        Returns:
            Raw response body. For CPC: ``{'recommendations': [...], 'search': [...]}``.
            For CPM: a flat list of per-NM dicts.

        Raises:
            ValidationError: When ``nm_ids`` is empty.
            AuthenticationError: When the portal rejects the credentials.
            ApiError: For other non-2xx responses or invalid JSON.
        """
        if not nm_ids:
            raise ValidationError('fetch_bid_recommendations: nm_ids is empty')
        pt_value = payment_type.value if isinstance(payment_type, PaymentType) else str(payment_type).lower()
        params: dict[str, str] = {
            'nms': ','.join(str(n) for n in nm_ids),
            'bid_type': str(bid_type),
        }
        if pt_value == PaymentType.CPC.value:
            path = EP_PORTAL_BIDS_CPC
        else:
            path = EP_PORTAL_BIDS
            params['payment_type'] = pt_value
        return self._get(WB_CMP_BASE_URL, path, params)

    def _build_jrpc_payload(
            self,
            params: dict[str, Any],
            method: str | None = None,
    ) -> dict[str, Any]:
        """Build a JSON-RPC 2.0 request payload."""
        self._jrpc_counter += 1
        payload: dict[str, Any] = {
            'params': params,
            'jsonrpc': '2.0',
            'id': f'{_JRPC_ID_PREFIX}_{self._jrpc_counter}',
        }
        if method:
            payload['method'] = method
        return payload

    def _build_headers(
            self,
            origin: str = SELLER_PORTAL_BASE_URL,
            referer: str | None = None,
    ) -> dict[str, str]:
        """Build request headers with cookie + authorizev3.

        Args:
            origin: Origin host for the request. Defaults to the seller portal.
                Pass ``WB_CMP_BASE_URL`` for cmp endpoints.
            referer: Optional referer override. Defaults to ``f'{origin}/'``.
        """
        return {
            PORTAL_AUTH_HEADER: self._authorizev3,
            'cookie': self._cookie,
            'content-type': 'application/json',
            'accept': '*/*',
            'origin': origin,
            'referer': referer or f'{origin}/',
            'user-agent': _DEFAULT_USER_AGENT,
        }

    def _post(
            self,
            base_url: str,
            path: str,
            payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Make a POST request to a portal endpoint.

        Args:
            base_url: Portal base URL.
            path: Endpoint path.
            payload: JSON body.

        Returns:
            Parsed JSON response.

        Raises:
            AuthenticationError: On 401/403 responses.
            ApiError: On other errors or invalid responses.
        """
        url = f'{base_url}{path}'
        headers = self._build_headers()

        try:
            response = httpx.post(
                url, json=payload, headers=headers, timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise ApiError(
                f'Portal request failed: {exc}',
                status_code=None,
                response_body=None,
            ) from exc

        if response.status_code in (401, 403):
            raise AuthenticationError(
                f'Portal authentication failed (HTTP {response.status_code}). '
                'Credentials may have expired — refresh from browser DevTools.'
            )

        if response.status_code >= 400:
            raise ApiError(
                f'Portal error: HTTP {response.status_code}',
                status_code=response.status_code,
                response_body=response.text,
            )

        try:
            return response.json()
        except ValueError as exc:
            raise ApiError(
                'Portal returned invalid JSON',
                status_code=response.status_code,
                response_body=response.text,
            ) from exc

    def _get(
            self,
            base_url: str,
            path: str,
            params: dict[str, str],
    ) -> dict[str, Any] | list[Any]:
        """Make a GET request to a portal endpoint.

        Args:
            base_url: Portal base URL.
            path: Endpoint path.
            params: Query parameters.

        Returns:
            Parsed JSON response — may be a dict or list depending on endpoint.

        Raises:
            AuthenticationError: On 401/403 responses.
            ApiError: On other errors or invalid responses.
        """
        url = f'{base_url}{path}'
        headers = self._build_headers(origin=base_url)

        try:
            response = httpx.get(
                url, params=params, headers=headers, timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise ApiError(
                f'Portal request failed: {exc}',
                status_code=None,
                response_body=None,
            ) from exc

        if response.status_code in (401, 403):
            raise AuthenticationError(
                f'Portal authentication failed (HTTP {response.status_code}). '
                'Credentials may have expired — refresh from browser DevTools.'
            )

        if response.status_code >= 400:
            raise ApiError(
                f'Portal error: HTTP {response.status_code}',
                status_code=response.status_code,
                response_body=response.text,
            )

        try:
            return response.json()
        except ValueError as exc:
            raise ApiError(
                'Portal returned invalid JSON',
                status_code=response.status_code,
                response_body=response.text,
            ) from exc

    @staticmethod
    def _parse_auth_response(data: dict[str, Any]) -> PortalSession:
        """Parse the auth/token JRPC response into a PortalSession."""
        try:
            result_data = data['result']['data']
            return PortalSession(
                token=result_data['token'],
                user_id=result_data['userID'],
                exp=result_data['exp'],
            )
        except (KeyError, TypeError) as exc:
            raise ApiError(
                f'Unexpected portal auth response format: {data}',
                status_code=None,
                response_body=str(data),
            ) from exc

    @staticmethod
    def _parse_token_response(data: dict[str, Any]) -> str:
        """Parse the generateToken JRPC response."""
        try:
            return data['result']['token']
        except (KeyError, TypeError) as exc:
            raise ApiError(
                f'Unexpected token generation response format: {data}',
                status_code=None,
                response_body=str(data),
            ) from exc

    @staticmethod
    def _parse_products_response(data: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse the tableListv6 response into a list of product cards."""
        try:
            return data.get('data', {}).get('cards', [])
        except (AttributeError, TypeError) as exc:
            raise ApiError(
                f'Unexpected product list response format: {data}',
                status_code=None,
                response_body=str(data),
            ) from exc
