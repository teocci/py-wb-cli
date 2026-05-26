"""CLI commands for WB Reports — warehouse remains, orders, sales."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date as _date, timedelta

import typer

from wb.cli._helpers import get_fields, get_profile, get_renderer
from wb.core.constants import ExitCode
from wb.core.exceptions import WbCliError
from wb.core.output import _stdout_console

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

    _stdout_console.print(table)


def _render_top_table(summaries: list, *, from_cache: bool = False) -> None:
    """Render top product stock summaries as a Rich table."""
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

    _stdout_console.print(table)


def _render_runway_table(report, *, from_cache: bool = False) -> None:
    """Render stock runway report as a Rich table."""
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

    _stdout_console.print(table)


# ── orders / sales (Statistics API) ──────────────────────────────────


def _resolve_orders_query(
        date_arg: str | None,
        since_arg: str | None,
        flag_arg: int | None,
) -> tuple[str, int, str]:
    """Resolve the three mutually exclusive date-mode options to API params.

    Args:
        date_arg: ``--date YYYY-MM-DD`` — single calendar day (flag=1).
        since_arg: ``--since YYYY-MM-DD[THH:MM[:SS]]`` — incremental cursor (flag=0).
        flag_arg: ``--flag 0|1`` — raw passthrough; must be paired with
            ``--date`` (flag=1) or ``--since`` (flag=0).

    Returns:
        Tuple of (``date_from``, ``flag``, ``label``) where ``label`` is a
        short human-readable description of the chosen window.

    Raises:
        typer.BadParameter: On mutual-exclusion violations or invalid flag values.
    """
    explicit_date = date_arg is not None
    explicit_since = since_arg is not None
    explicit_flag = flag_arg is not None

    if explicit_date and explicit_since:
        raise typer.BadParameter('--date and --since are mutually exclusive.')

    if explicit_flag and flag_arg not in (0, 1):
        raise typer.BadParameter('--flag must be 0 or 1.')

    if explicit_since:
        flag = flag_arg if explicit_flag else 0
        if flag != 0:
            raise typer.BadParameter('--since requires --flag 0 (incremental mode).')
        return since_arg, 0, f'since {since_arg} (flag=0, incremental)'

    if explicit_date:
        flag = flag_arg if explicit_flag else 1
        if flag != 1:
            raise typer.BadParameter('--date requires --flag 1 (single-day mode).')
        return date_arg, 1, f'on {date_arg} (flag=1, single day)'

    if explicit_flag:
        raise typer.BadParameter(
            '--flag requires either --date (flag=1) or --since (flag=0).'
        )

    yesterday = (_date.today() - timedelta(days=1)).isoformat()
    return yesterday, 1, f'on {yesterday} (flag=1, default = yesterday)'


@dataclass(slots=True)
class _ProductAggregate:
    """Client-side per-nmId aggregation of order or sale rows."""

    nm_id: int
    supplier_article: str = ''
    brand: str = ''
    subject: str = ''
    order_count: int = 0
    cancelled_count: int = 0
    total_revenue: float = 0.0
    total_for_pay: float = 0.0
    warehouses: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)


def _aggregate_by_product(rows: list[dict]) -> list[dict]:
    """Aggregate raw orders/sales rows by ``nmId``.

    Args:
        rows: Raw record dicts from the Statistics API.

    Returns:
        List of dicts (one per nm_id), sorted by ``order_count`` desc.
    """
    buckets: dict[int, _ProductAggregate] = {}
    wh_sets: dict[int, set[str]] = defaultdict(set)
    rg_sets: dict[int, set[str]] = defaultdict(set)

    for row in rows:
        nm_id = row.get('nmId') or 0
        if not nm_id:
            continue
        agg = buckets.get(nm_id)
        if agg is None:
            agg = _ProductAggregate(
                nm_id=nm_id,
                supplier_article=str(row.get('supplierArticle') or ''),
                brand=str(row.get('brand') or ''),
                subject=str(row.get('subject') or ''),
            )
            buckets[nm_id] = agg
        agg.order_count += 1
        if row.get('isCancel'):
            agg.cancelled_count += 1
        agg.total_revenue += float(row.get('priceWithDisc') or 0)
        agg.total_for_pay += float(row.get('forPay') or 0)
        wh = row.get('warehouseName')
        if wh:
            wh_sets[nm_id].add(str(wh))
        rg = row.get('regionName')
        if rg:
            rg_sets[nm_id].add(str(rg))

    for nm_id, agg in buckets.items():
        agg.warehouses = sorted(wh_sets[nm_id])
        agg.regions = sorted(rg_sets[nm_id])

    aggs = sorted(buckets.values(), key=lambda a: a.order_count, reverse=True)
    return [
        {
            'nm_id': a.nm_id,
            'supplier_article': a.supplier_article,
            'brand': a.brand,
            'subject': a.subject,
            'order_count': a.order_count,
            'cancelled_count': a.cancelled_count,
            'total_revenue': round(a.total_revenue, 2),
            'total_for_pay': round(a.total_for_pay, 2),
            'warehouses': a.warehouses,
            'regions': a.regions,
        }
        for a in aggs
    ]


_DATE_OPT = typer.Option(
    None, '--date',
    help='Single date YYYY-MM-DD (uses flag=1). Default: yesterday.',
)
_SINCE_OPT = typer.Option(
    None, '--since',
    help='Incremental cursor YYYY-MM-DD[THH:MM[:SS]] (uses flag=0).',
)
_FLAG_OPT = typer.Option(
    None, '--flag', min=0, max=1,
    help='Raw WB flag passthrough; pair with --date (1) or --since (0).',
)
_BY_PRODUCT_OPT = typer.Option(
    False, '--by-product',
    help='Aggregate client-side by nmId; one row per SKU.',
)
_EXCLUDE_CANCELLED_OPT = typer.Option(
    False, '--exclude-cancelled',
    help='Drop rows where isCancel=true (default: include).',
)


@report_app.command('orders')
def report_orders(
        ctx: typer.Context,
        date_arg: str | None = _DATE_OPT,
        since_arg: str | None = _SINCE_OPT,
        flag_arg: int | None = _FLAG_OPT,
        exclude_cancelled: bool = _EXCLUDE_CANCELLED_OPT,
        by_product: bool = _BY_PRODUCT_OPT,
) -> None:
    """List every order line for a date or incremental window.

    Wraps ``GET /api/v1/supplier/orders``. Returns one row per ordered
    item — all WB fields preserved (srid, sticker, warehouseName,
    regionName, totalPrice, finishedPrice, priceWithDisc, isCancel, …).
    Aggregate with ``--by-product`` for a per-SKU view.

    Default window: yesterday with flag=1 (single-day snapshot, no
    row cap). Rate-limited at 1/min by ``EndpointBudget`` so back-to-back
    calls within 60 s queue rather than 429.
    """
    from wb.services._factory import create_statistics_client

    renderer = get_renderer(ctx)
    profile = get_profile(ctx)
    date_from, flag, label = _resolve_orders_query(date_arg, since_arg, flag_arg)

    try:
        client = create_statistics_client(profile)
        rows = client.get_orders(date_from, flag=flag)
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=ExitCode.API_ERROR) from exc

    if exclude_cancelled:
        rows = [r for r in rows if not r.get('isCancel')]

    if by_product:
        data = _aggregate_by_product(rows)
        title = f'Orders by product — {label} ({len(data)} products, {sum(d["order_count"] for d in data)} orders)'
    else:
        data = rows
        title = f'Orders — {label} ({len(data)} rows)'

    if renderer.is_json:
        renderer.display(data, fields=get_fields(ctx))
        return

    if not data:
        typer.echo(f'No orders found ({label}).')
        return

    from wb.core.output import render_table
    if by_product:
        headers = [
            'nmID', 'Article', 'Brand', 'Subject',
            'Orders', 'Cancelled', 'Revenue ₽', 'Warehouses', 'Regions',
        ]
        table_rows = [
            [
                str(d['nm_id']),
                d['supplier_article'] or '—',
                (d['brand'] or '—')[:16],
                (d['subject'] or '—')[:20],
                str(d['order_count']),
                str(d['cancelled_count']),
                f'{d["total_revenue"]:.2f}',
                ', '.join(d['warehouses'][:3]) + ('…' if len(d['warehouses']) > 3 else ''),
                ', '.join(d['regions'][:3]) + ('…' if len(d['regions']) > 3 else ''),
            ]
            for d in data
        ]
    else:
        headers = [
            'Date', 'nmID', 'Article', 'Warehouse', 'Region',
            'Total ₽', 'Disc%', 'Final ₽', 'Cancelled',
        ]
        table_rows = [
            [
                str(r.get('date') or '—')[:19],
                str(r.get('nmId') or '—'),
                str(r.get('supplierArticle') or '—'),
                str(r.get('warehouseName') or '—')[:16],
                str(r.get('regionName') or '—')[:16],
                str(r.get('totalPrice') or '—'),
                str(r.get('discountPercent') or '—'),
                str(r.get('finishedPrice') or '—'),
                'Y' if r.get('isCancel') else '',
            ]
            for r in data
        ]
    render_table(headers, table_rows, title=title)


@report_app.command('sales')
def report_sales(
        ctx: typer.Context,
        date_arg: str | None = _DATE_OPT,
        since_arg: str | None = _SINCE_OPT,
        flag_arg: int | None = _FLAG_OPT,
        by_product: bool = _BY_PRODUCT_OPT,
) -> None:
    """List every sale or return line for a date or incremental window.

    Wraps ``GET /api/v1/supplier/sales``. Includes both sales (``saleID``
    starts with ``S``) and returns (``R``). Adds ``forPay`` (seller
    payout) and ``paymentSaleAmount`` over the orders schema. Aggregate
    with ``--by-product`` for a per-SKU view.

    Default window: yesterday with flag=1 (single-day snapshot).
    """
    from wb.services._factory import create_statistics_client

    renderer = get_renderer(ctx)
    profile = get_profile(ctx)
    date_from, flag, label = _resolve_orders_query(date_arg, since_arg, flag_arg)

    try:
        client = create_statistics_client(profile)
        rows = client.get_sales(date_from, flag=flag)
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=ExitCode.API_ERROR) from exc

    if by_product:
        data = _aggregate_by_product(rows)
        title = f'Sales by product — {label} ({len(data)} products, {sum(d["order_count"] for d in data)} sales/returns)'
    else:
        data = rows
        title = f'Sales/returns — {label} ({len(data)} rows)'

    if renderer.is_json:
        renderer.display(data, fields=get_fields(ctx))
        return

    if not data:
        typer.echo(f'No sales found ({label}).')
        return

    from wb.core.output import render_table
    if by_product:
        headers = [
            'nmID', 'Article', 'Brand', 'Subject',
            'Sales', 'Revenue ₽', 'Payout ₽', 'Warehouses', 'Regions',
        ]
        table_rows = [
            [
                str(d['nm_id']),
                d['supplier_article'] or '—',
                (d['brand'] or '—')[:16],
                (d['subject'] or '—')[:20],
                str(d['order_count']),
                f'{d["total_revenue"]:.2f}',
                f'{d["total_for_pay"]:.2f}',
                ', '.join(d['warehouses'][:3]) + ('…' if len(d['warehouses']) > 3 else ''),
                ', '.join(d['regions'][:3]) + ('…' if len(d['regions']) > 3 else ''),
            ]
            for d in data
        ]
    else:
        headers = [
            'Date', 'saleID', 'nmID', 'Article', 'Warehouse',
            'Region', 'Final ₽', 'forPay ₽',
        ]
        table_rows = [
            [
                str(r.get('date') or '—')[:19],
                str(r.get('saleID') or '—'),
                str(r.get('nmId') or '—'),
                str(r.get('supplierArticle') or '—'),
                str(r.get('warehouseName') or '—')[:16],
                str(r.get('regionName') or '—')[:16],
                str(r.get('finishedPrice') or '—'),
                str(r.get('forPay') or '—'),
            ]
            for r in data
        ]
    render_table(headers, table_rows, title=title)
