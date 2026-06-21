"""CLI commands for product card description management (Content API).

`wb content` reads and edits product card descriptions:

- ``list`` / ``get`` / ``export`` — read descriptions (single, bulk, to file).
- ``apply`` / ``set-description`` — write via the safe read-modify-write
  round-trip (the live card is re-fetched and only ``description`` is swapped).

Every write supports ``--dry-run`` (diff only) and confirms via WB's
failed-card report after applying.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import typer

from wb.cli._helpers import (
    confirm_or_abort,
    get_fields,
    get_profile,
    get_renderer,
)
from wb.core.constants import ExitCode
from wb.core.exceptions import WbCliError
from wb.core.output import render_table
from wb.domain.content import STATUS_CHANGED, STATUS_TOO_LONG, CardUpdateResult

__all__ = ['content_app']

# Title column width in table mode — descriptions are shown by length only.
_TITLE_TRUNCATE = 40

content_app = typer.Typer(
    help='Read & edit product card descriptions (Content API)',
    no_args_is_help=True,
)


def _get_content_service(profile: str | None = None):
    """Create a ContentService from current settings."""
    from wb.services._factory import create_content_service
    return create_content_service(profile)


def _parse_nm_ids(value: str) -> list[int]:
    """Parse a comma-separated NM ID string into a list of ints."""
    try:
        return [int(x.strip()) for x in value.split(',') if x.strip()]
    except ValueError as exc:
        raise typer.BadParameter('--nms must be comma-separated integers') from exc


# ── Reads ─────────────────────────────────────────────────────────────

@content_app.command('list')
def content_list(
        ctx: typer.Context,
        text: str | None = typer.Option(None, '--text', help='Filter by article / WB article / SKU'),
        brand: str | None = typer.Option(None, '--brand', help='Filter by brand name'),
        nms: str | None = typer.Option(None, '--nms', help='Comma-separated NM IDs (client-side filter)'),
        limit: int | None = typer.Option(None, '--limit', help='Max cards to fetch'),
) -> None:
    """List product cards with their description lengths."""
    renderer = get_renderer(ctx)
    profile = get_profile(ctx)
    nm_ids = _parse_nm_ids(nms) if nms else None

    try:
        svc = _get_content_service(profile)
        cards = svc.list_cards(text_search=text, brands=[brand] if brand else None,
                               nm_ids=nm_ids, limit=limit)
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=_exit_for(exc)) from exc

    if not cards:
        renderer.success('No cards found.')
        return

    if renderer.is_json:
        fields = get_fields(ctx)
        data = [
            {
                'nmID': c.nm_id, 'vendorCode': c.vendor_code, 'title': c.title,
                'descriptionLength': c.description_length, 'description': c.description,
            }
            for c in cards
        ]
        if fields:
            data = [{k: v for k, v in row.items() if k in fields} for row in data]
        typer.echo(json.dumps(data, indent=2, ensure_ascii=False))
        return

    rows = [
        [str(c.nm_id), c.vendor_code or '—', _truncate(c.title), str(c.description_length)]
        for c in cards
    ]
    render_table(['NM ID', 'Vendor Code', 'Title', 'Desc Len'], rows,
                 title=f'Product Cards ({len(cards)})')


@content_app.command('get')
def content_get(
        ctx: typer.Context,
        nm: int = typer.Option(..., '--nm', help='WB article (NM ID)'),
) -> None:
    """Show one card's full description text."""
    renderer = get_renderer(ctx)
    profile = get_profile(ctx)

    try:
        card = _get_content_service(profile).get_card(nm)
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=_exit_for(exc)) from exc

    if card is None:
        renderer.error(f'No card found for NM ID {nm}.')
        raise typer.Exit(code=ExitCode.VALIDATION_ERROR)

    if renderer.is_json:
        typer.echo(json.dumps({
            'nmID': card.nm_id, 'vendorCode': card.vendor_code, 'title': card.title,
            'descriptionLength': card.description_length, 'description': card.description,
        }, indent=2, ensure_ascii=False))
        return

    typer.echo(card.description)


@content_app.command('export')
def content_export(
        ctx: typer.Context,
        out: Path = typer.Option(..., '--out', help='Output JSON file path'),
        text: str | None = typer.Option(None, '--text', help='Filter by article / WB article / SKU'),
        brand: str | None = typer.Option(None, '--brand', help='Filter by brand name'),
) -> None:
    """Export all descriptions to an editable JSON file."""
    renderer = get_renderer(ctx)
    profile = get_profile(ctx)

    try:
        records = _get_content_service(profile).export_descriptions(
            text_search=text, brands=[brand] if brand else None,
        )
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=_exit_for(exc)) from exc

    out.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding='utf-8')
    renderer.success(f'Exported {len(records)} descriptions to {out}')


# ── Writes ────────────────────────────────────────────────────────────

@content_app.command('apply')
def content_apply(
        ctx: typer.Context,
        file: Path = typer.Option(..., '--file', help='JSON file of {nmID, description} edits'),
        dry_run: bool = typer.Option(False, '--dry-run', help='Preview the diff without writing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip the confirmation prompt'),
) -> None:
    """Bulk-apply description edits from a JSON file (round-trip update)."""
    renderer = get_renderer(ctx)
    profile = get_profile(ctx)

    try:
        updates = _load_updates_file(file)
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=ExitCode.VALIDATION_ERROR) from exc

    if not dry_run:
        confirm_or_abort(renderer, f'update {len(updates)} description(s)', yes)

    try:
        results, errors = _get_content_service(profile).apply_updates(updates, dry_run=dry_run)
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=_exit_for(exc)) from exc

    _render_outcome(ctx, renderer, results, errors, dry_run=dry_run)


@content_app.command('set-description')
def content_set_description(
        ctx: typer.Context,
        nm: int = typer.Option(..., '--nm', help='WB article (NM ID)'),
        text: str | None = typer.Option(None, '--text', help='New description text'),
        file: Path | None = typer.Option(None, '--file', help='Read new description from a text file'),
        dry_run: bool = typer.Option(False, '--dry-run', help='Preview the diff without writing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip the confirmation prompt'),
) -> None:
    """Set one card's description (round-trip update)."""
    renderer = get_renderer(ctx)
    profile = get_profile(ctx)

    try:
        description = _read_description(text, file)
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=ExitCode.VALIDATION_ERROR) from exc

    if not dry_run:
        confirm_or_abort(renderer, f'update description for NM ID {nm}', yes)

    try:
        result, errors = _get_content_service(profile).set_description(
            nm, description, dry_run=dry_run,
        )
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=_exit_for(exc)) from exc

    _render_outcome(ctx, renderer, [result], errors, dry_run=dry_run)


# ── Helpers ───────────────────────────────────────────────────────────

def _truncate(value: str) -> str:
    """Trim a title for table display."""
    value = value or '—'
    return value if len(value) <= _TITLE_TRUNCATE else value[:_TITLE_TRUNCATE - 1] + '…'


def _exit_for(exc: WbCliError) -> int:
    """Map a WbCliError to its exit code (defaults to API_ERROR)."""
    return getattr(exc, 'exit_code', ExitCode.API_ERROR)


def _load_updates_file(path: Path) -> dict[int, str]:
    """Read a JSON edit file into an ``nmID → description`` map.

    Accepts the export shape — a list of objects each carrying ``nmID``
    (or ``nm_id``) and ``description``.

    Args:
        path: Path to the JSON file.

    Returns:
        Map of WB article to new description.

    Raises:
        ValidationError: On a missing/unreadable file or malformed shape.
    """
    from wb.core.exceptions import ValidationError
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f'cannot read edit file {path}: {exc}') from exc
    if not isinstance(raw, list):
        raise ValidationError('edit file must be a JSON array of {nmID, description} objects')

    updates: dict[int, str] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValidationError('each edit entry must be a JSON object')
        nm_id = entry.get('nmID', entry.get('nm_id'))
        description = entry.get('description')
        if nm_id is None or description is None:
            raise ValidationError('each edit entry needs both nmID and description')
        updates[int(nm_id)] = str(description)
    return updates


def _read_description(text: str | None, file: Path | None) -> str:
    """Resolve the new description from ``--text`` or ``--file`` (exactly one).

    Args:
        text: Inline description.
        file: Path to a UTF-8 text file holding the description.

    Returns:
        The description string.

    Raises:
        ValidationError: When neither or both sources are given, or the file
            cannot be read.
    """
    from wb.core.exceptions import ValidationError
    if (text is None) == (file is None):
        raise ValidationError('provide exactly one of --text or --file')
    if text is not None:
        return text
    try:
        return file.read_text(encoding='utf-8')
    except OSError as exc:
        raise ValidationError(f'cannot read description file {file}: {exc}') from exc


def _render_outcome(
        ctx: typer.Context,
        renderer,
        results: list[CardUpdateResult],
        errors: list[str],
        *,
        dry_run: bool,
) -> None:
    """Render apply/set results + post-update errors; exit non-zero on errors."""
    if renderer.is_json:
        fields = get_fields(ctx)
        data = {
            'dryRun': dry_run,
            'results': [asdict(r) for r in results],
            'errors': errors,
        }
        if fields:
            data['results'] = [{k: v for k, v in r.items() if k in fields} for r in data['results']]
        typer.echo(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        rows = [
            [str(r.nm_id), r.vendor_code or '—', str(r.old_length), str(r.new_length), r.status]
            for r in results
        ]
        verb = 'Planned' if dry_run else 'Applied'
        render_table(['NM ID', 'Vendor Code', 'Old Len', 'New Len', 'Status'], rows,
                     title=f'{verb} description edits ({len(results)})')
        changed = sum(1 for r in results if r.status == STATUS_CHANGED)
        too_long = sum(1 for r in results if r.status == STATUS_TOO_LONG)
        renderer.success(
            f'{changed} {"to change" if dry_run else "changed"}'
            + (f', {too_long} over the {_max_len()}-char cap (skipped)' if too_long else ''),
        )
        for message in errors:
            renderer.error(message)

    if errors:
        raise typer.Exit(code=ExitCode.API_ERROR)


def _max_len() -> int:
    """Absolute description cap, for messaging."""
    from wb.core.constants import CONTENT_DESCRIPTION_MAX_LENGTH
    return CONTENT_DESCRIPTION_MAX_LENGTH
