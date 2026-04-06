"""CLI commands for Prices & Discounts operations."""

from __future__ import annotations

import json
from dataclasses import asdict

import typer

from wb.cli._helpers import get_profile, get_renderer
from wb.core.constants import ExitCode
from wb.core.exceptions import WbCliError

__all__ = ['prices_app']

prices_app = typer.Typer(
    help='Prices and discounts (Prices & Discounts API)',
    no_args_is_help=True,
)


def _get_prices_service(profile: str | None = None):
    """Create a PricesService from current settings."""
    from wb.services._factory import create_prices_service
    return create_prices_service(profile)


def _parse_int_list(value: str | None) -> list[int] | None:
    """Parse a comma-separated string of integers, or return None."""
    if not value:
        return None
    try:
        return [int(x.strip()) for x in value.split(',') if x.strip()]
    except ValueError as exc:
        raise typer.BadParameter('Must be comma-separated integers') from exc


def _fmt_price(value: float, currency: str) -> str:
    """Format a price value with a currency symbol."""
    symbol = '₽' if currency == 'RUB' else currency
    return f'{value:,.0f} {symbol}'


@prices_app.command('list')
def prices_list(
        ctx: typer.Context,
        nm_ids: str | None = typer.Option(
            None, '--nm-ids',
            help='Comma-separated NM IDs to filter (e.g. 227403075,100510938)',
        ),
        min_discount: int | None = typer.Option(
            None, '--min-discount',
            help='Only show products with seller discount >= N%%',
        ),
) -> None:
    """Fetch and display product prices with discounts.

    Shows base price, seller discount percentage, and final buyer price.
    A Club Price column appears only when at least one product has a WB
    Club discount. Fetches all products with auto-pagination when no
    --nm-ids filter is given.
    """
    renderer = get_renderer(ctx)
    profile = get_profile(ctx)

    try:
        svc = _get_prices_service(profile)
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=ExitCode.CONFIG_ERROR) from exc

    try:
        prices = svc.get_prices(
            nm_ids=_parse_int_list(nm_ids),
            min_discount=min_discount,
        )
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=ExitCode.API_ERROR) from exc

    if not prices:
        renderer.success('No products found matching the given filters.')
        return

    if renderer.is_json:
        typer.echo(json.dumps(
            [asdict(p) for p in prices],
            indent=2,
            ensure_ascii=False,
        ))
        return

    _render_prices_table(prices)


def _render_prices_table(prices) -> None:
    """Render a list of ProductPrice objects as a Rich table."""
    from rich.console import Console
    from rich.table import Table

    has_club = any(p.club_discount > 0 for p in prices)

    table = Table(title=f'Product Prices ({len(prices)})', show_lines=False)
    table.add_column('NM ID', style='cyan', justify='right')
    table.add_column('Vendor Code', style='dim')
    table.add_column('Base Price', justify='right')
    table.add_column('Discount', justify='center', style='yellow')
    table.add_column('Final Price', justify='right', style='green')
    if has_club:
        table.add_column('Club Price', justify='right', style='magenta')
    table.add_column('Currency', justify='center', style='dim')

    for p in prices:
        discount_str = f'-{p.discount}%' if p.discount > 0 else '—'
        row = [
            str(p.nm_id),
            p.vendor_code,
            _fmt_price(p.base_price, p.currency_iso),
            discount_str,
            _fmt_price(p.final_price, p.currency_iso),
        ]
        if has_club:
            club_str = (
                _fmt_price(p.club_price, p.currency_iso)
                if p.club_discount > 0
                else '—'
            )
            row.append(club_str)
        row.append(p.currency_iso)
        table.add_row(*row)

    Console().print(table)
