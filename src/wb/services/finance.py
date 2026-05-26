"""Service layer for WB Finance API (settlement reports).

Parses raw client responses into typed summaries for ``list`` endpoints
and forwards ``detailed*`` rows as raw ``dict`` for lossless WB field
passthrough. Encapsulates the ``rrdId`` cursor-pagination loop so CLI
commands stay declarative.
"""

from __future__ import annotations

import logging

from wb.client.finance import FinanceClient
from wb.domain.finance import AcquiringReportSummary, SalesReportSummary

__all__ = ['FinanceService', 'DEFAULT_PAGE_SIZE']

logger = logging.getLogger(__name__)

# WB's hard maximum for the ``limit`` body field on ``detailed*`` endpoints.
DEFAULT_PAGE_SIZE: int = 100_000


class FinanceService:
    """Coordinate :class:`FinanceClient` calls and domain conversion.

    The ``detailed*`` endpoints paginate via the ``rrdId`` cursor: start
    with ``rrd_id=0`` and on each subsequent call pass the previous
    page's last ``rrdId``. WB returns HTTP 204 (parsed as ``[]``) at the
    end of the stream. The ``fetch_all`` toggle on each detail method
    drives this loop; default behaviour is one page (≤ ``limit`` rows).
    """

    def __init__(self, client: FinanceClient) -> None:
        self._client = client

    # ── Sales Reports ─────────────────────────────────────────────────

    def list_sales_reports(
            self,
            *,
            date_from: str,
            date_to: str,
            period: str | None = None,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[SalesReportSummary]:
        """Return parsed sales-report headers for a date range.

        Args:
            date_from: Reporting-period start (YYYY-MM-DD or RFC3339).
            date_to: Reporting-period end.
            period: ``weekly`` (default) or ``daily``.
            limit: Cap on header rows.
            offset: Starting offset for pagination.

        Returns:
            List of :class:`SalesReportSummary` instances; empty when
            WB returns 204.
        """
        raw = self._client.list_sales_reports(
            date_from=date_from,
            date_to=date_to,
            period=period,
            limit=limit,
            offset=offset,
        ) or []
        return [SalesReportSummary.from_api(r) for r in raw]

    def detailed_sales_reports(
            self,
            *,
            date_from: str,
            date_to: str,
            period: str | None = None,
            limit: int = DEFAULT_PAGE_SIZE,
            rrd_id: int = 0,
            fetch_all: bool = False,
    ) -> list[dict]:
        """Return detail rows across all reports in ``date_from..date_to``.

        Rows are returned as raw dicts (lossless WB field passthrough,
        matching the I-21 sales/orders pattern). Use ``fetch_all=True``
        to exhaust the ``rrdId`` cursor — every page costs one API call
        and the endpoint is throttled at 1 req/min, so a 1 M-row seller
        takes 10+ minutes.

        Args:
            date_from: Reporting-period start.
            date_to: Reporting-period end.
            period: ``weekly`` or ``daily``.
            limit: Rows per API page (WB max 100 000).
            rrd_id: Starting cursor (``0`` for the first page).
            fetch_all: Exhaust the cursor when True; one page only when
                False (default).

        Returns:
            Concatenated detail-row dicts.
        """
        if not fetch_all:
            return self._client.detailed_sales_reports(
                date_from=date_from,
                date_to=date_to,
                period=period,
                limit=limit,
                rrd_id=rrd_id,
            )
        return self._paginate(
            lambda cursor: self._client.detailed_sales_reports(
                date_from=date_from,
                date_to=date_to,
                period=period,
                limit=limit,
                rrd_id=cursor,
            ),
            initial=rrd_id,
        )

    def sales_report_by_id(
            self,
            report_id: int,
            *,
            limit: int = DEFAULT_PAGE_SIZE,
            rrd_id: int = 0,
            fetch_all: bool = False,
    ) -> list[dict]:
        """Return detail rows for one specific sales report.

        Args:
            report_id: WB report identifier from
                :meth:`list_sales_reports`.
            limit: Rows per API page.
            rrd_id: Starting cursor.
            fetch_all: Exhaust the cursor when True.

        Returns:
            Detail-row dicts for that single report.
        """
        if not fetch_all:
            return self._client.sales_report_by_id(
                report_id, limit=limit, rrd_id=rrd_id,
            )
        return self._paginate(
            lambda cursor: self._client.sales_report_by_id(
                report_id, limit=limit, rrd_id=cursor,
            ),
            initial=rrd_id,
        )

    # ── Acquiring ─────────────────────────────────────────────────────

    def list_acquiring_reports(
            self,
            *,
            date_from: str,
            date_to: str,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[AcquiringReportSummary]:
        """Return parsed acquiring-report headers for a date range.

        Args:
            date_from: Reporting-period start.
            date_to: Reporting-period end.
            limit: Cap on header rows.
            offset: Starting offset.

        Returns:
            List of :class:`AcquiringReportSummary` instances.
        """
        raw = self._client.list_acquiring_reports(
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        ) or []
        return [AcquiringReportSummary.from_api(r) for r in raw]

    def detailed_acquiring_reports(
            self,
            *,
            date_from: str,
            date_to: str,
            limit: int = DEFAULT_PAGE_SIZE,
            rrd_id: int = 0,
            fetch_all: bool = False,
    ) -> list[dict]:
        """Return acquiring detail rows for a date range.

        Args:
            date_from: Reporting-period start.
            date_to: Reporting-period end.
            limit: Rows per API page.
            rrd_id: Starting cursor.
            fetch_all: Exhaust the cursor when True.

        Returns:
            Detail-row dicts across all acquiring reports in the range.
        """
        if not fetch_all:
            return self._client.detailed_acquiring_reports(
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                rrd_id=rrd_id,
            )
        return self._paginate(
            lambda cursor: self._client.detailed_acquiring_reports(
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                rrd_id=cursor,
            ),
            initial=rrd_id,
        )

    def acquiring_report_by_id(
            self,
            report_id: int,
            *,
            limit: int = DEFAULT_PAGE_SIZE,
            rrd_id: int = 0,
            fetch_all: bool = False,
    ) -> list[dict]:
        """Return acquiring detail rows for one specific report.

        Args:
            report_id: WB acquiring-report identifier.
            limit: Rows per API page.
            rrd_id: Starting cursor.
            fetch_all: Exhaust the cursor when True.

        Returns:
            Detail-row dicts for that single acquiring report.
        """
        if not fetch_all:
            return self._client.acquiring_report_by_id(
                report_id, limit=limit, rrd_id=rrd_id,
            )
        return self._paginate(
            lambda cursor: self._client.acquiring_report_by_id(
                report_id, limit=limit, rrd_id=cursor,
            ),
            initial=rrd_id,
        )

    # ── Pagination helper ────────────────────────────────────────────

    @staticmethod
    def _paginate(
            fetch,
            *,
            initial: int = 0,
            max_iterations: int = 1_000,
    ) -> list[dict]:
        """Exhaust an ``rrdId``-cursor endpoint by repeated calls.

        Loop invariant: each iteration advances the cursor to the last
        row's ``rrdId`` until WB returns ``[]`` (its 204 marker). The
        ``max_iterations`` guard prevents an infinite loop if WB ever
        starts echoing the same cursor — in that case we log a warning
        and bail rather than spin forever.

        Args:
            fetch: Callable ``cursor -> list[dict]`` performing one
                API page request.
            initial: Starting cursor value.
            max_iterations: Hard cap on the number of pages (≥ 100 M
                rows at default page size — effectively unbounded for
                real datasets).

        Returns:
            Concatenated detail rows.
        """
        rows: list[dict] = []
        cursor = initial
        for _ in range(max_iterations):
            page = fetch(cursor) or []
            if not page:
                return rows
            rows.extend(page)
            last_rrd = page[-1].get('rrdId')
            if last_rrd is None or last_rrd == cursor:
                logger.warning(
                    'Finance pagination did not advance (cursor=%s, last_rrd=%s); '
                    'stopping after %d rows.',
                    cursor, last_rrd, len(rows),
                )
                return rows
            cursor = int(last_rrd)
        logger.warning(
            'Finance pagination hit max_iterations=%d at cursor=%s; '
            'returning %d rows collected so far.',
            max_iterations, cursor, len(rows),
        )
        return rows
