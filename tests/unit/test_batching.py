"""Tests for wb.core.batching.chunk()."""

from __future__ import annotations

import pytest

from wb.core.batching import chunk


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
