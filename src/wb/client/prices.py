"""Typed HTTP client for WB Prices & Discounts API operations."""

from __future__ import annotations

from typing import Any

from wb.client.http import WbHttpClient
from wb.core.constants import EP_PRICES_GOODS_FILTER

__all__ = ['PricesClient']

_MAX_PAGE_LIMIT = 1000


class PricesClient:
    """Typed wrapper around WbHttpClient for the Prices & Discounts API.

    Returns raw API dicts; domain model conversion is the service layer's job.

    Auth uses the same seller API token as the promotion API, passed as
    'Authorization: <token>' with no 'Bearer' prefix by WbHttpClient.

    Attributes:
        _http: Underlying HTTP client pointed at the Prices & Discounts base URL.
    """

    def __init__(self, http: WbHttpClient) -> None:
        self._http = http

    def list_goods(
            self,
            limit: int = _MAX_PAGE_LIMIT,
            offset: int = 0,
            filter_nm_id: int | None = None,
    ) -> dict[str, Any]:
        """Fetch a page of goods with price and discount data.

        Args:
            limit: Number of records per page (max 1000, clamped automatically).
            offset: Number of records to skip for pagination.
            filter_nm_id: Optional single NM ID to filter by.
                          When provided, only that product is returned.

        Returns:
            Raw API response dict with shape::

                {'data': {'listGoods': [...]}}

            Returns an empty dict when the HTTP client returns a non-dict value.
        """
        params: dict[str, Any] = {
            'limit': min(limit, _MAX_PAGE_LIMIT),
            'offset': offset,
        }
        if filter_nm_id is not None:
            params['filterNmID'] = filter_nm_id

        result = self._http.get(EP_PRICES_GOODS_FILTER, params=params)
        return result if isinstance(result, dict) else {}
