"""Domain models for the WB Content API — product cards and description edits.

A :class:`ProductCard` is the subset of the ``/content/v2/get/cards/list``
response the CLI needs to *read* descriptions and to *round-trip* an edit
safely. ``cards/update`` is a destructive full-overwrite, so the editable
fields (``brand``/``title``/``characteristics``/``sizes``/``dimensions``)
are carried verbatim and re-sent unchanged; only ``description`` is swapped.

The read response carries a few fields the update payload must drop
(``dimensions.isValid``, ``characteristics[].name``) — :meth:`to_update_payload`
strips them so a faithful round-trip does not trip WB validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ['ProductCard', 'CardUpdateResult']

# Per-card outcome statuses used by the service/CLI for dry-run and apply.
STATUS_CHANGED = 'changed'
STATUS_UNCHANGED = 'unchanged'
STATUS_TOO_LONG = 'too-long'
STATUS_NOT_FOUND = 'not-found'

# Dimension sub-fields accepted by cards/update (read adds a read-only
# ``isValid`` flag that the writer rejects).
_UPDATE_DIMENSION_KEYS = ('length', 'width', 'height', 'weightBrutto')
# Size sub-fields preserved on update for an existing size. ``price`` is only
# meaningful when adding a new size, so it is carried only when present.
_UPDATE_SIZE_KEYS = ('chrtID', 'techSize', 'wbSize', 'price', 'skus')


@dataclass(slots=True)
class ProductCard:
    """A product card as needed for reading and round-tripping descriptions.

    Attributes:
        nm_id: WB article (``nmID``).
        vendor_code: Seller's article (``vendorCode``).
        brand: Brand name.
        title: Product title.
        description: Current product description.
        dimensions: Raw ``dimensions`` object from the read response.
        characteristics: Raw ``characteristics`` list (``[{id, name, value}]``).
        sizes: Raw ``sizes`` list (``[{chrtID, techSize, wbSize, skus}]``).
    """

    nm_id: int
    vendor_code: str
    brand: str
    title: str
    description: str
    dimensions: dict = field(default_factory=dict)
    characteristics: list[dict] = field(default_factory=list)
    sizes: list[dict] = field(default_factory=list)

    @property
    def description_length(self) -> int:
        """Character count of the current description."""
        return len(self.description or '')

    @classmethod
    def from_api(cls, raw: dict) -> ProductCard:
        """Build a card from one ``get/cards/list`` card object.

        Args:
            raw: A single card dict from the ``cards`` array.

        Returns:
            Parsed :class:`ProductCard`. Null/missing collections become
            empty, so an unedited round-trip never crashes on ``None``.
        """
        return cls(
            nm_id=raw.get('nmID', 0),
            vendor_code=raw.get('vendorCode') or '',
            brand=raw.get('brand') or '',
            title=raw.get('title') or '',
            description=raw.get('description') or '',
            dimensions=raw.get('dimensions') or {},
            characteristics=raw.get('characteristics') or [],
            sizes=raw.get('sizes') or [],
        )

    def to_update_payload(self, description: str | None = None) -> dict:
        """Build the ``cards/update`` payload for this card.

        Sends back every editable field unchanged except ``description``,
        which is replaced when ``description`` is given. Read-only sub-fields
        (``dimensions.isValid``, ``characteristics[].name``) are stripped.

        Args:
            description: Replacement description; ``None`` keeps the current.

        Returns:
            One card object ready for the ``cards/update`` array.
        """
        return {
            'nmID': self.nm_id,
            'vendorCode': self.vendor_code,
            'brand': self.brand,
            'title': self.title,
            'description': self.description if description is None else description,
            'dimensions': self._update_dimensions(),
            'characteristics': self._update_characteristics(),
            'sizes': self._update_sizes(),
        }

    def _update_dimensions(self) -> dict:
        """Keep only the writable dimension keys."""
        return {
            k: self.dimensions[k]
            for k in _UPDATE_DIMENSION_KEYS
            if k in self.dimensions
        }

    def _update_characteristics(self) -> list[dict]:
        """Reduce read characteristics to the writable ``{id, value}`` shape."""
        out: list[dict] = []
        for char in self.characteristics:
            if char.get('id') is None:
                continue
            out.append({'id': char['id'], 'value': char.get('value')})
        return out

    def _update_sizes(self) -> list[dict]:
        """Carry each size's writable keys (``price`` only when present)."""
        return [
            {k: size[k] for k in _UPDATE_SIZE_KEYS if k in size}
            for size in self.sizes
        ]


@dataclass(slots=True)
class CardUpdateResult:
    """Per-card outcome of an export-edit-apply or single set-description.

    Used both for ``--dry-run`` preview and the applied summary.

    Attributes:
        nm_id: WB article the result is for.
        vendor_code: Seller's article (context; empty when not found).
        old_length: Length of the current description on WB.
        new_length: Length of the requested new description.
        status: One of ``changed`` / ``unchanged`` / ``too-long`` / ``not-found``.
    """

    nm_id: int
    vendor_code: str
    old_length: int
    new_length: int
    status: str
