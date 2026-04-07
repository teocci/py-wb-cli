"""Prices & Discounts use-cases — fetch and filter product pricing data."""

from __future__ import annotations

from wb.client.prices import PricesClient
from wb.core.batching import paginate_all
from wb.domain.models import ProductPrice

__all__ = ['PricesService']

_PAGE_LIMIT = 1000


class PricesService:
    """Orchestrates product price fetching via the Prices & Discounts API.

    Pagination strategy: always fetch all pages client-side, then filter.
    The API's filterNmID only accepts a single NM ID, so querying N products
    would require N serial calls. A single paginated full-fetch is cheaper
    for any seller with fewer than ~10 000 products.

    Attributes:
        _client: Prices API client.
    """

    def __init__(self, client: PricesClient) -> None:
        self._client = client

    def get_prices(
            self,
            nm_ids: list[int] | None = None,
            min_discount: int | None = None,
    ) -> list[ProductPrice]:
        """Fetch product prices with optional filtering.

        Args:
            nm_ids: Optional list of NM IDs to include. None returns all products.
            min_discount: Optional minimum seller discount percentage.
                          Products with discount < min_discount are excluded.

        Returns:
            List of ProductPrice objects sorted by nm_id ascending.
        """
        raw_items = self._fetch_all_pages()
        prices = [ProductPrice.from_api(item) for item in raw_items]

        if nm_ids is not None:
            nm_id_set = set(nm_ids)
            prices = [p for p in prices if p.nm_id in nm_id_set]

        if min_discount is not None:
            prices = [p for p in prices if p.discount >= min_discount]

        return sorted(prices, key=lambda p: p.nm_id)

    def _fetch_all_pages(self) -> list[dict]:
        """Fetch all goods pages via auto-pagination.

        Uses :func:`wb.core.batching.paginate_all` with the standard
        offset-based sentinel: stops when a page returns fewer items than
        the page limit.

        Returns:
            Flat list of raw listGoods item dicts.
        """
        def _fetch(limit: int, offset: int) -> list[dict]:
            raw = self._client.list_goods(limit=limit, offset=offset)
            return raw.get('data', {}).get('listGoods') or []

        return paginate_all(_fetch, _PAGE_LIMIT)
