"""Service layer for WB seller-goods sales-report downloads (I-25).

Wraps the undocumented async 3-step workflow exposed by
``seller-weekly-report.wildberries.ru``: generate → poll-via-download →
return xlsx bytes. See ``docs/phases/I-25-portal-sales-report.md``.
"""

from __future__ import annotations

import logging
import time
from datetime import date

from wb.client.portal import PortalClient
from wb.core.constants import (
    REPORT_POLL_INTERVAL,
    REPORT_POLL_TIMEOUT,
    SALES_REPORT_TYPE_SUPPLIER_GOODS,
)
from wb.core.exceptions import ApiError
from wb.domain.models import SalesReport

__all__ = [
    'PortalSalesReportService',
    'default_filename',
    'format_query_date',
]

logger = logging.getLogger(__name__)


def format_query_date(d: date) -> str:
    """Format a date as ``DD.MM.YY`` for the sales-report query string.

    The WB endpoint uses day-first with a two-digit year. Years before 2000
    would silently collide with 19xx, so guard against that explicitly.

    Args:
        d: Date to format.

    Returns:
        ``DD.MM.YY`` string (zero-padded day and month).

    Raises:
        ValueError: If ``d.year < 2000``.
    """
    if d.year < 2000:
        raise ValueError(
            f'format_query_date: year {d.year} would collide with 19xx in DD.MM.YY'
        )
    return d.strftime('%d.%m.%y')


def default_filename(from_date: date, to_date: date) -> str:
    """Build a kebab-case ``.xlsx`` filename for a sales report.

    Single-day: ``supplier-goods_<YYYY-MM-DD>.xlsx``.
    Range: ``supplier-goods_<from>_<to>.xlsx``.
    """
    slug = SALES_REPORT_TYPE_SUPPLIER_GOODS
    if from_date == to_date:
        return f'{slug}_{from_date.isoformat()}.xlsx'
    return f'{slug}_{from_date.isoformat()}_{to_date.isoformat()}.xlsx'


class PortalSalesReportService:
    """Business logic for the seller-goods sales-report workflow.

    Attributes:
        client: Underlying :class:`PortalClient`.
    """

    def __init__(self, client: PortalClient) -> None:
        self._client = client

    def request_supplier_goods(
            self,
            from_date: date,
            to_date: date,
    ) -> SalesReport:
        """Trigger generation of a supplier-goods sales report.

        Returns:
            The :class:`SalesReport` parsed from the immediate POST response.
            ``file_url`` will be ``''`` until WB finishes generating.

        Raises:
            ApiError: When WB returns an error envelope on the generate call.
        """
        raw = self._client.generate_sales_report(
            SALES_REPORT_TYPE_SUPPLIER_GOODS,
            format_query_date(from_date),
            format_query_date(to_date),
        )
        if not isinstance(raw, dict) or raw.get('error'):
            raise ApiError(
                f'WB rejected sales-report generate: {raw}',
                status_code=None,
                response_body=str(raw)[:500],
            )
        data = raw.get('data') or {}
        if not isinstance(data, dict) or not data.get('id'):
            raise ApiError(
                'Sales-report generate response missing data.id',
                status_code=None,
                response_body=str(raw)[:500],
            )
        report = SalesReport.from_api(data)
        logger.info(
            'Requested supplier-goods sales report %s (%s..%s)',
            report.id, from_date.isoformat(), to_date.isoformat(),
        )
        return report

    def fetch_supplier_goods(
            self,
            from_date: date,
            to_date: date,
            *,
            interval: float = REPORT_POLL_INTERVAL,
            timeout: float = REPORT_POLL_TIMEOUT,
    ) -> tuple[SalesReport, bytes]:
        """Run the full generate → poll → download pipeline.

        Returns:
            Tuple of (SalesReport metadata with ``file_url`` backfilled, xlsx bytes).

        Raises:
            ApiError: On generation failure or poll timeout.
        """
        report = self.request_supplier_goods(from_date, to_date)
        xlsx = self._poll_download(
            report.id, interval=interval, timeout=timeout,
        )
        backfilled = SalesReport(
            id=report.id,
            supplier_id=report.supplier_id,
            locale=report.locale,
            report_name=report.report_name,
            date_from=report.date_from,
            date_to=report.date_to,
            created_at=report.created_at,
            expired_at=report.expired_at,
            file_url=report.file_url or f'sales-report:{report.id}',
            total_count=report.total_count,
            is_deleted=report.is_deleted,
        )
        return backfilled, xlsx

    def list_reports(
            self,
            report_type: str = SALES_REPORT_TYPE_SUPPLIER_GOODS,
    ) -> list[SalesReport]:
        """List sales reports of ``report_type`` known to WB."""
        raw = self._client.list_sales_reports(report_type)
        return [SalesReport.from_api(item) for item in raw]

    def _poll_download(
            self,
            report_id: str,
            *,
            interval: float,
            timeout: float,
    ) -> bytes:
        """Loop ``try_download_sales_report_xlsx`` until the file lands or timeout.

        The xlsx endpoint is the readiness signal — there is no separate
        status field on the list endpoint and re-POSTing the generate call
        creates a new id (the trailing nonce confirms this is not idempotent).

        Raises:
            ApiError: When ``timeout`` elapses with no successful download.
        """
        elapsed = 0.0
        while elapsed < timeout:
            xlsx = self._client.try_download_sales_report_xlsx(
                SALES_REPORT_TYPE_SUPPLIER_GOODS, report_id,
            )
            if xlsx is not None:
                logger.debug(
                    'Sales-report %s ready after %.0fs (%d bytes)',
                    report_id, elapsed, len(xlsx),
                )
                return xlsx
            logger.debug(
                'Sales-report %s still pending after %.0fs', report_id, elapsed,
            )
            time.sleep(interval)
            elapsed += interval
        raise ApiError(
            f'Sales-report {report_id} did not finish within {timeout:.0f}s',
            status_code=None,
            response_body=None,
        )
