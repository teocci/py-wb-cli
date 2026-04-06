"""CLI commands for WB Reports — warehouse remains and async reports."""

from __future__ import annotations

import typer

from wb.cli._helpers import get_fields, get_profile, get_renderer
from wb.core.constants import ExitCode
from wb.core.exceptions import WbCliError

report_app = typer.Typer(
    help='Reports (warehouse remains, orders, sales)',
    no_args_is_help=True,
)

warehouse_app = typer.Typer(
    help='Warehouse inventory reports',
    no_args_is_help=True,
)
report_app.add_typer(warehouse_app, name='warehouse')


def _get_reports_service(profile: str | None = None):
    """Create a ReportsService from current settings."""
    from wb.services._factory import create_reports_service
    return create_reports_service(profile)


def _get_stock_runway_service(profile: str | None = None):
    """Create a ReportsService with StatisticsClient for runway computation."""
    from wb.services._factory import create_stock_runway_service
    return create_stock_runway_service(profile)


@warehouse_app.command('create')
def warehouse_create(
        ctx: typer.Context,
        locale: str = typer.Option('ru', '--locale', help='Language (ru, en, zh)'),
        group_by_nm: bool = typer.Option(False, '--group-by-nm', help='Group by WB article'),
        group_by_brand: bool = typer.Option(False, '--group-by-brand', help='Group by brand'),
        group_by_subject: bool = typer.Option(False, '--group-by-subject', help='Group by subject'),
        group_by_sa: bool = typer.Option(False, '--group-by-sa', help='Group by seller article'),
        group_by_barcode: bool = typer.Option(False, '--group-by-barcode', help='Group by barcode'),
        group_by_size: bool = typer.Option(False, '--group-by-size', help='Group by size'),
        filter_pics: int = typer.Option(0, '--filter-pics', help='Photo filter (-1/0/1)'),
        filter_volume: int = typer.Option(0, '--filter-volume', help='Volume filter (-1/0/3)'),
) -> None:
    """Create a warehouse remains report task."""
    renderer = get_renderer(ctx)
    profile = get_profile(ctx)

    try:
        svc = _get_reports_service(profile)
        task = svc.create_warehouse_report(
            locale=locale,
            group_by_nm=group_by_nm,
            group_by_brand=group_by_brand,
            group_by_subject=group_by_subject,
            group_by_sa=group_by_sa,
            group_by_barcode=group_by_barcode,
            group_by_size=group_by_size,
            filter_pics=filter_pics,
            filter_volume=filter_volume,
        )
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=ExitCode.API_ERROR) from exc

    if renderer.is_json:
        import json
        from dataclasses import asdict
        typer.echo(json.dumps(asdict(task), indent=2, ensure_ascii=False))
    else:
        typer.echo(f'Task created: {task.task_id}')
        typer.echo(f'Status: {task.status}')
        typer.echo(f'\nCheck status: wb report warehouse status {task.task_id}')


@warehouse_app.command('status')
def warehouse_status(
        ctx: typer.Context,
        task_id: str = typer.Argument(..., help='Report task UUID'),
) -> None:
    """Check the status of a warehouse report task."""
    renderer = get_renderer(ctx)
    profile = get_profile(ctx)

    try:
        svc = _get_reports_service(profile)
        task = svc.check_warehouse_status(task_id)
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=ExitCode.API_ERROR) from exc

    if renderer.is_json:
        import json
        from dataclasses import asdict
        typer.echo(json.dumps(asdict(task), indent=2, ensure_ascii=False))
    else:
        typer.echo(f'Task: {task.task_id}')
        typer.echo(f'Status: {task.status}')
        if task.is_done:
            typer.echo(f'\nDownload: wb report warehouse download {task.task_id}')


@warehouse_app.command('download')
def warehouse_download(
        ctx: typer.Context,
        task_id: str = typer.Argument(..., help='Report task UUID'),
) -> None:
    """Download a completed warehouse report."""
    renderer = get_renderer(ctx)
    profile = get_profile(ctx)

    try:
        svc = _get_reports_service(profile)
        items = svc.download_warehouse_report(task_id)
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=ExitCode.API_ERROR) from exc

    if renderer.is_json:
        import json
        from dataclasses import asdict
        typer.echo(json.dumps(
            [asdict(i) for i in items],
            indent=2,
            ensure_ascii=False,
        ))
        return

    if not items:
        typer.echo('No data in report.')
        return

    _render_warehouse_table(items)


@warehouse_app.command('top')
def warehouse_top(
        ctx: typer.Context,
        limit: int = typer.Option(10, '--limit', '-n', help='Number of top products'),
        locale: str = typer.Option('ru', '--locale', help='Language (ru, en, zh)'),
        timeout: float = typer.Option(120.0, '--timeout', help='Max seconds to wait for report'),
        use_cache: bool = typer.Option(True, '--cache/--no-cache', help='Use file cache (default: enabled)'),
) -> None:
    """Show top products by stock with warehouse breakdown.

    Creates a report grouped by NM, waits for completion, then
    displays the top N products sorted by total stock quantity.
    Same-day results are cached for 6 hours to avoid repeated API calls.
    """
    renderer = get_renderer(ctx)
    profile = get_profile(ctx)

    try:
        svc = _get_reports_service(profile)
        summaries, from_cache = svc.get_warehouse_top(
            limit=limit,
            locale=locale,
            poll_timeout=timeout,
            use_cache=use_cache,
        )
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=ExitCode.API_ERROR) from exc

    if renderer.is_json:
        import json
        from dataclasses import asdict
        typer.echo(json.dumps(
            [asdict(s) for s in summaries],
            indent=2,
            ensure_ascii=False,
        ))
        return

    if not summaries:
        typer.echo('No products found.')
        return

    _render_top_table(summaries, from_cache=from_cache)


@warehouse_app.command('stock-runway')
def warehouse_stock_runway(
        ctx: typer.Context,
        sales_days: int = typer.Option(30, '--days', help='Sales lookback window in days'),
        timeout: float = typer.Option(120.0, '--timeout', help='Max seconds to wait for warehouse report'),
        use_cache: bool = typer.Option(True, '--cache/--no-cache', help='Use file cache (default: enabled)'),
) -> None:
    """Days of stock remaining per warehouse (stock / avg daily sales).

    Fetches the current warehouse stock and cross-references it with
    your sales velocity to compute how many days until each product
    runs out of stock at each warehouse.
    Same-day results are cached for 6 hours to avoid repeated API calls.

    Alert levels: critical (<=7 days), low (<=14 days).
    Confidence: high (>=20 sale-days), medium (>=10), low (<10), none (no sales).
    """
    renderer = get_renderer(ctx)
    profile = get_profile(ctx)

    try:
        svc = _get_stock_runway_service(profile)
        report, from_cache = svc.get_stock_runway(
            sales_period_days=sales_days,
            poll_timeout=timeout,
            use_cache=use_cache,
        )
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=ExitCode.API_ERROR) from exc

    if renderer.is_json:
        import json
        from dataclasses import asdict
        typer.echo(json.dumps(asdict(report), indent=2, ensure_ascii=False))
        return

    if not report.items:
        typer.echo('No products found.')
        return

    _render_runway_table(report, from_cache=from_cache)


def _render_warehouse_table(items: list) -> None:
    """Render warehouse remain items as a Rich table."""
    from rich.console import Console
    from rich.table import Table

    table = Table(title=f'Warehouse Remains ({len(items)} items)')
    table.add_column('nmID', style='cyan', justify='right')
    table.add_column('Vendor', style='dim')
    table.add_column('Brand')
    table.add_column('Subject', max_width=25)
    table.add_column('Total', justify='right', style='green')
    table.add_column('Warehouses')

    for item in items:
        wh_str = ', '.join(
            f'{w.warehouse_name}: {w.quantity}'
            for w in item.warehouses
        ) if item.warehouses else '-'
        table.add_row(
            str(item.nm_id),
            item.vendor_code,
            item.brand,
            item.subject_name[:25],
            str(item.total_quantity),
            wh_str,
        )

    Console().print(table)


def _render_top_table(summaries: list, *, from_cache: bool = False) -> None:
    """Render top product stock summaries as a Rich table."""
    from rich.console import Console
    from rich.table import Table

    cache_label = ' \[cached]' if from_cache else ''
    table = Table(title=f'Top {len(summaries)} Products by Stock{cache_label}')
    table.add_column('#', style='dim', justify='right')
    table.add_column('nmID', style='cyan', justify='right')
    table.add_column('Vendor', style='dim')
    table.add_column('Brand')
    table.add_column('Subject', max_width=25)
    table.add_column('Total', justify='right', style='green bold')
    table.add_column('Warehouses')

    for i, s in enumerate(summaries, 1):
        wh_str = ', '.join(
            f'{w.warehouse_name}: {w.quantity}'
            for w in s.warehouses
        ) if s.warehouses else '-'
        table.add_row(
            str(i),
            str(s.nm_id),
            s.vendor_code,
            s.brand,
            s.subject_name[:25],
            str(s.total_quantity),
            wh_str,
        )

    Console().print(table)


def _render_runway_table(report, *, from_cache: bool = False) -> None:
    """Render stock runway report as a Rich table."""
    from rich.console import Console
    from rich.table import Table

    cache_label = ' \[cached]' if from_cache else ''
    table = Table(
        title=f'Stock Runway — {report.sales_period_days}d sales window '
              f'(computed {report.computed_at}){cache_label}',
    )
    table.add_column('nmID', style='cyan', justify='right')
    table.add_column('Avg/day', justify='right')
    table.add_column('Confidence', justify='center')
    table.add_column('Total stock', justify='right', style='green')
    table.add_column('Total days', justify='right')
    table.add_column('Alert', justify='center')
    table.add_column('Warehouses (qty / days)')

    _alert_style = {'critical': 'red bold', 'low': 'yellow', None: ''}

    for item in report.items:
        wh_parts = [
            f'{w.warehouse_name}: {w.quantity}'
            + (f'/{w.days_of_stock}d' if w.days_of_stock is not None else '')
            + (f' [{w.alert}]' if w.alert else '')
            for w in item.warehouses
        ]
        alert_label = item.alert or '-'
        table.add_row(
            str(item.nm_id),
            f'{item.avg_daily_sales:.2f}',
            item.confidence,
            str(item.total_stock),
            str(item.total_days_of_stock) if item.total_days_of_stock is not None else '-',
            alert_label,
            ', '.join(wh_parts) if wh_parts else '-',
            style=_alert_style.get(item.alert, ''),
        )

    Console().print(table)
