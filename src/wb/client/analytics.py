"""Typed client for WB Analytics API operations."""

from __future__ import annotations

from wb.client.http import WbHttpClient
from wb.core.constants import (
    EP_CSV_CREATE,
    EP_CSV_DOWNLOAD,
    EP_CSV_LIST,
    EP_CSV_RETRY,
    EP_FUNNEL_GROUPED,
    EP_FUNNEL_HISTORY,
    EP_FUNNEL_PRODUCTS,
    EP_SEARCH_DETAILS,
    EP_SEARCH_GROUPS,
    EP_SEARCH_ORDERS,
    EP_SEARCH_REPORT,
    EP_SEARCH_TEXTS,
)

__all__ = ['AnalyticsClient']


class AnalyticsClient:
    """Typed wrapper around WbHttpClient for Analytics API.

    Returns raw API dicts; model conversion is the service layer's job.

    Attributes:
        http: Underlying HTTP client.
    """

    def __init__(self, http: WbHttpClient) -> None:
        self._http = http

    # ── Sales Funnel ─────────────────────────────────────────────────

    def get_funnel_products(self, body: dict) -> dict:
        """Product cards statistics per period.

        Args:
            body: Request body with selectedPeriod, filters, pagination.

        Returns:
            Response dict with data.products[] and data.currency.
        """
        result = self._http.post(EP_FUNNEL_PRODUCTS, json_body=body)
        return result if isinstance(result, dict) else {}

    def get_funnel_history(self, body: dict) -> list:
        """Product cards statistics per days.

        Args:
            body: Request body with selectedPeriod, nmIds, aggregationLevel.

        Returns:
            List of product history dicts.
        """
        result = self._http.post(EP_FUNNEL_HISTORY, json_body=body)
        return result if isinstance(result, list) else []

    def get_funnel_grouped(self, body: dict) -> dict:
        """Grouped product cards statistics per days.

        Args:
            body: Request body with selectedPeriod, filters, aggregationLevel.

        Returns:
            Response dict with data array.
        """
        result = self._http.post(EP_FUNNEL_GROUPED, json_body=body)
        return result if isinstance(result, dict) else {}

    # ── Search Report ────────────────────────────────────────────────

    def get_search_report(self, body: dict) -> dict:
        """Main search report page.

        Args:
            body: Request body with currentPeriod, filters, pagination.

        Returns:
            Response dict with data containing commonInfo, groups, etc.
        """
        result = self._http.post(EP_SEARCH_REPORT, json_body=body)
        return result if isinstance(result, dict) else {}

    def get_search_groups(self, body: dict) -> dict:
        """Pagination by groups in search report.

        Args:
            body: Request body with currentPeriod, filters, pagination.

        Returns:
            Response dict with data.groups[].
        """
        result = self._http.post(EP_SEARCH_GROUPS, json_body=body)
        return result if isinstance(result, dict) else {}

    def get_search_details(self, body: dict) -> dict:
        """Pagination by products within a group.

        Args:
            body: Request body with currentPeriod, group filters, pagination.

        Returns:
            Response dict with data.products[].
        """
        result = self._http.post(EP_SEARCH_DETAILS, json_body=body)
        return result if isinstance(result, dict) else {}

    def get_search_texts(self, body: dict) -> dict:
        """Top search texts by product.

        Args:
            body: Request body with currentPeriod, nmId, limit.

        Returns:
            Response dict with data.searchTexts[].
        """
        result = self._http.post(EP_SEARCH_TEXTS, json_body=body)
        return result if isinstance(result, dict) else {}

    def get_search_orders(self, body: dict) -> dict:
        """Orders and positions by product search texts.

        Args:
            body: Request body with currentPeriod, nmId, searchTexts[].

        Returns:
            Response dict with order/position data.
        """
        result = self._http.post(EP_SEARCH_ORDERS, json_body=body)
        return result if isinstance(result, dict) else {}

    # ── CSV Reports ──────────────────────────────────────────────────

    def create_report(self, body: dict) -> dict:
        """Create a CSV report generation task.

        Args:
            body: Request body with id, reportType, userReportName, params.

        Returns:
            Response dict with data confirmation message.
        """
        result = self._http.post(EP_CSV_CREATE, json_body=body)
        return result if isinstance(result, dict) else {}

    def list_reports(
            self, download_ids: list[str] | None = None,
    ) -> dict:
        """Get the list of CSV reports.

        Args:
            download_ids: Optional list of report UUIDs to filter by.

        Returns:
            Response dict with data[] containing report statuses.
        """
        params = None
        if download_ids:
            params = {'filter[downloadIds]': download_ids}
        result = self._http.get(EP_CSV_LIST, params=params)
        return result if isinstance(result, dict) else {}

    def retry_report(self, download_id: str) -> dict:
        """Retry a failed CSV report generation.

        Args:
            download_id: Report UUID to retry.

        Returns:
            Response dict with data confirmation message.
        """
        result = self._http.post(
            EP_CSV_RETRY,
            json_body={'downloadId': download_id},
        )
        return result if isinstance(result, dict) else {}

    def download_report(self, download_id: str) -> bytes:
        """Download a generated CSV report as ZIP.

        Args:
            download_id: Report UUID to download.

        Returns:
            Raw ZIP file bytes.
        """
        path = f'{EP_CSV_DOWNLOAD}/{download_id}'
        return self._http.request_raw('GET', path)
