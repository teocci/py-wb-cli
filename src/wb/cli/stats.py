"""CLI commands for campaign and cluster statistics."""

from __future__ import annotations

from dataclasses import asdict

import typer

from wb.core.output import OutputRenderer
from wb.domain.enums import OutputFormat, VerbosityLevel

stats_app = typer.Typer(
    help='Campaign and cluster statistics',
    no_args_is_help=True,
)


def _get_renderer(ctx: typer.Context) -> OutputRenderer:
    """Build an OutputRenderer from global CLI flags."""
    obj = ctx.obj or {}
    fmt = OutputFormat.JSON if obj.get('json_output') else OutputFormat.TABLE
    verb = VerbosityLevel.QUIET if obj.get('quiet') else VerbosityLevel.NORMAL
    if obj.get('verbose'):
        verb = VerbosityLevel.VERBOSE
    return OutputRenderer(fmt, verb)


def _get_profile(ctx: typer.Context) -> str | None:
    """Extract profile name from CLI context."""
    return (ctx.obj or {}).get('profile')


def _parse_ids(ids_str: str) -> list[int]:
    """Parse comma-separated IDs to a list of integers.

    Args:
        ids_str: Comma-separated campaign IDs.

    Returns:
        List of integer IDs.

    Raises:
        typer.BadParameter: If any ID is not a valid integer.
    """
    try:
        return [int(x.strip()) for x in ids_str.split(',') if x.strip()]
    except ValueError as exc:
        raise typer.BadParameter(
            f'Invalid campaign IDs: {ids_str!r}. Use comma-separated integers.'
        ) from exc


@stats_app.command('campaign')
def stats_campaign(
        ctx: typer.Context,
        campaign_id: int = typer.Option(..., '--id', help='Campaign ID'),
        date_from: str = typer.Option(..., '--from', help='Start date YYYY-MM-DD'),
        date_to: str = typer.Option(..., '--to', help='End date YYYY-MM-DD'),
) -> None:
    """Show statistics for a single campaign."""
    from wb.services._factory import create_stats_service

    renderer = _get_renderer(ctx)
    svc = create_stats_service(_get_profile(ctx))
    stats = svc.get_campaign_stats(campaign_id, date_from, date_to)

    data = asdict(stats)
    headers = ['Field', 'Value']
    rows = [
        ['Campaign ID', str(stats.campaign_id)],
        ['Views', str(stats.views)],
        ['Clicks', str(stats.clicks)],
        ['CTR', f'{stats.ctr:.2f}%'],
        ['Orders', str(stats.orders)],
        ['Spend', str(stats.spend)],
        ['CPC', f'{stats.cpc:.2f}'],
        ['CPM', f'{stats.cpm:.2f}'],
    ]
    renderer.display(data, headers=headers, title=f'Stats — Campaign {campaign_id}')


@stats_app.command('campaigns')
def stats_campaigns(
        ctx: typer.Context,
        ids: str = typer.Option(..., '--ids', help='Comma-separated campaign IDs'),
        date_from: str = typer.Option(..., '--from', help='Start date YYYY-MM-DD'),
        date_to: str = typer.Option(..., '--to', help='End date YYYY-MM-DD'),
) -> None:
    """Show statistics for multiple campaigns."""
    from wb.services._factory import create_stats_service

    renderer = _get_renderer(ctx)
    campaign_ids = _parse_ids(ids)
    svc = create_stats_service(_get_profile(ctx))
    stats_list = svc.get_campaigns_stats(campaign_ids, date_from, date_to)

    if not stats_list:
        renderer.success('No statistics data available.')
        return

    data = [asdict(s) for s in stats_list]
    headers = ['ID', 'Views', 'Clicks', 'CTR', 'Orders', 'Spend']
    rows = [
        [
            str(s.campaign_id),
            str(s.views),
            str(s.clicks),
            f'{s.ctr:.2f}%',
            str(s.orders),
            str(s.spend),
        ]
        for s in stats_list
    ]
    renderer.display(data, headers=headers, title='Campaign Statistics')
