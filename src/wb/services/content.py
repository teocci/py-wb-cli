"""Service layer for the WB Content API — product card description editing.

Owns the **read-modify-write round-trip** that makes editing a description
safe against the destructive ``cards/update`` overwrite: the live card is
always re-fetched, only ``description`` is swapped, and the full card is sent
back so characteristics / sizes / dimensions survive untouched.

Bulk edits (``apply_updates``) fetch the whole card set once and diff against
it; single edits (``set_description``) fetch just the target card via
``textSearch``. Both classify each card as changed / unchanged / too-long /
not-found before any write, so ``--dry-run`` and the applied summary share one
code path. After a write, ``cards/error/list`` is polled and any failures —
keyed by WB on ``vendorCode`` — are mapped back to ``nmID`` and surfaced.
"""

from __future__ import annotations

import logging

from wb.client.content import ContentClient
from wb.core.constants import (
    CONTENT_DESCRIPTION_MAX_LENGTH,
    CONTENT_UPDATE_BATCH_LIMIT,
)
from wb.core.exceptions import ApiError
from wb.domain.content import (
    STATUS_CHANGED,
    STATUS_NOT_FOUND,
    STATUS_TOO_LONG,
    STATUS_UNCHANGED,
    CardUpdateResult,
    ProductCard,
)

__all__ = ['ContentService']

logger = logging.getLogger(__name__)


class ContentService:
    """Coordinate :class:`ContentClient` calls and the description round-trip.

    Attributes:
        _client: Underlying Content API client.
    """

    def __init__(self, client: ContentClient) -> None:
        self._client = client

    # ── Reads ─────────────────────────────────────────────────────────

    def list_cards(
            self,
            *,
            text_search: str | None = None,
            brands: list[str] | None = None,
            nm_ids: list[int] | None = None,
            limit: int | None = None,
    ) -> list[ProductCard]:
        """Return cards, optionally filtered by text/brand/NM IDs.

        Args:
            text_search: Seller article / WB article / SKU filter (WB-side).
            brands: Brand-name filter (WB-side).
            nm_ids: Client-side exact NM ID filter (disables ``limit``).
            limit: Cap on cards fetched when ``nm_ids`` is not given.

        Returns:
            Parsed :class:`ProductCard` list.
        """
        max_cards = None if nm_ids else limit
        raw = self._client.get_cards_list(
            text_search=text_search, brands=brands, max_cards=max_cards,
        )
        cards = [ProductCard.from_api(r) for r in raw]
        if nm_ids:
            wanted = set(nm_ids)
            cards = [c for c in cards if c.nm_id in wanted]
        return cards

    def get_card(self, nm_id: int) -> ProductCard | None:
        """Fetch a single card by NM ID via ``textSearch`` (exact match).

        Args:
            nm_id: WB article.

        Returns:
            The card, or ``None`` when WB returns no exact match.
        """
        for raw in self._client.get_cards_list(text_search=str(nm_id)):
            if raw.get('nmID') == nm_id:
                return ProductCard.from_api(raw)
        return None

    def export_descriptions(
            self,
            *,
            text_search: str | None = None,
            brands: list[str] | None = None,
    ) -> list[dict]:
        """Dump every card's editable identity + description for offline edit.

        Args:
            text_search: Optional WB-side text filter.
            brands: Optional WB-side brand filter.

        Returns:
            List of ``{nmID, vendorCode, title, description}`` dicts — the
            shape :meth:`apply_updates` reads back (only ``description`` is
            used on apply; the rest is human context).
        """
        return [
            {
                'nmID': card.nm_id,
                'vendorCode': card.vendor_code,
                'title': card.title,
                'description': card.description,
            }
            for card in self.list_cards(text_search=text_search, brands=brands)
        ]

    # ── Writes (round-trip) ───────────────────────────────────────────

    def apply_updates(
            self,
            updates: dict[int, str],
            *,
            dry_run: bool = False,
    ) -> tuple[list[CardUpdateResult], list[str]]:
        """Bulk-apply ``nmID → new description`` edits via the round-trip.

        Fetches all live cards once, classifies each requested edit, and (unless
        ``dry_run``) overwrites only the changed ones in batches of
        ≤3000. Unchanged / over-length / unknown NM IDs are reported, never sent.

        Args:
            updates: Map of WB article → replacement description.
            dry_run: When True, classify only — no write, no error poll.

        Returns:
            ``(results, errors)`` — per-card outcomes and human-readable
            post-update error strings (empty on dry-run or clean apply).
        """
        live = self._fetch_card_map()
        results: list[CardUpdateResult] = []
        payloads: list[dict] = []
        vendor_to_nm: dict[str, int] = {}

        for nm_id, new_desc in updates.items():
            card = live.get(nm_id)
            if card is None:
                results.append(
                    CardUpdateResult(nm_id, '', 0, len(new_desc), STATUS_NOT_FOUND),
                )
                continue
            result = _evaluate(nm_id, card.vendor_code, card.description, new_desc)
            results.append(result)
            if result.status == STATUS_CHANGED:
                payloads.append(card.to_update_payload(new_desc))
                vendor_to_nm[card.vendor_code] = nm_id

        if dry_run or not payloads:
            return results, []
        self._push(payloads)
        return results, self._confirm(vendor_to_nm)

    def set_description(
            self,
            nm_id: int,
            description: str,
            *,
            dry_run: bool = False,
    ) -> tuple[CardUpdateResult, list[str]]:
        """Set one card's description via the round-trip.

        Fetches just the target card (cheap ``textSearch``), classifies the
        edit, and writes only when it actually changes.

        Args:
            nm_id: WB article.
            description: Replacement description.
            dry_run: When True, classify only — no write.

        Returns:
            ``(result, errors)`` for the single card.
        """
        card = self.get_card(nm_id)
        if card is None:
            return CardUpdateResult(nm_id, '', 0, len(description), STATUS_NOT_FOUND), []
        result = _evaluate(nm_id, card.vendor_code, card.description, description)
        if dry_run or result.status != STATUS_CHANGED:
            return result, []
        self._push([card.to_update_payload(description)])
        return result, self._confirm({card.vendor_code: nm_id})

    # ── Internals ─────────────────────────────────────────────────────

    def _fetch_card_map(self) -> dict[int, ProductCard]:
        """Fetch all cards into an ``nm_id → ProductCard`` map."""
        return {
            card.nm_id: card
            for card in (ProductCard.from_api(r) for r in self._client.get_cards_list())
        }

    def _push(self, payloads: list[dict]) -> None:
        """POST update payloads in ≤3000-card batches; raise on WB error flag.

        Args:
            payloads: Fully-formed card-update objects.

        Raises:
            ApiError: When a batch response carries ``error: true`` (a
                synchronous rejection — distinct from per-card async errors).
        """
        for start in range(0, len(payloads), CONTENT_UPDATE_BATCH_LIMIT):
            chunk = payloads[start:start + CONTENT_UPDATE_BATCH_LIMIT]
            response = self._client.update_cards(chunk)
            if response.get('error'):
                raise ApiError(response.get('errorText') or 'cards/update returned an error')

    def _confirm(self, vendor_to_nm: dict[str, int]) -> list[str]:
        """Map post-update errors (keyed by vendorCode) back to NM IDs.

        Args:
            vendor_to_nm: ``vendorCode → nmID`` for the cards just submitted.

        Returns:
            ``nmID (vendorCode): message`` strings for any of our cards that
            appear in the failed-card report.
        """
        if not vendor_to_nm:
            return []
        messages: list[str] = []
        for batch in self._client.list_errors():
            for vendor_code, errors in (batch.get('errors') or {}).items():
                if vendor_code not in vendor_to_nm:
                    continue
                nm_id = vendor_to_nm[vendor_code]
                messages.extend(
                    f'nmID {nm_id} ({vendor_code}): {msg}' for msg in (errors or [])
                )
        return messages


def _evaluate(
        nm_id: int,
        vendor_code: str,
        old_description: str,
        new_description: str,
) -> CardUpdateResult:
    """Classify one requested edit without contacting WB.

    Args:
        nm_id: WB article.
        vendor_code: Seller's article.
        old_description: Current description on WB.
        new_description: Requested replacement.

    Returns:
        A :class:`CardUpdateResult` with status changed / unchanged / too-long.
    """
    old_len = len(old_description or '')
    new_len = len(new_description)
    if new_len > CONTENT_DESCRIPTION_MAX_LENGTH:
        status = STATUS_TOO_LONG
    elif new_description == (old_description or ''):
        status = STATUS_UNCHANGED
    else:
        status = STATUS_CHANGED
    return CardUpdateResult(nm_id, vendor_code, old_len, new_len, status)
