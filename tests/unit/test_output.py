"""Tests for wb.core.output module."""

import json

import pytest

from wb.core.output import OutputRenderer, render_json
from wb.domain.enums import OutputFormat, VerbosityLevel


class TestRenderJson:
    """Tests for the render_json function."""

    def test_produces_valid_json(self) -> None:
        data = {'key': 'value', 'count': 42}
        result = render_json(data)
        parsed = json.loads(result)
        assert parsed == data

    def test_handles_list(self) -> None:
        data = [1, 2, 3]
        result = render_json(data)
        assert json.loads(result) == data

    def test_handles_nested_structure(self) -> None:
        data = {'items': [{'id': 1}, {'id': 2}]}
        result = render_json(data)
        assert json.loads(result) == data

    def test_pretty_printed(self) -> None:
        data = {'a': 1}
        result = render_json(data)
        # Pretty-printed JSON should contain newlines
        assert '\n' in result

    def test_non_ascii_preserved(self) -> None:
        data = {'name': '\u0422\u0435\u0441\u0442'}
        result = render_json(data)
        assert '\u0422\u0435\u0441\u0442' in result


class TestOutputRendererJsonFormat:
    """Tests for OutputRenderer with JSON output format."""

    def test_display_outputs_json(self, capsys: pytest.CaptureFixture) -> None:
        renderer = OutputRenderer(
            output_format=OutputFormat.JSON,
            verbosity=VerbosityLevel.NORMAL,
        )
        data = {'campaigns': [1, 2, 3]}
        renderer.display(data)
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed == data


class TestOutputRendererQuietFormat:
    """Tests for OutputRenderer with QUIET format."""

    def test_display_suppresses_output(self, capsys: pytest.CaptureFixture) -> None:
        renderer = OutputRenderer(
            output_format=OutputFormat.QUIET,
            verbosity=VerbosityLevel.NORMAL,
        )
        renderer.display({'data': 'secret'})
        captured = capsys.readouterr()
        assert captured.out == ''

    def test_success_suppressed_when_quiet_verbosity(
        self, capsys: pytest.CaptureFixture,
    ) -> None:
        renderer = OutputRenderer(
            output_format=OutputFormat.TABLE,
            verbosity=VerbosityLevel.QUIET,
        )
        renderer.success('all done')
        captured = capsys.readouterr()
        assert captured.out == ''

    def test_error_still_shown_in_quiet_mode(
        self, capsys: pytest.CaptureFixture,
    ) -> None:
        renderer = OutputRenderer(
            output_format=OutputFormat.QUIET,
            verbosity=VerbosityLevel.QUIET,
        )
        renderer.error('something broke')
        captured = capsys.readouterr()
        assert 'something broke' in captured.err
