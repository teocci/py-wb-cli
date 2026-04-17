"""CLI command: wb pulse — intraday campaign health check."""

from __future__ import annotations

import json
from dataclasses import asdict

import typer

from wb.cli._helpers import get_profile, get_renderer
from wb.core.constants import ExitCode
from wb.core.output import _stdout_console

__all__ = ['pulse_command']


def pulse_command(
        ctx: typer.Context,
        campaigns: str = typer.Option(
            ..., '--campaigns', '-c',
            help='Comma-separated campaign IDs to check',
        ),
) -> None:
    """Intraday campaign health check using real-time endpoints.

    Checks bid recommendations, budget balance, and campaign status for each
    specified campaign. Compares bid recommendations against the morning
    baseline saved by wb assess to detect intraday drift.

    Alert codes:
      competitor_surge  — bid recommendations jumped >15% since morning
      budget_low        — budget below 500 RUB or <20% of morning balance
      campaign_paused   — campaign auto-paused (budget exhausted)
      bid_floor_rising  — minimum bid up >10% since morning

    No analytics data is used — this command reflects the current market
    state, not historical performance.
    """
    from wb.core.exceptions import WbCliError
    from wb.services._factory import create_pulse_service

    renderer = get_renderer(ctx)
    profile = get_profile(ctx)

    try:
        campaign_ids = [int(x.strip()) for x in campaigns.split(',') if x.strip()]
    except ValueError as exc:
        renderer.error('--campaigns must be comma-separated integers')
        raise typer.Exit(code=ExitCode.VALIDATION_ERROR) from exc

    if not campaign_ids:
        renderer.error('No campaign IDs provided')
        raise typer.Exit(code=ExitCode.VALIDATION_ERROR)

    try:
        svc = create_pulse_service(profile)
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=ExitCode.CONFIG_ERROR) from exc

    try:
        report = svc.get_pulse(campaign_ids)
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=ExitCode.API_ERROR) from exc

    if renderer.is_json:
        data = asdict(report)
        if renderer.compact:
            typer.echo(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
        else:
            typer.echo(json.dumps(data, indent=2, ensure_ascii=False))
        return

    _render_pulse_report(report)


def _render_pulse_report(report) -> None:
    """Render PulseReport as Rich console output."""
    from rich.table import Table

    console = _stdout_console
    ts = report.timestamp[:19].replace('T', ' ') + ' UTC'

    if not report.action_needed:
        console.print(f'[green]✓ All campaigns healthy[/green]  (as of {ts})')
        return

    console.print(f'[bold yellow]⚠ Action needed[/bold yellow]  (as of {ts})')

    table = Table(title='Campaign Pulse', show_lines=True)
    table.add_column('ID', justify='right', style='cyan')
    table.add_column('NM ID', justify='right')
    table.add_column('Status')
    table.add_column('Budget ₽', justify='right')
    table.add_column('Bid ₽', justify='right')
    table.add_column('Bid drift', justify='right')
    table.add_column('Alerts', style='yellow')

    for c in report.campaigns:
        drift_str = f'{c.bid_recommend_drift_pct:+.1f}%'
        alerts_str = ', '.join(c.alerts) if c.alerts else '—'
        drift_style = 'red' if c.bid_recommend_drift_pct >= 15 else 'green'
        table.add_row(
            str(c.campaign_id),
            str(c.nm_id) if c.nm_id else '—',
            c.status,
            f'{c.budget_remaining_rub:,.2f}',
            f'{c.bid_recommend_rub:,.2f}',
            f'[{drift_style}]{drift_str}[/{drift_style}]',
            alerts_str,
        )

    console.print(table)
    console.print()
    _print_alert_guide(console, report)


def _print_alert_guide(console, report) -> None:
    """Print action guidance for each unique alert type present."""
    from rich.markup import escape

    all_alerts = {a for c in report.campaigns for a in c.alerts}
    guides = {
        'competitor_surge': 'Consider raising bids — competitors are bidding more aggressively',
        'budget_low': 'Replenish budget: [dim]wb budget topup --campaign <id> --sum <kopecks>[/dim]',
        'campaign_paused': 'Campaign stopped — replenish then resume: [dim]wb campaign start[/dim]',
        'bid_floor_rising': 'Minimum bids increased — verify your bids are still above the floor',
    }
    for alert in sorted(all_alerts):
        guide = guides.get(alert, alert)
        console.print(f'  [bold]{escape(alert)}[/bold]: {guide}')
