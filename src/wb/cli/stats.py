"""CLI commands for campaign and cluster statistics."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date as _date, timedelta

import typer

from wb.cli._helpers import get_fields, get_profile, get_renderer

stats_app = typer.Typer(
    help='Campaign and cluster statistics',
    no_args_is_help=True,
)

_STATUS_MAP: dict[str, list[int]] = {
    'running': [9],
    'paused':  [11],
    'active':  [9, 11],
}


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

    renderer = get_renderer(ctx)
    svc = create_stats_service(get_profile(ctx))
    stats = svc.get_campaign_stats(campaign_id, date_from, date_to)

    if renderer.is_json:
        typer.echo(json.dumps(asdict(stats), indent=2, ensure_ascii=False))
        return

    from wb.core.output import render_table
    rows = [
        ['Campaign ID', str(stats.campaign_id)],
        ['Views', str(stats.views)],
        ['Clicks', str(stats.clicks)],
        ['CTR', f'{stats.ctr:.2f}%'],
        ['Orders', str(stats.orders)],
        ['Spend', str(stats.spend)],
        ['CPC', f'{stats.cpc:.2f}'],
        ['CR', f'{stats.cr:.2f}'],
    ]
    render_table(['Field', 'Value'], rows, title=f'Stats — Campaign {campaign_id}')


@stats_app.command('product-spend')
def stats_product_spend(
        ctx: typer.Context,
        nms: str = typer.Option(..., '--nms', help='Comma-separated NM IDs'),
        date_from: str = typer.Option(..., '--from', help='Start date YYYY-MM-DD'),
        date_to: str = typer.Option(..., '--to', help='End date YYYY-MM-DD'),
) -> None:
    """Show per-product ad spend aggregated across all campaigns."""
    from wb.services._factory import create_stats_service

    renderer = get_renderer(ctx)
    nm_ids = _parse_ids(nms)
    svc = create_stats_service(get_profile(ctx))
    nm_stats = svc.get_product_spend(nm_ids, date_from, date_to)

    if not nm_stats:
        renderer.success('No spend data found.')
        return

    if renderer.is_json:
        typer.echo(json.dumps(
            [asdict(s) for s in nm_stats],
            indent=2,
            ensure_ascii=False,
        ))
        return

    from wb.core.output import render_table
    headers = ['NM ID', 'Name', 'Spend', 'Views', 'Clicks', 'Orders', 'Avg Pos']
    rows = [
        [
            str(s.nm_id),
            s.name or '—',
            f'{s.spend:.0f}',
            str(s.views),
            str(s.clicks),
            str(s.orders),
            f'{s.avg_position:.1f}' if s.avg_position else '—',
        ]
        for s in nm_stats
    ]
    render_table(headers, rows, title='Per-Product Ad Spend')


@stats_app.command('campaigns')
def stats_campaigns(
        ctx: typer.Context,
        ids: str | None = typer.Option(None, '--ids', help='Comma-separated campaign IDs'),
        status: str | None = typer.Option(
            None, '--status',
            help='Filter by status: running, paused, active (running+paused)',
        ),
        date_from: str = typer.Option(..., '--from', help='Start date YYYY-MM-DD'),
        date_to: str = typer.Option(..., '--to', help='End date YYYY-MM-DD'),
) -> None:
    """Show statistics for multiple campaigns (by IDs or status filter)."""
    from wb.services._factory import create_stats_service

    if bool(ids) == bool(status):
        raise typer.BadParameter('Provide exactly one of --ids or --status.')
    if status and status not in _STATUS_MAP:
        valid = ', '.join(_STATUS_MAP)
        raise typer.BadParameter(f'--status must be one of: {valid}')

    renderer = get_renderer(ctx)
    svc = create_stats_service(get_profile(ctx))

    if ids:
        stats_list = svc.get_campaigns_stats(_parse_ids(ids), date_from, date_to)
        title = 'Campaign Statistics'
    else:
        stats_list = svc.get_stats_by_status(_STATUS_MAP[status], date_from, date_to)
        title = f'Campaign Statistics ({status})'

    if not stats_list:
        renderer.success('No statistics data available.')
        return

    if renderer.is_json:
        typer.echo(json.dumps(
            [asdict(s) for s in stats_list],
            indent=2,
            ensure_ascii=False,
        ))
        return

    from wb.core.output import render_table
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
    render_table(headers, rows, title=title)


@stats_app.command('daily-report')
def stats_daily_report(
        ctx: typer.Context,
        report_date: str | None = typer.Option(
            None, '--date', help='Report date YYYY-MM-DD (default: yesterday)',
        ),
        status: str = typer.Option(
            'active', '--status',
            help='Campaign status filter: running, paused, active (running+paused)',
        ),
) -> None:
    """Show per-product ad spend and total orders for a single date.

    Combines Promotion API spend data with Analytics funnel order counts.
    Requires an analytics token for total orders; falls back to 0 if unavailable.
    """
    from wb.services._factory import create_analytics_service, create_stats_service

    if status not in _STATUS_MAP:
        valid = ', '.join(_STATUS_MAP)
        raise typer.BadParameter(f'--status must be one of: {valid}')

    resolved_date = report_date or str(_date.today() - timedelta(days=1))
    profile = get_profile(ctx)
    renderer = get_renderer(ctx)
    svc = create_stats_service(profile)

    analytics_svc = None
    analytics_note = ''
    try:
        analytics_svc = create_analytics_service(profile)
    except Exception:
        analytics_note = ' (analytics token unavailable — total orders set to 0)'

    rows = svc.get_daily_report(
        resolved_date,
        statuses=_STATUS_MAP[status],
        analytics_svc=analytics_svc,
    )

    if not rows:
        renderer.success(f'No active campaigns found for {resolved_date}.')
        return

    if renderer.is_json:
        typer.echo(json.dumps(
            [asdict(r) for r in rows],
            indent=2,
            ensure_ascii=False,
        ))
        return

    from wb.core.output import render_table
    headers = ['SKU', 'Product Name', 'Ad Spend ₽', 'Total Orders']
    table_rows = [
        [
            str(r.nm_id),
            r.name or '—',
            f'{r.ad_spend:.2f}',
            str(r.total_orders),
        ]
        for r in rows
    ]
    title = f'Daily Report — {resolved_date}{analytics_note}'
    render_table(headers, table_rows, title=title)
