"""Batch chunking utilities for the WB CLI.

Provides a generic chunk() generator that splits any sequence into
sub-lists of at most `size` items, used transparently by services
to stay within WB API per-request limits.
"""

__all__ = ['chunk']

from collections.abc import Generator
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
