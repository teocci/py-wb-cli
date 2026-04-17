"""CLI commands for composite product analysis."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, timedelta

import typer

from wb.cli._helpers import get_fields, get_profile, get_renderer
from wb.core.constants import ExitCode
from wb.core.exceptions import WbCliError
from wb.core.output import _stdout_console

__all__ = ['product_app']

product_app = typer.Typer(
    help='Composite product summary (ad spend + prices + analytics)',
    no_args_is_help=True,
)


def _get_product_service(profile: str | None = None):
    """Create a ProductService from current settings."""
    from wb.services._factory import create_product_service
    return create_product_service(profile)


def _default_from() -> str:
    return (date.today() - timedelta(days=7)).strftime('%Y-%m-%d')


def _default_to() -> str:
    return date.today().strftime('%Y-%m-%d')


def _parse_nm_ids(value: str) -> list[int]:
    """Parse a comma-separated NM ID string into a list of ints."""
    try:
        return [int(x.strip()) for x in value.split(',') if x.strip()]
    except ValueError as exc:
        raise typer.BadParameter('--nms must be comma-separated integers') from exc


@product_app.command('summary')
def product_summary(
        ctx: typer.Context,
        nms: str = typer.Option(
            ..., '--nms',
            help='Comma-separated NM IDs (e.g. 100525085,227403075)',
        ),
        date_from: str | None = typer.Option(
            None, '--from',
            help='Start date YYYY-MM-DD (default: 7 days ago)',
        ),
        date_to: str | None = typer.Option(
            None, '--to',
            help='End date YYYY-MM-DD (default: today)',
        ),
) -> None:
    """Composite per-product snapshot in one call.

    Returns ad spend, prices, sales funnel, and campaign/cluster placement
    for each requested NM ID. Analytics and price data are best-effort:
    if those tokens are unavailable their fields appear as zero.
    """
    renderer = get_renderer(ctx)
    profile = get_profile(ctx)
    nm_ids = _parse_nm_ids(nms)
    from_date = date_from or _default_from()
    to_date = date_to or _default_to()

    try:
        svc = _get_product_service(profile)
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=ExitCode.CONFIG_ERROR) from exc

    try:
        summaries = svc.get_product_summary(nm_ids, from_date, to_date)
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=ExitCode.API_ERROR) from exc

    if not summaries:
        renderer.success('No data found for the requested NM IDs.')
        return

    if renderer.is_json:
        fields = get_fields(ctx)
        data = [asdict(s) for s in summaries]
        if fields:
            data = [{k: v for k, v in row.items() if k in fields} for row in data]
        typer.echo(json.dumps(data, indent=2, ensure_ascii=False))
        return

    _render_summary_table(summaries)


def _render_summary_table(summaries) -> None:
    """Render ProductSummary list as a Rich table."""
    from rich.table import Table

    table = Table(
        title=f'Product Summary ({len(summaries)} products)',
        show_lines=False,
    )
    table.add_column('NM ID', style='cyan', justify='right')
    table.add_column('Vendor Code', style='dim')
    table.add_column('Base Price', justify='right')
    table.add_column('Final Price', justify='right', style='green')
    table.add_column('Disc%', justify='center', style='yellow')
    table.add_column('Ad Spend', justify='right', style='magenta')
    table.add_column('Views', justify='right')
    table.add_column('Clicks', justify='right')
    table.add_column('Orders', justify='right')
    table.add_column('Campaigns', justify='right')
    table.add_column('Clusters', justify='right')

    for s in summaries:
        discount_str = f'-{s.discount}%' if s.discount > 0 else '—'
        base_str = f'{s.base_price:,.0f} ₽' if s.base_price else '—'
        final_str = f'{s.final_price:,.0f} ₽' if s.final_price else '—'
        spend_str = f'{s.ad_spend:,.2f} ₽'
        clusters_str = f'{s.active_cluster_count}/{s.cluster_count}'
        table.add_row(
            str(s.nm_id),
            s.vendor_code or '—',
            base_str,
            final_str,
            discount_str,
            spend_str,
            str(s.ad_views),
            str(s.ad_clicks),
            str(s.ad_orders),
            str(len(s.campaign_ids)),
            clusters_str,
        )

    _stdout_console.print(table)
