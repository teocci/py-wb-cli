"""Typed client for WB Finance API — sales-reports and acquiring."""

from __future__ import annotations

from wb.client.http import WbHttpClient
from wb.core.constants import (
    EP_FINANCE_ACQUIRING_DETAILED,
    EP_FINANCE_ACQUIRING_DETAILED_BY_ID,
    EP_FINANCE_ACQUIRING_LIST,
    EP_FINANCE_SALES_REPORT_DETAILED,
    EP_FINANCE_SALES_REPORT_DETAILED_BY_ID,
    EP_FINANCE_SALES_REPORT_LIST,
)

__all__ = ['FinanceClient']


class FinanceClient:
    """Typed wrapper around :class:`WbHttpClient` for the WB Finance API.

    All six endpoints are POST. Returns raw API responses (``list[dict]``
    for the report bodies); domain parsing happens in
    :class:`wb.services.finance.FinanceService`.
    """

    def __init__(self, http: WbHttpClient) -> None:
        self._http = http

    # ── Sales Reports ────────────────────────────────────────────────

    def list_sales_reports(
            self,
            *,
            date_from: str,
            date_to: str,
            period: str | None = None,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[dict]:
        """POST ``/api/finance/v1/sales-reports/list``.

        Args:
            date_from: Reporting-period start (YYYY-MM-DD or RFC3339).
            date_to: Reporting-period end (YYYY-MM-DD or RFC3339).
            period: Optional ``weekly`` (default) or ``daily``.
            limit: Optional cap on the number of header rows returned.
            offset: Optional starting offset for pagination.

        Returns:
            Raw list of report-header dicts, or ``[]`` on 204.
        """
        body: dict = {'dateFrom': date_from, 'dateTo': date_to}
        if period:
            body['period'] = period
        if limit is not None:
            body['limit'] = limit
        if offset is not None:
            body['offset'] = offset
        result = self._http.post(EP_FINANCE_SALES_REPORT_LIST, json_body=body)
        return result if isinstance(result, list) else []

    def detailed_sales_reports(
            self,
            *,
            date_from: str,
            date_to: str,
            period: str | None = None,
            limit: int | None = None,
            rrd_id: int | None = None,
    ) -> list[dict]:
        """POST ``/api/finance/v1/sales-reports/detailed`` (by period).

        Args:
            date_from: Reporting-period start.
            date_to: Reporting-period end.
            period: Optional ``weekly`` or ``daily``.
            limit: Rows per response page (WB max 100 000).
            rrd_id: Cursor — start at 0; on subsequent calls pass the
                ``rrdId`` of the last row in the previous response. WB
                returns HTTP 204 (parsed as ``[]``) at the end of the
                stream.

        Returns:
            Raw list of detail-row dicts, or ``[]`` on 204.
        """
        body: dict = {'dateFrom': date_from, 'dateTo': date_to}
        if period:
            body['period'] = period
        if limit is not None:
            body['limit'] = limit
        if rrd_id is not None:
            body['rrdId'] = rrd_id
        result = self._http.post(EP_FINANCE_SALES_REPORT_DETAILED, json_body=body)
        return result if isinstance(result, list) else []

    def sales_report_by_id(
            self,
            report_id: int,
            *,
            limit: int | None = None,
            rrd_id: int | None = None,
    ) -> list[dict]:
        """POST ``/api/finance/v1/sales-reports/detailed/{reportId}``.

        Args:
            report_id: WB sales-report identifier (from
                :meth:`list_sales_reports`).
            limit: Rows per response page.
            rrd_id: ``rrdId`` cursor (0 for first call).

        Returns:
            Raw list of detail-row dicts, or ``[]`` on 204.
        """
        path = EP_FINANCE_SALES_REPORT_DETAILED_BY_ID.format(report_id=report_id)
        body: dict = {}
        if limit is not None:
            body['limit'] = limit
        if rrd_id is not None:
            body['rrdId'] = rrd_id
        result = self._http.post(path, json_body=body)
        return result if isinstance(result, list) else []

    # ── Acquiring ────────────────────────────────────────────────────

    def list_acquiring_reports(
            self,
            *,
            date_from: str,
            date_to: str,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[dict]:
        """POST ``/api/finance/v1/acquiring/list``.

        Args:
            date_from: Reporting-period start.
            date_to: Reporting-period end.
            limit: Optional cap on returned rows.
            offset: Optional starting offset.

        Returns:
            Raw list of acquiring-report-header dicts, or ``[]`` on 204.
        """
        body: dict = {'dateFrom': date_from, 'dateTo': date_to}
        if limit is not None:
            body['limit'] = limit
        if offset is not None:
            body['offset'] = offset
        result = self._http.post(EP_FINANCE_ACQUIRING_LIST, json_body=body)
        return result if isinstance(result, list) else []

    def detailed_acquiring_reports(
            self,
            *,
            date_from: str,
            date_to: str,
            limit: int | None = None,
            rrd_id: int | None = None,
    ) -> list[dict]:
        """POST ``/api/finance/v1/acquiring/detailed`` (by period).

        Args:
            date_from: Reporting-period start.
            date_to: Reporting-period end.
            limit: Rows per response page.
            rrd_id: ``rrdId`` cursor (0 for first call).

        Returns:
            Raw list of detail-row dicts, or ``[]`` on 204.
        """
        body: dict = {'dateFrom': date_from, 'dateTo': date_to}
        if limit is not None:
            body['limit'] = limit
        if rrd_id is not None:
            body['rrdId'] = rrd_id
        result = self._http.post(EP_FINANCE_ACQUIRING_DETAILED, json_body=body)
        return result if isinstance(result, list) else []

    def acquiring_report_by_id(
            self,
            report_id: int,
            *,
            limit: int | None = None,
            rrd_id: int | None = None,
    ) -> list[dict]:
        """POST ``/api/finance/v1/acquiring/detailed/{reportId}``.

        Args:
            report_id: WB acquiring-report identifier.
            limit: Rows per response page.
            rrd_id: ``rrdId`` cursor (0 for first call).

        Returns:
            Raw list of detail-row dicts, or ``[]`` on 204.
        """
        path = EP_FINANCE_ACQUIRING_DETAILED_BY_ID.format(report_id=report_id)
        body: dict = {}
        if limit is not None:
            body['limit'] = limit
        if rrd_id is not None:
            body['rrdId'] = rrd_id
        result = self._http.post(path, json_body=body)
        return result if isinstance(result, list) else []
