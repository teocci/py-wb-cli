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
    DOWNLOADS_CONTENT_ANALYTICS_BASE_URL,
    EP_PORTAL_AUTH_TOKEN,
    EP_PORTAL_BIDS,
    EP_PORTAL_BIDS_CPC,
    EP_PORTAL_JAM_DOWNLOADS,
    EP_PORTAL_JAM_FILE,
    EP_PORTAL_JAM_GENERATE,
    EP_PORTAL_SALES_REPORT_GENERATE,
    EP_PORTAL_SALES_REPORT_LIST,
    EP_PORTAL_SALES_REPORT_XLSX,
    EP_PORTAL_TABLE_LIST,
    EP_PORTAL_TOKENS_JRPC,
    EP_PORTAL_UPD_LIST,
    EP_PORTAL_UPD_XLSX,
    PORTAL_AUTH_HEADER,
    SELLER_CONTENT_BASE_URL,
    SELLER_PORTAL_BASE_URL,
    SELLER_WEEKLY_REPORT_BASE_URL,
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

    def generate_token(self, team: str = 'render') -> str:
        """Mint a portal token via the ``tokensjrpc`` JRPC endpoint.

        The same JRPC method serves multiple "teams" — each returns a token
        scoped for one downstream service. Known teams:

        - ``render`` (default, legacy use-case): 412-char alphanumeric render token.
        - ``content-analytics``: base64 ``{expiresAt, encryptedPart}`` token used as
          the ``x-download-token`` header by the WB Джем (Jam) downloads CDN.

        Args:
            team: The token "team" to request.

        Returns:
            The minted token string. Shape depends on ``team``.

        Raises:
            AuthenticationError: If credentials are invalid or expired.
            ApiError: If the response format is unexpected or the team is unknown.
        """
        payload = self._build_jrpc_payload(
            method='generateToken',
            params={'team': team},
        )
        response = self._post(
            SELLER_CONTENT_BASE_URL,
            EP_PORTAL_TOKENS_JRPC,
            payload,
        )
        return self._parse_token_response(response)

    def generate_download_token(self) -> str:
        """Mint the short-lived ``x-download-token`` for the Jam downloads CDN.

        Convenience wrapper for :meth:`generate_token` with ``team='content-analytics'``.
        The token is required by ``downloads-content-analytics.wildberries.ru`` and
        expires after a few minutes — mint just-in-time before each download.
        """
        return self.generate_token(team='content-analytics')

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

    def generate_jam_report(
            self,
            report_id: str,
            report_type: str,
            params: dict[str, Any],
            *,
            user_report_name: str = '',
    ) -> dict[str, Any]:
        """Trigger generation of a WB Джем (Jam) report.

        The caller picks ``report_id`` (a UUID) so the same id can later be
        matched against the ``downloads`` list during polling.

        Args:
            report_id: Client-generated UUID for this report instance.
            report_type: WB report-type slug (e.g. ``SEARCH_QUERIES_REPORT``).
            params: Report-specific parameters (date range, filters, sort).
            user_report_name: Optional display name; empty string by default.

        Returns:
            Parsed JSON — expected shape ``{'data': 'Created', 'error': false, ...}``.
        """
        payload = {
            'id': report_id,
            'userReportName': user_report_name,
            'reportType': report_type,
            'params': params,
        }
        return self._post(
            SELLER_CONTENT_BASE_URL,
            EP_PORTAL_JAM_GENERATE,
            payload,
        )

    def list_jam_reports(self, report_type: str) -> list[dict[str, Any]]:
        """List Jam reports of a given type that WB has queued or generated.

        Args:
            report_type: WB report-type slug to filter by.

        Returns:
            List of raw ``downloads[]`` entries (may be empty).
        """
        response = self._get(
            SELLER_CONTENT_BASE_URL,
            EP_PORTAL_JAM_DOWNLOADS,
            {'report_types': report_type},
        )
        if not isinstance(response, dict):
            return []
        data = response.get('data') or {}
        downloads = data.get('downloads') or []
        return [d for d in downloads if isinstance(d, dict)]

    def download_jam_file(self, report_id: str) -> bytes:
        """Fetch the binary ZIP for a generated Jam report.

        Two-step on the WB side:

        1. Mint a short-lived ``x-download-token`` via the portal JRPC tokens
           endpoint (``team='content-analytics'``).
        2. GET the file from ``downloads-content-analytics.wildberries.ru`` with
           that token + the session cookie (no ``authorizev3`` on this host).

        Args:
            report_id: The same UUID passed to :meth:`generate_jam_report`.

        Returns:
            Raw ZIP bytes; caller writes to disk.
        """
        download_token = self.generate_download_token()
        return self._get_bytes(
            DOWNLOADS_CONTENT_ANALYTICS_BASE_URL,
            f'{EP_PORTAL_JAM_FILE}/{report_id}',
            download_token=download_token,
            include_auth=False,
        )

    def generate_sales_report(
            self,
            report_type: str,
            from_dd_mm_yy: str,
            to_dd_mm_yy: str,
    ) -> dict[str, Any]:
        """Request generation of a sales report on the seller-weekly-report host.

        The POST has no body — the date range is passed as ``dateFrom`` /
        ``dateTo`` query-string params (DD.MM.YY format per the captured trace).

        Args:
            report_type: WB report-type slug (e.g. ``'supplier-goods'``).
            from_dd_mm_yy: Range start formatted as ``DD.MM.YY``.
            to_dd_mm_yy: Range end formatted as ``DD.MM.YY``.

        Returns:
            Parsed JSON response — expected shape ``{'data': {...}, 'error': false}``.

        Raises:
            AuthenticationError: On 401/403 responses.
            ApiError: On other non-2xx responses or invalid JSON.
        """
        path = f'{EP_PORTAL_SALES_REPORT_GENERATE}/{report_type}/order'
        return self._post(
            SELLER_WEEKLY_REPORT_BASE_URL,
            path,
            payload=None,
            params={'dateFrom': from_dd_mm_yy, 'dateTo': to_dd_mm_yy},
        )

    def list_sales_reports(self, report_type: str) -> list[dict[str, Any]]:
        """List sales reports of ``report_type`` known to WB.

        Args:
            report_type: WB report-type slug (e.g. ``'supplier-goods'``).

        Returns:
            List of raw report dicts (may be empty).
        """
        path = f'{EP_PORTAL_SALES_REPORT_LIST}/{report_type}/orders'
        response = self._get(
            SELLER_WEEKLY_REPORT_BASE_URL,
            path,
            params={},
            origin=SELLER_PORTAL_BASE_URL,
        )
        if not isinstance(response, dict):
            return []
        data = response.get('data') or []
        return [d for d in data if isinstance(d, dict)]

    def try_download_sales_report_xlsx(
            self,
            report_type: str,
            report_id: str,
    ) -> bytes | None:
        """Attempt to download a sales-report xlsx; return ``None`` if pending.

        The endpoint returns a JSON envelope ``{data, error, errorText}`` rather
        than raw bytes — the xlsx is base64-encoded inside ``data``. Successful
        readiness is ``error=false`` AND a non-empty ``data`` string. Anything
        else (``error=true``, empty ``data``) is treated as "still generating".

        Args:
            report_type: WB report-type slug (e.g. ``'supplier-goods'``).
            report_id: The id returned by :meth:`generate_sales_report`.

        Returns:
            Decoded xlsx bytes on success, ``None`` while pending.

        Raises:
            AuthenticationError: On 401/403 responses.
            ApiError: On other non-2xx responses, invalid JSON, or undecodable
                base64.
        """
        import base64
        import binascii

        path = f'{EP_PORTAL_SALES_REPORT_XLSX}/{report_type}/xlsx/{report_id}'
        response = self._get(
            SELLER_WEEKLY_REPORT_BASE_URL,
            path,
            params={},
            origin=SELLER_PORTAL_BASE_URL,
        )
        if not isinstance(response, dict):
            return None
        if response.get('error'):
            return None
        encoded = response.get('data')
        if not encoded or not isinstance(encoded, str):
            return None
        try:
            return base64.b64decode(encoded, validate=False)
        except (binascii.Error, ValueError) as exc:
            raise ApiError(
                f'Sales-report xlsx base64 decode failed: {exc}',
                status_code=None,
                response_body=encoded[:200],
            ) from exc

    def list_campaign_finance(
            self,
            from_dt: str,
            to_dt: str,
            *,
            page_number: int = 1,
            page_size: int = 100,
            bid_type: str = '[0]',
            attribute: str = 'all',
    ) -> dict[str, Any]:
        """Fetch one page of the campaign expense ledger (``/api/v6/upd``).

        Args:
            from_dt: Range start as ISO-8601 with MSK offset
                (e.g. ``'2026-05-11T00:00:00+03:00'``).
            to_dt: Range end (inclusive end-of-day per WB semantics — pass
                the start-of-day for that calendar day).
            page_number: 1-indexed page number.
            page_size: Rows per page.
            bid_type: Bid-type filter — ``'[0]'`` (default) returns all types.
            attribute: WB's catch-all filter — ``'all'`` matches the UI default.

        Returns:
            Raw response ``{upd_total_amount, total_count, upd_info[]}``.

        Raises:
            AuthenticationError: On 401/403.
            ApiError: On other non-2xx responses or invalid JSON.
        """
        params = {
            'page_number': str(page_number),
            'page_size': str(page_size),
            'bid_type': bid_type,
            'attribute': attribute,
            'from': from_dt,
            'to': to_dt,
        }
        response = self._get(
            WB_CMP_BASE_URL,
            EP_PORTAL_UPD_LIST,
            params,
            origin=WB_CMP_BASE_URL,
            referer=f'{WB_CMP_BASE_URL}/campaigns/finances',
        )
        if not isinstance(response, dict):
            raise ApiError(
                f'Unexpected /api/v6/upd payload type: {type(response).__name__}',
                status_code=None,
                response_body=None,
            )
        return response

    def download_campaign_finance_xlsx(
            self,
            from_dt: str,
            to_dt: str,
            *,
            page_size: int = 10,
            bid_type: str = '[0]',
    ) -> bytes:
        """Download the full campaign-finance ledger as an xlsx workbook.

        The xlsx endpoint always returns every row for the date range — the
        ``pageNumber``/``pageSize`` params are vestigial (the UI sends 1/10).
        We match the UI value to stay close to the captured trace.

        Args:
            from_dt: Range start as ISO-8601 with MSK offset.
            to_dt: Range end (inclusive end-of-day per WB semantics).
            page_size: Vestigial; passed through unchanged.
            bid_type: Bid-type filter (default ``'[0]'`` = all).

        Returns:
            Raw xlsx bytes; caller writes to disk.

        Raises:
            AuthenticationError: On 401/403.
            ApiError: On other non-2xx responses.
        """
        params = {
            'bid_type': bid_type,
            'from': from_dt,
            'to': to_dt,
            'pageNumber': '1',
            'pageSize': str(page_size),
        }
        return self._get_bytes(
            WB_CMP_BASE_URL,
            EP_PORTAL_UPD_XLSX,
            params=params,
            origin=WB_CMP_BASE_URL,
            referer=f'{WB_CMP_BASE_URL}/campaigns/finances',
        )

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
            payload: dict[str, Any] | None = None,
            *,
            params: dict[str, str] | None = None,
            origin: str | None = None,
            referer: str | None = None,
    ) -> dict[str, Any]:
        """Make a POST request to a portal endpoint.

        Args:
            base_url: Portal base URL.
            path: Endpoint path.
            payload: JSON body. When ``None``, the request is sent with
                ``Content-Length: 0`` — used by the sales-report generate
                endpoint where the date range lives in the query string.
            params: Optional query-string parameters.
            origin: Override ``Origin`` header (defaults to seller portal).
            referer: Override ``Referer`` header.

        Returns:
            Parsed JSON response.

        Raises:
            AuthenticationError: On 401/403 responses.
            ApiError: On other errors or invalid responses.
        """
        url = f'{base_url}{path}'
        headers = self._build_headers(
            origin=origin or SELLER_PORTAL_BASE_URL,
            referer=referer,
        )

        try:
            kwargs: dict[str, Any] = {
                'headers': headers,
                'timeout': self._timeout,
            }
            if payload is not None:
                kwargs['json'] = payload
            if params is not None:
                kwargs['params'] = params
            response = httpx.post(url, **kwargs)
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
            *,
            origin: str | None = None,
            referer: str | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Make a GET request to a portal endpoint.

        Args:
            base_url: Portal base URL.
            path: Endpoint path.
            params: Query parameters.
            origin: Override ``Origin`` header (defaults to ``base_url``).
            referer: Override ``Referer`` header (defaults to ``f'{origin}/'``).

        Returns:
            Parsed JSON response — may be a dict or list depending on endpoint.

        Raises:
            AuthenticationError: On 401/403 responses.
            ApiError: On other errors or invalid responses.
        """
        url = f'{base_url}{path}'
        headers = self._build_headers(origin=origin or base_url, referer=referer)

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

    def _get_bytes(
            self,
            base_url: str,
            path: str,
            params: dict[str, str] | None = None,
            *,
            download_token: str | None = None,
            include_auth: bool = True,
            origin: str | None = None,
            referer: str | None = None,
    ) -> bytes:
        """GET a binary payload from a portal-adjacent host.

        Two known shapes:

        - ``downloads-content-analytics.wildberries.ru`` (Jam reports): cookie +
          ``x-download-token`` only; ``authorizev3`` is rejected by this CDN.
          Callers pass ``include_auth=False`` and supply ``download_token``.
        - ``cmp.wildberries.ru`` (campaign-finance xlsx): regular portal auth
          (cookie + ``authorizev3``). Default behavior.

        Args:
            base_url: Host base URL.
            path: Endpoint path (already includes any ``/{id}`` suffix).
            params: Optional query parameters.
            download_token: Optional ``x-download-token`` value (Jam CDN).
            include_auth: When True (default), sends the ``authorizev3`` header.
                Set False for the Jam CDN which rejects it.
            origin: Override ``Origin`` header (defaults to seller portal).
            referer: Override ``Referer`` header (defaults to ``f'{origin}/'``).

        Returns:
            Raw response body bytes.

        Raises:
            AuthenticationError: On 401/403.
            ApiError: On other non-2xx responses.
        """
        url = f'{base_url}{path}'
        effective_origin = origin or SELLER_PORTAL_BASE_URL
        headers = {
            'cookie': self._cookie,
            'accept': '*/*',
            'origin': effective_origin,
            'referer': referer or f'{effective_origin}/',
            'user-agent': _DEFAULT_USER_AGENT,
        }
        if include_auth:
            headers[PORTAL_AUTH_HEADER] = self._authorizev3
        if download_token:
            headers['x-download-token'] = download_token
        try:
            response = httpx.get(url, params=params, headers=headers, timeout=self._timeout)
        except httpx.HTTPError as exc:
            raise ApiError(
                f'Portal download failed: {exc}',
                status_code=None,
                response_body=None,
            ) from exc

        if response.status_code in (401, 403):
            raise AuthenticationError(
                f'Portal download auth failed (HTTP {response.status_code}). '
                'Session cookie may have expired — re-run `wb auth login-portal`.'
            )
        if response.status_code >= 400:
            raise ApiError(
                f'Portal download error: HTTP {response.status_code}',
                status_code=response.status_code,
                response_body=response.text[:500],
            )
        return response.content

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
