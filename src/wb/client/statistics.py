"""HTTP client for WB Statistics API (statistics-api.wildberries.ru)."""

from __future__ import annotations

from wb.client.http import WbHttpClient
from wb.core.constants import EP_STATISTICS_SALES

__all__ = ['StatisticsClient']


class StatisticsClient:
    """Typed wrapper for statistics-api.wildberries.ru.

    Attributes:
        _http: Underlying WbHttpClient with statistics base URL.
    """

    def __init__(self, http: WbHttpClient) -> None:
        self._http = http

    def get_sales(self, date_from: str, flag: int = 1) -> list[dict]:
        """Fetch sales records since a given date.

        Args:
            date_from: ISO date string 'YYYY-MM-DD' for the start of the window.
            flag: 1 = by actual sale date (default), 0 = by last-change date.

        Returns:
            List of raw sale record dicts from the API.
        """
        params = {'dateFrom': date_from, 'flag': flag}
        result = self._http.get(EP_STATISTICS_SALES, params=params)
        if not isinstance(result, list):
            return []
        return result
