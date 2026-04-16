"""CLI command: wb assess — morning account and campaign snapshot."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, timedelta

import typer

from wb.cli._helpers import get_profile, get_renderer
from wb.core.constants import ExitCode

__all__ = ['assess_command']


def assess_command(
        ctx: typer.Context,
        nm: int | None = typer.Option(
            None, '--nm',
            help='NM ID for a single-product detailed summary (optional)',
        ),
        quick: bool = typer.Option(
            False, '--quick',
            help='Skip product-spend stats (no 20-second rate-limit wait)',
        ),
        days: int = typer.Option(
            7, '--days',
            help='Number of days to look back for product spend stats',
        ),
) -> None:
    """Morning account snapshot: balance, campaigns, and 7-day product spend.

    Aggregates balance, running/paused campaign counts, and per-product
    ad spend. Also saves a bid-recommendation baseline to
    ~/.wb-cli/pulse_baseline.json so that wb pulse can detect intraday
    bid drift.

    Use --quick to skip the product-spend call (which waits ~20 s for the
    rate limiter) when you only need a fast status check.
    """
    from wb.core.exceptions import WbCliError
    from wb.services._factory import create_assess_service, create_pulse_service

    renderer = get_renderer(ctx)
    profile = get_profile(ctx)
    today = date.today()
    date_from = (today - timedelta(days=days)).strftime('%Y-%m-%d')
    date_to = today.strftime('%Y-%m-%d')

    try:
        assess_svc = create_assess_service(profile)
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=ExitCode.CONFIG_ERROR) from exc

    try:
        snapshot = assess_svc.get_snapshot(date_from, date_to, quick=quick)
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=ExitCode.API_ERROR) from exc

    # Save bid baselines for wb pulse (best-effort, non-blocking)
    if not quick and snapshot.running:
        running_ids = [c.campaign_id for c in snapshot.running]
        try:
            pulse_svc = create_pulse_service(profile)
            pulse_svc.save_baseline(running_ids)
        except Exception as exc:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).debug('baseline save failed: %s', exc)

    if renderer.is_json:
        data = asdict(snapshot)
        if renderer.compact:
            typer.echo(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
        else:
            typer.echo(json.dumps(data, indent=2, ensure_ascii=False))
        return

    _render_assess_table(snapshot, date_from, date_to)


def _render_assess_table(snapshot, date_from: str, date_to: str) -> None:
    """Render AssessSnapshot as Rich output."""
    from rich.console import Console
    from rich.table import Table

    console = Console()

    n_running = len(snapshot.running)
    n_paused = len(snapshot.paused)
    n_ready = len(snapshot.ready)

    header = Table(
        title=f'Account Snapshot  ({date_from} → {date_to})',
        show_header=False, show_lines=False, box=None,
    )
    header.add_column('Field', style='dim', min_width=18)
    header.add_column('Value', style='cyan')
    header.add_row('Balance', f'{snapshot.balance_rub:,.2f} ₽')
    header.add_row('Running campaigns', str(n_running))
    header.add_row('Paused campaigns', str(n_paused))
    header.add_row('Ready campaigns', str(n_ready))
    header.add_row('Data as of', snapshot.data_as_of[:19].replace('T', ' ') + ' UTC')
    console.print(header)

    if snapshot.running:
        _render_campaign_table(console, snapshot.running, 'Running')
    if snapshot.paused:
        _render_campaign_table(console, snapshot.paused, 'Paused')

    if snapshot.product_spend_7d:
        spend_table = Table(title='7-Day Product Spend', show_lines=False)
        spend_table.add_column('NM ID', justify='right', style='cyan')
        spend_table.add_column('Spend ₽', justify='right', style='magenta')
        spend_table.add_column('Views', justify='right')
        spend_table.add_column('Clicks', justify='right')
        spend_table.add_column('Orders', justify='right')
        for row in snapshot.product_spend_7d:
            spend_table.add_row(
                str(row.get('nm_id', 0)),
                f"{row.get('spend', 0.0):,.2f}",
                str(row.get('views', 0)),
                str(row.get('clicks', 0)),
                str(row.get('orders', 0)),
            )
        console.print(spend_table)
    elif not snapshot.running:
        console.print('[dim]No running campaigns — no spend data to show[/dim]')


def _render_campaign_table(console, campaigns, title: str) -> None:
    """Render a list of CampaignAssessSummary as a Rich table."""
    from rich.table import Table

    table = Table(title=title, show_lines=False)
    table.add_column('ID', justify='right', style='cyan')
    table.add_column('Name')
    table.add_column('NM ID', justify='right')
    for c in campaigns:
        table.add_row(str(c.campaign_id), c.name, str(c.nm_id) if c.nm_id else '—')
    console.print(table)
