"""Typed client for WB Reports API — warehouse remains and async reports."""

from __future__ import annotations

from wb.client.http import WbHttpClient
from wb.core.constants import (
    EP_WAREHOUSE_REMAINS_CREATE,
    EP_WAREHOUSE_REMAINS_DOWNLOAD,
    EP_WAREHOUSE_REMAINS_STATUS,
)

__all__ = ['ReportsClient']


class ReportsClient:
    """Typed wrapper around WbHttpClient for Reports API.

    Handles the async 3-step report lifecycle:
    create task -> poll status -> download results.

    Attributes:
        http: Underlying HTTP client.
    """

    def __init__(self, http: WbHttpClient) -> None:
        self._http = http

    # ── Warehouse Remains ────────────────────────────────────────────

    def create_warehouse_remains(
            self,
            *,
            locale: str = 'ru',
            group_by_brand: bool = False,
            group_by_subject: bool = False,
            group_by_sa: bool = False,
            group_by_nm: bool = False,
            group_by_barcode: bool = False,
            group_by_size: bool = False,
            filter_pics: int = 0,
            filter_volume: int = 0,
    ) -> dict:
        """Create a warehouse remains report task.

        Args:
            locale: Language for response fields (ru, en, zh).
            group_by_brand: Group results by brand.
            group_by_subject: Group results by subject.
            group_by_sa: Group results by seller's article.
            group_by_nm: Group results by WB article (adds volume field).
            group_by_barcode: Group results by barcode.
            group_by_size: Group results by size.
            filter_pics: Photo filter (-1=no photo, 0=no filter, 1=with photo).
            filter_volume: Volume filter (-1=no dims, 0=no filter, 3=over 3L).

        Returns:
            Response dict with data.taskId.
        """
        params = {
            'locale': locale,
            'groupByBrand': str(group_by_brand).lower(),
            'groupBySubject': str(group_by_subject).lower(),
            'groupBySa': str(group_by_sa).lower(),
            'groupByNm': str(group_by_nm).lower(),
            'groupByBarcode': str(group_by_barcode).lower(),
            'groupBySize': str(group_by_size).lower(),
            'filterPics': filter_pics,
            'filterVolume': filter_volume,
        }
        result = self._http.get(EP_WAREHOUSE_REMAINS_CREATE, params=params)
        return result if isinstance(result, dict) else {}

    def get_warehouse_remains_status(self, task_id: str) -> dict:
        """Check the status of a warehouse remains report task.

        Args:
            task_id: UUID of the generation task.

        Returns:
            Response dict with data.id and data.status.
        """
        path = f'{EP_WAREHOUSE_REMAINS_STATUS}/{task_id}/status'
        result = self._http.get(path)
        return result if isinstance(result, dict) else {}

    def download_warehouse_remains(self, task_id: str) -> list:
        """Download the completed warehouse remains report.

        Args:
            task_id: UUID of the completed task.

        Returns:
            List of item dicts with warehouses breakdown.
        """
        path = f'{EP_WAREHOUSE_REMAINS_DOWNLOAD}/{task_id}/download'
        result = self._http.get(path)
        return result if isinstance(result, list) else []
