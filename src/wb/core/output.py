"""Output rendering utilities for the WB CLI.

Provides functions and a dispatcher class for rendering data as
rich tables, JSON, or styled messages to the console.
"""

__all__ = [
    'render_json',
    'render_table',
    'render_error',
    'render_success',
    'OutputRenderer',
]

import json
from typing import Any

from rich.console import Console
from rich.table import Table

from wb.domain.enums import OutputFormat, VerbosityLevel

# Module-level consoles to avoid repeated instantiation
_stdout_console = Console()
_stderr_console = Console(stderr=True)


def render_json(data: Any) -> str:
    """Serialize data to a pretty-printed JSON string.

    Args:
        data: Any JSON-serializable value.

    Returns:
        Indented JSON string.
    """
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def render_table(
        headers: list[str],
        rows: list[list[str]],
        title: str | None = None,
) -> None:
    """Print a rich table to stdout.

    Args:
        headers: Column header labels.
        rows: Row data; each inner list corresponds to one row.
        title: Optional table title displayed above the header row.
    """
    table = Table(title=title, show_lines=False)
    for header in headers:
        table.add_column(header)
    for row in rows:
        table.add_row(*row)
    _stdout_console.print(table)


def render_error(
        message: str,
        details: dict | None = None,
) -> None:
    """Print an error message to stderr.

    Args:
        message: Primary error description.
        details: Optional key-value pairs with additional context.
    """
    _stderr_console.print(f'[bold red]Error:[/bold red] {message}')
    if details:
        for key, value in details.items():
            _stderr_console.print(f'  [dim]{key}:[/dim] {value}')


def render_success(message: str) -> None:
    """Print a success message to stdout.

    Args:
        message: Success description.
    """
    _stdout_console.print(f'[bold green]Success:[/bold green] {message}')


def _filter_fields(data: Any, fields: list[str] | None) -> Any:
    """Filter dict keys or list-of-dicts to only the specified fields.

    Args:
        data: Value to filter.
        fields: Field names to keep. None means keep all.

    Returns:
        Filtered data with only the requested keys, or original if no filter.
    """
    if fields is None:
        return data
    field_set = set(fields)
    if isinstance(data, list):
        return [
            {k: v for k, v in item.items() if k in field_set}
            if isinstance(item, dict) else item
            for item in data
        ]
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if k in field_set}
    return data


class OutputRenderer:
    """Dispatches output to the appropriate renderer based on format and verbosity.

    Attributes:
        output_format: Active output format (table, json, quiet).
        verbosity: Active verbosity level.
    """

    def __init__(
            self,
            output_format: OutputFormat,
            verbosity: VerbosityLevel,
    ) -> None:
        self.output_format = output_format
        self.verbosity = verbosity

    @property
    def is_json(self) -> bool:
        """True when JSON output format is active."""
        return self.output_format == OutputFormat.JSON

    def display(
            self,
            data: Any,
            headers: list[str] | None = None,
            title: str | None = None,
            fields: list[str] | None = None,
    ) -> None:
        """Render data according to the configured output format.

        Args:
            data: Payload to render. For JSON format this is serialized
                directly; for table format it should be a list of lists.
            headers: Column headers (required for table format).
            title: Optional title for table output.
            fields: If provided, filter output to only these fields/columns.
                For JSON: keys are filtered from dicts. For table: columns
                whose header labels match (case-insensitive) are included.
        """
        if self.output_format == OutputFormat.QUIET:
            return

        if self.output_format == OutputFormat.JSON:
            _stdout_console.print(
                render_json(_filter_fields(data, fields)), highlight=False,
            )
            return

        if headers is None:
            # Fall back to JSON when no headers are available for a table
            _stdout_console.print(
                render_json(_filter_fields(data, fields)), highlight=False,
            )
            return

        if fields is not None:
            keep = {f.lower() for f in fields}
            indices = [i for i, h in enumerate(headers) if h.lower() in keep]
            headers = [headers[i] for i in indices]
            data = [[row[i] for i in indices] for row in data]

        render_table(headers, data, title=title)

    def error(
            self,
            message: str,
            details: dict | None = None,
    ) -> None:
        """Render an error message regardless of output format.

        When JSON output is active, emits a structured JSON error
        to stdout so agents can parse it programmatically.

        Args:
            message: Primary error description.
            details: Optional additional context.
        """
        if self.is_json:
            error_data: dict = {'status': 'error', 'error': {'message': message}}
            if details:
                error_data['error']['details'] = details
            _stdout_console.print(render_json(error_data), highlight=False)
            return
        render_error(message, details=details)

    def success(self, message: str) -> None:
        """Render a success message unless in quiet mode.

        Args:
            message: Success description.
        """
        if self.verbosity == VerbosityLevel.QUIET:
            return
        render_success(message)

    def verbose(self, message: str) -> None:
        """Render a diagnostic message only when verbosity is VERBOSE.

        Args:
            message: Diagnostic information.
        """
        if self.verbosity != VerbosityLevel.VERBOSE:
            return
        _stderr_console.print(f'[dim]{message}[/dim]')
