"""Analytics use-cases for sales funnel, search reports, and CSV exports."""

from __future__ import annotations

import uuid
from pathlib import Path

from wb.client.analytics import AnalyticsClient
from wb.core.batching import chunk
from wb.core.constants import HISTORY_CHUNK_SIZE, PRODUCTS_CHUNK_SIZE
from wb.core.exceptions import ValidationError
from wb.domain.analytics_models import (
    CsvReportStatus,
    FunnelHistoryDay,
    ProductFunnelHistory,
    ProductFunnelStats,
    SearchReportGroup,
    SearchReportProduct,
    SearchTextEntry,
)

__all__ = ['AnalyticsService']

_MAX_LIMIT = 1000
_MAX_SEARCH_TEXT_LIMIT = 100


class AnalyticsService:
    """Orchestrates analytics operations via the Analytics API.

    Attributes:
        client: Analytics API client.
    """

    def __init__(self, client: AnalyticsClient) -> None:
        self._client = client

    # ── Sales Funnel ─────────────────────────────────────────────────

    def get_product_funnel(
            self,
            begin: str,
            end: str,
            *,
            nm_ids: list[int] | None = None,
            brand_names: list[str] | None = None,
            subject_ids: list[int] | None = None,
            tag_ids: list[int] | None = None,
            limit: int = 50,
            offset: int = 0,
    ) -> list[ProductFunnelStats]:
        """Retrieve product cards statistics for a period.

        Args:
            begin: Period start date (YYYY-MM-DD).
            end: Period end date (YYYY-MM-DD).
            nm_ids: Filter by WB article numbers.
            brand_names: Filter by brand names.
            subject_ids: Filter by subject IDs.
            tag_ids: Filter by tag IDs.
            limit: Number of products to return (max 1000).
            offset: Number of results to skip.

        Returns:
            List of ProductFunnelStats domain objects.
        """
        body: dict = {
            'selectedPeriod': {'start': begin, 'end': end},
            'limit': min(limit, _MAX_LIMIT),
            'offset': offset,
        }
        if nm_ids:
            body['nmIds'] = nm_ids[:PRODUCTS_CHUNK_SIZE]
        if brand_names:
            body['brandNames'] = brand_names
        if subject_ids:
            body['subjectIds'] = subject_ids
        if tag_ids:
            body['tagIds'] = tag_ids

        raw = self._client.get_funnel_products(body)
        data = raw.get('data', {})
        currency = data.get('currency', 'RUB')
        products = data.get('products', [])
        return [
            ProductFunnelStats.from_api(p, currency=currency)
            for p in products
        ]

    def get_product_history(
            self,
            begin: str,
            end: str,
            nm_ids: list[int],
            *,
            aggregation: str = 'day',
    ) -> list[ProductFunnelHistory]:
        """Retrieve product cards statistics per days.

        Automatically splits nm_ids into HISTORY_CHUNK_SIZE chunks so
        callers can pass any number of IDs without hitting API limits.

        Args:
            begin: Period start date (YYYY-MM-DD).
            end: Period end date (YYYY-MM-DD).
            nm_ids: WB article numbers (at least 1 required).
            aggregation: Aggregation level ('day' or 'week').

        Returns:
            List of ProductFunnelHistory domain objects.

        Raises:
            ValidationError: If nm_ids is empty.
        """
        if not nm_ids:
            raise ValidationError('At least one nm_id is required')
        results: list[ProductFunnelHistory] = []
        for batch in chunk(nm_ids, HISTORY_CHUNK_SIZE):
            body = {
                'selectedPeriod': {'start': begin, 'end': end},
                'nmIds': batch,
                'aggregationLevel': aggregation,
            }
            raw = self._client.get_funnel_history(body)
            results.extend(ProductFunnelHistory.from_api(item) for item in raw)
        return results

    def get_grouped_history(
            self,
            begin: str,
            end: str,
            *,
            brand_names: list[str] | None = None,
            subject_ids: list[int] | None = None,
            tag_ids: list[int] | None = None,
            aggregation: str = 'day',
    ) -> list[ProductFunnelHistory]:
        """Retrieve grouped product cards statistics per days.

        Args:
            begin: Period start date (YYYY-MM-DD).
            end: Period end date (YYYY-MM-DD).
            brand_names: Filter by brand names.
            subject_ids: Filter by subject IDs.
            tag_ids: Filter by tag IDs.
            aggregation: Aggregation level ('day' or 'week').

        Returns:
            List of ProductFunnelHistory domain objects.
        """
        body: dict = {
            'selectedPeriod': {'start': begin, 'end': end},
            'aggregationLevel': aggregation,
        }
        if brand_names:
            body['brandNames'] = brand_names
        if subject_ids:
            body['subjectIds'] = subject_ids
        if tag_ids:
            body['tagIds'] = tag_ids

        raw = self._client.get_funnel_grouped(body)
        data = raw.get('data', [])
        if isinstance(data, list):
            return [ProductFunnelHistory.from_api(item) for item in data]
        return []

    # ── Search Report ────────────────────────────────────────────────

    def get_search_report(
            self,
            start: str,
            end: str,
            *,
            nm_ids: list[int] | None = None,
            subject_ids: list[int] | None = None,
            brand_names: list[str] | None = None,
            limit: int = 20,
            offset: int = 0,
    ) -> dict:
        """Retrieve main search report page.

        Args:
            start: Current period start date (YYYY-MM-DD).
            end: Current period end date (YYYY-MM-DD).
            nm_ids: Filter by WB article numbers.
            subject_ids: Filter by subject IDs.
            brand_names: Filter by brand names.
            limit: Number of groups (max 1000).
            offset: Number of results to skip.

        Returns:
            Raw report data dict (complex nested structure).
        """
        body = self._build_search_body(
            start, end,
            nm_ids=nm_ids,
            subject_ids=subject_ids,
            brand_names=brand_names,
            limit=limit,
            offset=offset,
        )
        raw = self._client.get_search_report(body)
        return raw.get('data', {})

    def get_search_groups(
            self,
            start: str,
            end: str,
            *,
            nm_ids: list[int] | None = None,
            subject_ids: list[int] | None = None,
            brand_names: list[str] | None = None,
            limit: int = 20,
            offset: int = 0,
    ) -> list[SearchReportGroup]:
        """Retrieve search report groups with pagination.

        Args:
            start: Current period start date (YYYY-MM-DD).
            end: Current period end date (YYYY-MM-DD).
            nm_ids: Filter by WB article numbers.
            subject_ids: Filter by subject IDs.
            brand_names: Filter by brand names.
            limit: Number of groups (max 1000).
            offset: Number of results to skip.

        Returns:
            List of SearchReportGroup domain objects.
        """
        body = self._build_search_body(
            start, end,
            nm_ids=nm_ids,
            subject_ids=subject_ids,
            brand_names=brand_names,
            limit=limit,
            offset=offset,
        )
        raw = self._client.get_search_groups(body)
        data = raw.get('data', {})
        groups = data.get('groups', [])
        return [SearchReportGroup.from_api(g) for g in groups]

    def get_search_details(
            self,
            start: str,
            end: str,
            *,
            subject_id: int | None = None,
            brand_name: str | None = None,
            tag_id: int | None = None,
            nm_ids: list[int] | None = None,
            limit: int = 20,
            offset: int = 0,
    ) -> list[SearchReportProduct]:
        """Retrieve product details within a search report group.

        Args:
            start: Current period start date (YYYY-MM-DD).
            end: Current period end date (YYYY-MM-DD).
            subject_id: Subject ID filter for the group.
            brand_name: Brand name filter for the group.
            tag_id: Tag ID filter for the group.
            nm_ids: Filter by WB article numbers.
            limit: Number of products (max 1000).
            offset: Number of results to skip.

        Returns:
            List of SearchReportProduct domain objects.
        """
        body = self._build_search_body(
            start, end, nm_ids=nm_ids, limit=limit, offset=offset,
        )
        if subject_id is not None:
            body['subjectId'] = subject_id
        if brand_name is not None:
            body['brandName'] = brand_name
        if tag_id is not None:
            body['tagId'] = tag_id

        raw = self._client.get_search_details(body)
        data = raw.get('data', {})
        products = data.get('products', [])
        return [SearchReportProduct.from_api(p) for p in products]

    def get_search_texts(
            self,
            start: str,
            end: str,
            nm_id: int,
            *,
            limit: int = 30,
    ) -> list[SearchTextEntry]:
        """Retrieve top search texts for a product.

        Args:
            start: Current period start date (YYYY-MM-DD).
            end: Current period end date (YYYY-MM-DD).
            nm_id: Single WB article number.
            limit: Number of texts (max 100).

        Returns:
            List of SearchTextEntry domain objects.
        """
        body: dict = {
            'currentPeriod': {'start': start, 'end': end},
            'nmId': nm_id,
            'limit': min(limit, _MAX_SEARCH_TEXT_LIMIT),
            'includeSubstitutedSKUs': True,
            'includeSearchTexts': True,
        }
        raw = self._client.get_search_texts(body)
        data = raw.get('data', {})
        texts = data.get('searchTexts', [])
        return [SearchTextEntry.from_api(t) for t in texts]

    def get_search_orders(
            self,
            start: str,
            end: str,
            nm_id: int,
            search_texts: list[str],
    ) -> dict:
        """Retrieve orders and positions by product search texts.

        Args:
            start: Current period start date (YYYY-MM-DD).
            end: Current period end date (YYYY-MM-DD).
            nm_id: Single WB article number.
            search_texts: List of search query texts.

        Returns:
            Raw response data dict.
        """
        body: dict = {
            'currentPeriod': {'start': start, 'end': end},
            'nmId': nm_id,
            'searchTexts': search_texts,
            'includeSubstitutedSKUs': True,
            'includeSearchTexts': True,
        }
        raw = self._client.get_search_orders(body)
        return raw.get('data', {})

    # ── CSV Reports ──────────────────────────────────────────────────

    def create_csv_report(
            self,
            report_type: str,
            name: str,
            params: dict,
    ) -> CsvReportStatus:
        """Create a CSV report generation task.

        Args:
            report_type: Report type identifier (e.g. DETAIL_HISTORY_REPORT).
            name: User-defined report name.
            params: Report-specific parameters dict.

        Returns:
            CsvReportStatus with the new report ID.
        """
        report_id = str(uuid.uuid4())
        body = {
            'id': report_id,
            'reportType': report_type,
            'userReportName': name,
            'params': params,
        }
        self._client.create_report(body)
        return CsvReportStatus(id=report_id, name=name, status='WAITING')

    def list_csv_reports(
            self, download_ids: list[str] | None = None,
    ) -> list[CsvReportStatus]:
        """List CSV report generation tasks.

        Args:
            download_ids: Optional filter by report UUIDs.

        Returns:
            List of CsvReportStatus domain objects.
        """
        raw = self._client.list_reports(download_ids)
        data = raw.get('data', [])
        return [CsvReportStatus.from_api(item) for item in data]

    def retry_csv_report(self, download_id: str) -> str:
        """Retry a failed CSV report generation.

        Args:
            download_id: Report UUID to retry.

        Returns:
            Confirmation message.
        """
        raw = self._client.retry_report(download_id)
        return raw.get('data', 'Retry requested')

    def download_csv_report(
            self,
            download_id: str,
            output_path: Path,
    ) -> Path:
        """Download a generated CSV report ZIP file.

        Args:
            download_id: Report UUID to download.
            output_path: Destination file path.

        Returns:
            The path where the file was saved.
        """
        content = self._client.download_report(download_id)
        output_path.write_bytes(content)
        return output_path

    # ── Private helpers ──────────────────────────────────────────────

    def _build_search_body(
            self,
            start: str,
            end: str,
            *,
            nm_ids: list[int] | None = None,
            subject_ids: list[int] | None = None,
            brand_names: list[str] | None = None,
            limit: int = 20,
            offset: int = 0,
    ) -> dict:
        """Build common search report request body.

        Args:
            start: Period start date.
            end: Period end date.
            nm_ids: WB article number filter.
            subject_ids: Subject ID filter.
            brand_names: Brand name filter.
            limit: Result limit.
            offset: Result offset.

        Returns:
            Request body dict.
        """
        body: dict = {
            'currentPeriod': {'start': start, 'end': end},
            'positionCluster': 'all',
            'orderBy': {'field': 'openCard', 'mode': 'desc'},
            'includeSubstitutedSKUs': True,
            'includeSearchTexts': True,
            'limit': min(limit, _MAX_LIMIT),
            'offset': offset,
        }
        if nm_ids:
            body['nmIds'] = nm_ids
        if subject_ids:
            body['subjectIds'] = subject_ids
        if brand_names:
            body['brandNames'] = brand_names
        return body
