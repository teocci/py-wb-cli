"""Service layer for WB Джем (Jam) report downloads.

Wraps the undocumented async ``file-manager`` workflow exposed by the WB seller
portal: generate → poll until ``SUCCESS`` → download the ZIP. See
``docs/phases/I-23-portal-jam-reports.md`` for the captured browser trace.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import date, timedelta

from wb.client.portal import PortalClient
from wb.core.constants import (
    JAM_REPORT_SEARCH_QUERIES,
    REPORT_POLL_INTERVAL,
    REPORT_POLL_TIMEOUT,
)
from wb.core.exceptions import ApiError
from wb.domain.models import JamReport

__all__ = ['PortalJamService', 'JAM_REPORT_SLUGS', 'default_filename']

logger = logging.getLogger(__name__)

# Human-readable filename slugs per WB report type.
JAM_REPORT_SLUGS: dict[str, str] = {
    JAM_REPORT_SEARCH_QUERIES: 'search-queries',
}


def default_filename(report_type: str, from_date: date, to_date: date) -> str:
    """Build a kebab-case ``.zip`` filename for a Jam report.

    Single-day: ``<slug>_<YYYY-MM-DD>.zip``. Range: ``<slug>_<from>_<to>.zip``.
    Unknown report types fall back to the lower-cased report-type slug.
    """
    slug = JAM_REPORT_SLUGS.get(report_type, report_type.lower().replace('_', '-'))
    if from_date == to_date:
        return f'{slug}_{from_date.isoformat()}.zip'
    return f'{slug}_{from_date.isoformat()}_{to_date.isoformat()}.zip'


def _previous_window(from_date: date, to_date: date) -> tuple[date, date]:
    """Same-length window immediately preceding ``[from_date, to_date]`` (inclusive)."""
    length_days = (to_date - from_date).days + 1
    prev_end = from_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length_days - 1)
    return prev_start, prev_end


class PortalJamService:
    """Business logic for the Jam ``file-manager`` workflow.

    Attributes:
        client: Underlying :class:`PortalClient`.
    """

    def __init__(self, client: PortalClient) -> None:
        self._client = client

    # ── Search-queries report ─────────────────────────────────────────

    @staticmethod
    def build_search_queries_params(from_date: date, to_date: date) -> dict:
        """Assemble the ``params`` block for ``SEARCH_QUERIES_REPORT`` generate.

        Mirrors the captured browser payload: ``orderBy openCard desc``,
        ``positionCluster='all'``, ``textLimit=30``, empty filter lists, and a
        same-length ``previous*`` window computed from ``[from_date, to_date]``.
        """
        prev_start, prev_end = _previous_window(from_date, to_date)
        return {
            'startDate': from_date.isoformat(),
            'endDate': to_date.isoformat(),
            'brands': [],
            'subjects': [],
            'tags': [],
            'nms': [],
            'vendorCodes': [],
            'orderBy': {'field': 'openCard', 'mode': 'desc'},
            'positionCluster': 'all',
            'topOrderBy': 'openCard',
            'textLimit': 30,
            'previousStartDate': prev_start.isoformat(),
            'previousEndDate': prev_end.isoformat(),
            'includeSearchTexts': True,
            'includeSubstitutedSKUs': True,
        }

    def request_search_queries(self, from_date: date, to_date: date) -> str:
        """Trigger generation of a search-queries report; returns its UUID."""
        report_id = str(uuid.uuid4())
        params = self.build_search_queries_params(from_date, to_date)
        self._client.generate_jam_report(
            report_id, JAM_REPORT_SEARCH_QUERIES, params,
        )
        logger.info('Requested Jam search-queries report %s (%s..%s)',
                    report_id, from_date.isoformat(), to_date.isoformat())
        return report_id

    def fetch_search_queries(
            self,
            from_date: date,
            to_date: date,
            *,
            interval: float = REPORT_POLL_INTERVAL,
            timeout: float = REPORT_POLL_TIMEOUT,
    ) -> tuple[JamReport, bytes]:
        """Run the full pipeline for a search-queries report.

        Returns:
            Tuple of (JamReport metadata, ZIP bytes).

        Raises:
            ApiError: On generation failure, poll timeout, or download error.
        """
        report_id = self.request_search_queries(from_date, to_date)
        report = self.poll_report(
            report_id, JAM_REPORT_SEARCH_QUERIES,
            interval=interval, timeout=timeout,
        )
        if not report.is_success:
            raise ApiError(
                f'Jam report {report_id} ended with status: {report.status}'
            )
        content = self._client.download_jam_file(report_id)
        return report, content

    # ── Polling + listing (generic across report types) ──────────────

    def list_reports(self, report_type: str = JAM_REPORT_SEARCH_QUERIES) -> list[JamReport]:
        """List Jam reports of ``report_type`` known to WB (queued or ready)."""
        raw = self._client.list_jam_reports(report_type)
        return [JamReport.from_api(item) for item in raw]

    def poll_report(
            self,
            report_id: str,
            report_type: str,
            *,
            interval: float = REPORT_POLL_INTERVAL,
            timeout: float = REPORT_POLL_TIMEOUT,
    ) -> JamReport:
        """Poll the downloads list until our ``report_id`` is terminal.

        Raises:
            ApiError: When ``timeout`` elapses without a terminal status.
        """
        elapsed = 0.0
        last_status = '<not-found>'
        while elapsed < timeout:
            match = self._find_report(report_id, report_type)
            if match is not None:
                last_status = match.status
                logger.debug('Jam %s status: %s (%.0fs)',
                             report_id, match.status, elapsed)
                if match.is_terminal:
                    return match
            time.sleep(interval)
            elapsed += interval
        raise ApiError(
            f'Jam report {report_id} did not finish within '
            f'{timeout:.0f}s (last status: {last_status})'
        )

    def _find_report(self, report_id: str, report_type: str) -> JamReport | None:
        for report in self.list_reports(report_type):
            if report.id == report_id:
                return report
        return None
