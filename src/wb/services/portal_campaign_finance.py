"""Service layer for the cmp.wildberries.ru campaign-finance ledger.

Two synchronous endpoints, both on the unofficial portal:

- ``GET /api/v6/upd``    — paginated JSON rows.
- ``GET /api/v5/updxlsx`` — one-shot binary xlsx of the same rows.

See ``docs/phases/I-24-portal-campaign-finance.md`` for the captured trace.
"""

from __future__ import annotations

import logging
from datetime import date

from wb.client.portal import PortalClient
from wb.core.constants import (
    CAMPAIGN_FINANCE_DEFAULT_PAGE_SIZE,
    MSK_TZ_OFFSET,
)
from wb.domain.models import CampaignFinancePage

__all__ = [
    'PortalCampaignFinanceService',
    'format_msk_datetime',
    'default_filename',
]

logger = logging.getLogger(__name__)


def format_msk_datetime(d: date) -> str:
    """Render ``d`` as a WB-portal ISO-8601 datetime at start-of-day MSK.

    Example: ``date(2026, 5, 29) -> '2026-05-29T00:00:00+03:00'``.
    """
    return f'{d.isoformat()}T00:00:00{MSK_TZ_OFFSET}'


def default_filename(from_date: date, to_date: date) -> str:
    """Build a kebab-case ``.xlsx`` filename for the campaign-finance export.

    Single-day: ``campaign-finance_<YYYY-MM-DD>.xlsx``.
    Range: ``campaign-finance_<from>_<to>.xlsx``.
    """
    if from_date == to_date:
        return f'campaign-finance_{from_date.isoformat()}.xlsx'
    return f'campaign-finance_{from_date.isoformat()}_{to_date.isoformat()}.xlsx'


class PortalCampaignFinanceService:
    """Business logic for the campaign-finance ledger endpoints.

    Attributes:
        client: Underlying :class:`PortalClient`.
    """

    def __init__(self, client: PortalClient) -> None:
        self._client = client

    def list_page(
            self,
            from_date: date,
            to_date: date,
            *,
            page_number: int = 1,
            page_size: int = CAMPAIGN_FINANCE_DEFAULT_PAGE_SIZE,
    ) -> CampaignFinancePage:
        """Fetch one page of expense rows for ``[from_date, to_date]``."""
        raw = self._client.list_campaign_finance(
            format_msk_datetime(from_date),
            format_msk_datetime(to_date),
            page_number=page_number,
            page_size=page_size,
        )
        return CampaignFinancePage.from_api(
            raw, page_number=page_number, page_size=page_size,
        )

    def list_all(
            self,
            from_date: date,
            to_date: date,
            *,
            page_size: int = CAMPAIGN_FINANCE_DEFAULT_PAGE_SIZE,
    ) -> CampaignFinancePage:
        """Fetch every row for ``[from_date, to_date]`` by walking pages.

        Stops when ``total_count`` is reached or the API returns a short page.
        The returned :class:`CampaignFinancePage` has ``page_number=1`` and
        ``page_size`` set to the combined entry count (or the per-page size if
        no rows were returned).
        """
        entries = []
        upd_total_amount = 0
        total_count = 0
        page_number = 1
        while True:
            page = self.list_page(
                from_date, to_date,
                page_number=page_number, page_size=page_size,
            )
            upd_total_amount = page.upd_total_amount
            total_count = page.total_count
            entries.extend(page.entries)
            if not page.entries or len(entries) >= total_count or len(page.entries) < page_size:
                break
            page_number += 1
        return CampaignFinancePage(
            entries=entries,
            upd_total_amount=upd_total_amount,
            total_count=total_count,
            page_number=1,
            page_size=len(entries) or page_size,
        )

    def download_xlsx(self, from_date: date, to_date: date) -> bytes:
        """Download the whole-range xlsx workbook in one call."""
        return self._client.download_campaign_finance_xlsx(
            format_msk_datetime(from_date),
            format_msk_datetime(to_date),
        )
