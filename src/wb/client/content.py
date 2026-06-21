"""Typed HTTP client for the WB Content API — product card read/update.

Three POST endpoints (host ``content-api.wildberries.ru``):

- ``get/cards/list`` — cursor-paginated card export (this client walks the
  whole cursor and returns every raw card dict).
- ``cards/update`` — destructive full-overwrite edit (caller supplies the
  fully-formed card array; chunking ≤3000 is the service's job).
- ``cards/error/list`` — failed-card report, used to confirm an update.

Returns raw API structures; domain conversion lives in
:class:`wb.services.content.ContentService`.
"""

from __future__ import annotations

from typing import Any

from wb.client.http import WbHttpClient
from wb.core.constants import (
    CONTENT_CARDS_PAGE_LIMIT,
    EP_CONTENT_CARDS_ERROR_LIST,
    EP_CONTENT_CARDS_LIST,
    EP_CONTENT_CARDS_UPDATE,
)

__all__ = ['ContentClient']

# withPhoto filter values; -1 returns cards regardless of photo presence so a
# description export is never silently truncated to photographed cards only.
_WITH_PHOTO_ALL = -1
# Safety stop for the cursor loop in case WB never reports a short page.
_MAX_PAGES = 1000


class ContentClient:
    """Typed wrapper around :class:`WbHttpClient` for the WB Content API.

    Auth uses the profile's ``content`` token, passed as
    ``Authorization: <token>`` (no ``Bearer`` prefix) by WbHttpClient.

    Attributes:
        _http: HTTP client pointed at the Content API base URL.
    """

    def __init__(self, http: WbHttpClient) -> None:
        self._http = http

    def get_cards_list(
            self,
            *,
            text_search: str | None = None,
            brands: list[str] | None = None,
            page_limit: int = CONTENT_CARDS_PAGE_LIMIT,
            max_cards: int | None = None,
    ) -> list[dict]:
        """Walk the cursor and return every matching card.

        Pagination follows the WB recipe: repeat with the response cursor's
        ``updatedAt``/``nmID`` until the page ``total`` is below the request
        ``limit`` (or an empty page arrives).

        Args:
            text_search: Optional seller article / WB article / SKU filter.
            brands: Optional brand-name filter.
            page_limit: Cards per page (WB max 100).
            max_cards: Optional hard cap on cards returned.

        Returns:
            List of raw card dicts.
        """
        limit = min(page_limit, CONTENT_CARDS_PAGE_LIMIT)
        cursor: dict[str, Any] = {'limit': limit}
        cards: list[dict] = []

        for _ in range(_MAX_PAGES):
            body = self._build_list_body(cursor, text_search, brands)
            result = self._http.post(EP_CONTENT_CARDS_LIST, json_body=body)
            result = result if isinstance(result, dict) else {}
            page = result.get('cards') or []
            cards.extend(page)

            if max_cards is not None and len(cards) >= max_cards:
                return cards[:max_cards]

            resp_cursor = result.get('cursor') or {}
            if not page or resp_cursor.get('total', 0) < limit:
                break
            cursor = {
                'limit': limit,
                'updatedAt': resp_cursor.get('updatedAt'),
                'nmID': resp_cursor.get('nmID'),
            }
        return cards

    @staticmethod
    def _build_list_body(
            cursor: dict[str, Any],
            text_search: str | None,
            brands: list[str] | None,
    ) -> dict:
        """Assemble the ``get/cards/list`` request body."""
        card_filter: dict[str, Any] = {'withPhoto': _WITH_PHOTO_ALL}
        if text_search:
            card_filter['textSearch'] = text_search
        if brands:
            card_filter['brands'] = brands
        return {
            'settings': {
                'sort': {'ascending': False},
                'filter': card_filter,
                'cursor': dict(cursor),
            },
        }

    def update_cards(self, cards: list[dict]) -> dict:
        """POST ``cards/update`` with a fully-formed card array.

        Args:
            cards: Card objects (≤3000) already shaped for the overwrite.

        Returns:
            Raw response dict ``{data, error, errorText, additionalErrors}``;
            empty dict if WB returns a non-dict body.
        """
        result = self._http.post(EP_CONTENT_CARDS_UPDATE, json_body=cards)
        return result if isinstance(result, dict) else {}

    def list_errors(self, *, limit: int = CONTENT_CARDS_PAGE_LIMIT) -> list[dict]:
        """POST ``cards/error/list`` and return the error batches.

        Args:
            limit: Batches per page (single page is enough to confirm a
                just-submitted update).

        Returns:
            List of batch dicts; each carries ``vendorCodes`` and an
            ``errors`` map keyed by vendor code.
        """
        body = {'cursor': {'limit': limit}, 'order': {'ascending': False}}
        result = self._http.post(EP_CONTENT_CARDS_ERROR_LIST, json_body=body)
        result = result if isinstance(result, dict) else {}
        data = result.get('data') or {}
        return data.get('items') or []
