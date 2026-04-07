"""Tests for wb.core.batching.chunk() and paginate_all()."""

from __future__ import annotations

import pytest

from wb.core.batching import chunk, paginate_all


class TestChunk:
    """Tests for the chunk() generator utility."""

    def test_empty_list_yields_nothing(self):
        result = list(chunk([], 10))
        assert result == []

    def test_single_element(self):
        result = list(chunk([42], 10))
        assert result == [[42]]

    def test_exact_fit(self):
        result = list(chunk([1, 2, 3], 3))
        assert result == [[1, 2, 3]]

    def test_splits_evenly(self):
        result = list(chunk([1, 2, 3, 4], 2))
        assert result == [[1, 2], [3, 4]]

    def test_last_chunk_is_smaller(self):
        result = list(chunk([1, 2, 3, 4, 5], 2))
        assert result == [[1, 2], [3, 4], [5]]

    def test_size_one_yields_singletons(self):
        result = list(chunk([10, 20, 30], 1))
        assert result == [[10], [20], [30]]

    def test_size_larger_than_list(self):
        result = list(chunk([1, 2, 3], 100))
        assert result == [[1, 2, 3]]

    def test_original_order_preserved(self):
        items = list(range(25))
        chunks = list(chunk(items, 10))
        assert chunks[0] == list(range(10))
        assert chunks[1] == list(range(10, 20))
        assert chunks[2] == list(range(20, 25))

    def test_size_zero_raises(self):
        with pytest.raises(ValueError, match='chunk size must be >= 1'):
            list(chunk([1, 2], 0))

    def test_negative_size_raises(self):
        with pytest.raises(ValueError, match='chunk size must be >= 1'):
            list(chunk([1, 2], -5))

    def test_returns_lists_not_tuples(self):
        result = list(chunk([1, 2, 3], 2))
        for c in result:
            assert isinstance(c, list)

    def test_is_generator(self):
        from collections.abc import Generator
        result = chunk([1, 2, 3], 2)
        assert isinstance(result, Generator)


class TestPaginateAll:
    """Tests for the paginate_all() offset-based pagination helper."""

    def test_single_page_shorter_than_page_size(self):
        """A page shorter than page_size signals the last (only) page."""
        calls = []

        def fetch(limit, offset):
            calls.append((limit, offset))
            return [1, 2, 3]  # 3 < page_size=10

        result = paginate_all(fetch, page_size=10)
        assert result == [1, 2, 3]
        assert calls == [(10, 0)]

    def test_multi_page_stops_on_short_page(self):
        """Full page triggers next fetch; short page stops iteration."""
        pages = [[1, 2], [3, 4], [5]]  # page_size=2; last page has 1 item

        def fetch(limit, offset):
            return pages[offset // limit]

        result = paginate_all(fetch, page_size=2)
        assert result == [1, 2, 3, 4, 5]

    def test_empty_first_page_returns_empty_list(self):
        result = paginate_all(lambda limit, offset: [], page_size=10)
        assert result == []

    def test_exact_multiple_then_empty(self):
        """When page == page_size, fetch next page; empty next page stops."""
        responses = {0: [10, 20], 2: []}  # page_size=2

        def fetch(limit, offset):
            return responses.get(offset, [])

        result = paginate_all(fetch, page_size=2)
        assert result == [10, 20]

    def test_two_full_pages_then_partial(self):
        """Three fetches: two full pages and one partial."""
        def fetch(limit, offset):
            if offset == 0:
                return list(range(5))
            if offset == 5:
                return list(range(5, 10))
            return [99]  # partial

        result = paginate_all(fetch, page_size=5)
        assert result == list(range(10)) + [99]

    def test_page_size_one(self):
        """Smallest valid page size — fetches one item at a time."""
        def fetch(limit, offset):
            return [offset] if offset < 3 else []

        result = paginate_all(fetch, page_size=1)
        assert result == [0, 1, 2]

    def test_page_size_zero_raises(self):
        with pytest.raises(ValueError, match='page_size must be >= 1'):
            paginate_all(lambda l, o: [], page_size=0)

    def test_page_size_negative_raises(self):
        with pytest.raises(ValueError, match='page_size must be >= 1'):
            paginate_all(lambda l, o: [], page_size=-5)

    def test_fetch_receives_correct_limit_and_offset(self):
        """Verify the exact (limit, offset) values passed to each fetch call."""
        calls = []

        def fetch(limit, offset):
            calls.append((limit, offset))
            return [1, 2, 3] if offset == 0 else [4]  # second call is partial

        paginate_all(fetch, page_size=3)
        assert calls == [(3, 0), (3, 3)]

    def test_result_is_flat_list(self):
        """Items from all pages are concatenated into a single flat list."""
        def fetch(limit, offset):
            return ['a', 'b'] if offset == 0 else ['c']

        result = paginate_all(fetch, page_size=2)
        assert result == ['a', 'b', 'c']
        assert isinstance(result, list)
