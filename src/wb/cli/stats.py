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

_MAX_RANGE_DAYS = 7


def _resolve_daily_range(
        report_date: str | None,
        days: int | None,
        date_from: str | None,
        date_to: str | None,
) -> tuple[str, str]:
    """Resolve mutually-exclusive date-filter options to an inclusive (from, to) range.

    Args:
        report_date: Single date from ``--date``.
        days: Relative window from ``--days``.
        date_from: Range start from ``--from``.
        date_to: Range end from ``--to``.

    Returns:
        Tuple of (from_date, to_date) YYYY-MM-DD strings.

    Raises:
        typer.BadParameter: On mutual exclusion, future dates, missing pair,
            inverted range, or range wider than 7 days.
    """
    today = _date.today()
    yesterday = today - timedelta(days=1)

    modes_active = sum([
        report_date is not None,
        days is not None,
        date_from is not None or date_to is not None,
    ])
    if modes_active > 1:
        raise typer.BadParameter(
            '--date, --days, and --from/--to are mutually exclusive; use exactly one.'
        )

    if date_from is not None or date_to is not None:
        if date_from is None or date_to is None:
            raise typer.BadParameter('--from and --to must be used together.')
        from_d = _date.fromisoformat(date_from)
        to_d = _date.fromisoformat(date_to)
        if from_d > to_d:
            raise typer.BadParameter(f'--from {date_from} is after --to {date_to}.')
        if to_d >= today:
            raise typer.BadParameter(
                f'--to {date_to} must be before today ({today}) — 24-hour settle window.'
            )
        if (to_d - from_d).days >= _MAX_RANGE_DAYS:
            raise typer.BadParameter(
                f'Date range exceeds {_MAX_RANGE_DAYS}-day limit '
                f'({(to_d - from_d).days + 1} days requested).'
            )
        return date_from, date_to

    if days is not None:
        if days < 1:
            raise typer.BadParameter('--days must be >= 1.')
        if days > _MAX_RANGE_DAYS:
            raise typer.BadParameter(
                f'--days {days} exceeds the {_MAX_RANGE_DAYS}-day limit.'
            )
        from_d = yesterday - timedelta(days=days - 1)
        return str(from_d), str(yesterday)

    if report_date is not None:
        d = _date.fromisoformat(report_date)
        if d >= today:
            raise typer.BadParameter(
                f'--date {report_date} must be before today ({today}) — 24-hour settle window.'
            )
        return report_date, report_date

    return str(yesterday), str(yesterday)


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
            None, '--date',
            help='Single past date YYYY-MM-DD (default: yesterday)',
        ),
        days: int | None = typer.Option(
            None, '--days',
            help='Relative range: last N days ending yesterday (1–7)',
        ),
        date_from: str | None = typer.Option(
            None, '--from',
            help='Range start YYYY-MM-DD (use with --to)',
        ),
        date_to_opt: str | None = typer.Option(
            None, '--to',
            help='Range end YYYY-MM-DD (use with --from)',
        ),
        status: str = typer.Option(
            'active', '--status',
            help='Campaign status filter: running, paused, active (running+paused)',
        ),
) -> None:
    """Show per-product ad spend and funnel metrics for a date or range.

    Combines Promotion API spend data with Analytics funnel metrics.
    Requires an analytics token for funnel fields; falls back to 0 if unavailable.

    Date modes (mutually exclusive, default = yesterday):
      --date YYYY-MM-DD         single past date
      --days N                  last N days (1-7) ending yesterday
      --from YYYY-MM-DD --to YYYY-MM-DD  absolute range (max 7 days)
    """
    from wb.services._factory import create_analytics_service, create_stats_service

    if status not in _STATUS_MAP:
        valid = ', '.join(_STATUS_MAP)
        raise typer.BadParameter(f'--status must be one of: {valid}')

    resolved_from, resolved_to = _resolve_daily_range(
        report_date, days, date_from, date_to_opt,
    )
    profile = get_profile(ctx)
    renderer = get_renderer(ctx)
    svc = create_stats_service(profile)

    analytics_svc = None
    analytics_note = ''
    try:
        analytics_svc = create_analytics_service(profile)
    except Exception:
        analytics_note = ' (analytics token unavailable — funnel fields set to 0)'

    date_to_arg = None if resolved_from == resolved_to else resolved_to
    rows = svc.get_daily_report(
        resolved_from,
        date_to=date_to_arg,
        statuses=_STATUS_MAP[status],
        analytics_svc=analytics_svc,
    )

    date_label = (
        resolved_from if resolved_from == resolved_to
        else f'{resolved_from} to {resolved_to}'
    )
    if not rows:
        renderer.success(f'No active campaigns found for {date_label}.')
        return

    if renderer.is_json:
        renderer.display([asdict(r) for r in rows], fields=get_fields(ctx))
        return

    from wb.core.output import render_table
    headers = [
        'SKU', 'Product Name',
        'Spend ₽', 'Views', 'Clicks', 'Ad Orders', 'Avg Pos',
        'Opens', 'Cart', 'Orders', 'Order Sum', 'Buyouts',
    ]
    table_rows = [
        [
            str(r.nm_id),
            r.name or '—',
            f'{r.spend:.2f}',
            str(r.views),
            str(r.clicks),
            str(r.ad_orders),
            f'{r.avg_position:.1f}' if r.avg_position else '—',
            str(r.opens),
            str(r.cart_adds),
            str(r.orders),
            str(r.order_sum),
            str(r.buyouts),
        ]
        for r in rows
    ]
    title = f'Daily Report — {date_label}{analytics_note}'
    render_table(headers, table_rows, title=title)
