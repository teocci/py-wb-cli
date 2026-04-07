"""Batch chunking and auto-pagination utilities for the WB CLI.

Provides:
- :func:`chunk` — splits a list into sub-lists of at most ``size`` items,
  used transparently by services to stay within WB API per-request limits.
- :func:`paginate_all` — fetches all pages from an offset-based API endpoint
  and returns a single flat list.
"""

__all__ = ['chunk', 'paginate_all']

from collections.abc import Callable, Generator
from typing import TypeVar

_T = TypeVar('_T')


def chunk(items: list[_T], size: int) -> Generator[list[_T], None, None]:
    """Yield successive non-overlapping sub-lists of at most `size` items.

    Args:
        items: The full list to partition.
        size: Maximum items per chunk (must be >= 1).

    Yields:
        Sub-lists of length 1..size.

    Raises:
        ValueError: If size < 1.
    """
    if size < 1:
        raise ValueError(f'chunk size must be >= 1, got {size}')
    for i in range(0, len(items), size):
        yield items[i : i + size]


def paginate_all(
        fetch: Callable[[int, int], list[_T]],
        page_size: int,
) -> list[_T]:
    """Fetch all pages from an offset-based API endpoint.

    Calls ``fetch(page_size, offset)`` repeatedly with ``offset = 0,
    page_size, 2 * page_size, ...`` until a page returns fewer items than
    ``page_size``, which signals the last page.

    This is the standard pagination pattern used by the WB Prices &
    Analytics APIs. The same sentinel is used by
    :meth:`wb.services.prices.PricesService._fetch_all_pages`.

    Args:
        fetch: Callable with signature ``(limit: int, offset: int) -> list[T]``
            that returns one page of items.
        page_size: Number of items to request per page (must be >= 1).

    Returns:
        Flat list of all items concatenated across all pages.

    Raises:
        ValueError: If ``page_size < 1``.

    Example::

        items = paginate_all(
            fetch=lambda limit, offset: client.list_goods(limit, offset),
            page_size=1000,
        )
    """
    if page_size < 1:
        raise ValueError(f'page_size must be >= 1, got {page_size}')

    all_items: list[_T] = []
    offset = 0

    while True:
        page = fetch(page_size, offset)
        all_items.extend(page)
        if len(page) < page_size:
            break
        offset += page_size

    return all_items
