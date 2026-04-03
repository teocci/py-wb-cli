"""CLI commands for seller portal operations."""

from __future__ import annotations

import typer

from wb.core.constants import ExitCode
from wb.core.exceptions import WbCliError

portal_app = typer.Typer(
    help='Seller portal operations (requires portal session)',
    no_args_is_help=True,
)


def _get_portal_client():
    """Create a PortalClient from current settings."""
    from wb.services._factory import create_portal_client
    return create_portal_client()


@portal_app.command('products')
def portal_products(
        ctx: typer.Context,
        limit: int = typer.Option(20, '--limit', '-n', help='Number of products'),
        search: str = typer.Option('', '--search', '-s', help='Search query'),
) -> None:
    """List product cards from the seller portal."""
    from wb.domain.models import PortalProductCard

    json_output = ctx.obj.get('json_output', False) if ctx.obj else False

    try:
        client = _get_portal_client()
    except WbCliError as exc:
        typer.secho(f'Error: {exc}', fg=typer.colors.RED, err=True)
        raise typer.Exit(code=ExitCode.CONFIG_ERROR) from exc

    try:
        raw_cards = client.list_products(page_size=limit, search=search)
    except WbCliError as exc:
        typer.secho(f'Portal error: {exc}', fg=typer.colors.RED, err=True)
        raise typer.Exit(code=ExitCode.API_ERROR) from exc

    cards = [PortalProductCard.from_portal(c) for c in raw_cards]

    if json_output:
        import json
        from dataclasses import asdict
        typer.echo(json.dumps([asdict(c) for c in cards], indent=2, ensure_ascii=False))
        return

    if not cards:
        typer.echo('No products found.')
        return

    from rich.console import Console
    from rich.table import Table

    table = Table(title=f'Products ({len(cards)})')
    table.add_column('nmID', style='cyan', justify='right')
    table.add_column('Vendor', style='dim')
    table.add_column('Title', max_width=40)
    table.add_column('Stock', justify='right')
    table.add_column('Price', justify='right', style='green')
    table.add_column('Rating', justify='center')
    table.add_column('Reviews', justify='right')

    for c in cards:
        table.add_row(
            str(c.nm_id),
            c.vendor_code,
            c.title[:40],
            str(c.stocks),
            f'{c.price}',
            f'{c.feedback_rating:.1f}',
            str(c.feedback_count),
        )

    Console().print(table)
