"""Tests for --compact JSON output mode in OutputRenderer."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from wb.core.output import OutputRenderer
from wb.domain.enums import OutputFormat, VerbosityLevel


def _capture_display(renderer: OutputRenderer, data, **kwargs) -> str:
    """Capture stdout from renderer.display() and return it."""
    captured: list[str] = []
    with patch('wb.core.output.typer.echo', side_effect=captured.append):
        renderer.display(data, **kwargs)
    return '\n'.join(captured)


def _make_renderer(compact: bool = False) -> OutputRenderer:
    return OutputRenderer(OutputFormat.JSON, VerbosityLevel.NORMAL, compact=compact)


class TestCompactJsonOutput:
    def test_compact_json_is_single_line(self):
        renderer = _make_renderer(compact=True)
        data = [{'nm_id': 1, 'orders': 10}, {'nm_id': 2, 'orders': 5}]

        calls: list[str] = []
        with patch('wb.core.output.typer.echo', side_effect=calls.append):
            renderer.display(data)

        assert len(calls) == 1
        output = calls[0]
        # Single line: no newlines within the JSON (the print call itself has no \n)
        assert '\n' not in output
        # Still valid JSON
        parsed = json.loads(output)
        assert len(parsed) == 2

    def test_non_compact_json_is_indented(self):
        renderer = _make_renderer(compact=False)
        data = {'nm_id': 1, 'orders': 10}

        calls: list[str] = []
        with patch('wb.core.output.typer.echo', side_effect=calls.append):
            renderer.display(data)

        output = calls[0]
        # Pretty-printed output contains newlines and spaces
        assert '\n' in output
        assert '  ' in output

    def test_compact_ignored_in_table_mode(self):
        renderer = OutputRenderer(OutputFormat.TABLE, VerbosityLevel.NORMAL, compact=True)
        headers = ['ID', 'Name']
        rows = [['1', 'Alpha'], ['2', 'Beta']]

        with patch('wb.core.output._stdout_console') as mock:
            mock.print.side_effect = lambda table: None
            # Should not raise; compact flag is a no-op for table mode
            renderer.display(rows, headers=headers, title='Test')

        # display was called without error — compact does not affect table rendering
        mock.print.assert_called_once()

    def test_compact_field_filter_combined(self):
        renderer = _make_renderer(compact=True)
        data = [{'nm_id': 1, 'orders': 10, 'opens': 500}]

        calls: list[str] = []
        with patch('wb.core.output.typer.echo', side_effect=calls.append):
            renderer.display(data, fields=['nm_id', 'orders'])

        output = calls[0]
        parsed = json.loads(output)
        assert parsed == [{'nm_id': 1, 'orders': 10}]
        assert '\n' not in output

    def test_compact_attribute_stored(self):
        r = _make_renderer(compact=True)
        assert r.compact is True
        r2 = _make_renderer(compact=False)
        assert r2.compact is False

    def test_compact_default_is_false(self):
        r = OutputRenderer(OutputFormat.JSON, VerbosityLevel.NORMAL)
        assert r.compact is False
