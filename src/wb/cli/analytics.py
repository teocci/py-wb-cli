"""CLI commands for analytics operations."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import typer

from wb.cli._helpers import get_fields, get_profile, get_renderer
from wb.core.constants import ExitCode

analytics_app = typer.Typer(
    help='Analytics operations (requires analytics token)',
    no_args_is_help=True,
)

funnel_app = typer.Typer(
    help='Sales funnel statistics',
    no_args_is_help=True,
)
analytics_app.add_typer(funnel_app, name='sales-funnel')

search_app = typer.Typer(
    help='Search query reports',
    no_args_is_help=True,
)
analytics_app.add_typer(search_app, name='search-report')

csv_app = typer.Typer(
    help='CSV report management',
    no_args_is_help=True,
)
analytics_app.add_typer(csv_app, name='csv')


def _parse_int_list(value: str | None) -> list[int] | None:
    """Parse a comma-separated string of integers, or None."""
    if not value:
        return None
    try:
        return [int(x.strip()) for x in value.split(',') if x.strip()]
    except ValueError:
        raise typer.BadParameter('Must be comma-separated integers')


def _parse_str_list(value: str | None) -> list[str] | None:
    """Parse a comma-separated string, or None."""
    if not value:
        return None
    return [x.strip() for x in value.split(',') if x.strip()]


_FROM_OPT = typer.Option(..., '--from', help='Start date (YYYY-MM-DD)')
_TO_OPT = typer.Option(..., '--to', help='End date (YYYY-MM-DD)')
_LIMIT_OPT = typer.Option(20, '--limit', '-l', help='Number of results')
_OFFSET_OPT = typer.Option(0, '--offset', help='Results to skip')

_SORT_FIELD_MAP = {
    'orders': 'order_count',
    'opens': 'open_count',
    'cart': 'cart_count',
    'revenue': 'order_sum',
    'buyouts': 'buyout_count',
}


def _sort_funnel(
        stats: list,
        sort_by: str | None,
        top: int | None,
) -> list:
    """Sort and slice a list of ProductFunnelStats.

    Args:
        stats: List of ProductFunnelStats objects.
        sort_by: Field alias to sort by (orders, opens, cart, revenue, buyouts).
        top: Maximum number of results to return after sorting.

    Returns:
        Sorted (descending) and optionally sliced list.

    Raises:
        typer.BadParameter: If sort_by is not a recognised field alias.
    """
    if sort_by is not None:
        field = _SORT_FIELD_MAP.get(sort_by)
        if field is None:
            valid = ', '.join(_SORT_FIELD_MAP)
            raise typer.BadParameter(
                f'Unknown sort field "{sort_by}". Valid options: {valid}',
                param_hint='--sort-by',
            )
        stats = sorted(stats, key=lambda s: getattr(s, field), reverse=True)
    if top is not None:
        stats = stats[:top]
    return stats


# ── Sales Funnel commands ────────────────────────────────────────────


@funnel_app.command('products')
def funnel_products(
        ctx: typer.Context,
        date_from: str = _FROM_OPT,
        date_to: str = _TO_OPT,
        nm_ids: str | None = typer.Option(None, '--nm-ids', help='Comma-separated NM IDs'),
        brands: str | None = typer.Option(None, '--brands', help='Comma-separated brand names'),
        subjects: str | None = typer.Option(None, '--subjects', help='Comma-separated subject IDs'),
        limit: int = _LIMIT_OPT,
        offset: int = _OFFSET_OPT,
        sort_by: str | None = typer.Option(
            None, '--sort-by',
            help='Sort by: orders, opens, cart, revenue, buyouts',
        ),
        top: int | None = typer.Option(
            None, '--top', '-n',
            help='Return only the top N results after sorting',
        ),
) -> None:
    """Product cards statistics for a period."""
    from wb.services._factory import create_analytics_service

    renderer = get_renderer(ctx)
    svc = create_analytics_service(get_profile(ctx))
    stats = svc.get_product_funnel(
        date_from, date_to,
        nm_ids=_parse_int_list(nm_ids),
        brand_names=_parse_str_list(brands),
        subject_ids=_parse_int_list(subjects),
        limit=limit,
        offset=offset,
    )
    stats = _sort_funnel(stats, sort_by, top)

    if not stats:
        renderer.success('No funnel data available.')
        return

    data = [asdict(s) for s in stats]
    headers = [
        'NM ID', 'Title', 'Opens', 'Cart', 'Orders',
        'Order Sum', 'Buyouts', 'Cart %', 'Order %',
    ]
    renderer.display(data, headers=headers, title='Sales Funnel', fields=get_fields(ctx))


@funnel_app.command('history')
def funnel_history(
        ctx: typer.Context,
        date_from: str = _FROM_OPT,
        date_to: str = _TO_OPT,
        nm_ids: str = typer.Option(..., '--nm-ids', help='Comma-separated NM IDs (1-20)'),
        aggregation: str = typer.Option('day', '--aggregation', '-a', help='day or week'),
) -> None:
    """Product cards statistics per days."""
    from wb.services._factory import create_analytics_service

    renderer = get_renderer(ctx)
    parsed_ids = _parse_int_list(nm_ids) or []
    svc = create_analytics_service(get_profile(ctx))
    items = svc.get_product_history(
        date_from, date_to, parsed_ids, aggregation=aggregation,
    )

    if not items:
        renderer.success('No history data available.')
        return

    data = [asdict(item) for item in items]
    headers = ['NM ID', 'Title', 'History']
    renderer.display(data, headers=headers, title='Funnel History', fields=get_fields(ctx))


@funnel_app.command('grouped')
def funnel_grouped(
        ctx: typer.Context,
        date_from: str = _FROM_OPT,
        date_to: str = _TO_OPT,
        brands: str | None = typer.Option(None, '--brands', help='Comma-separated brand names'),
        subjects: str | None = typer.Option(None, '--subjects', help='Comma-separated subject IDs'),
        aggregation: str = typer.Option('day', '--aggregation', '-a', help='day or week'),
) -> None:
    """Grouped product cards statistics per days."""
    from wb.services._factory import create_analytics_service

    renderer = get_renderer(ctx)
    svc = create_analytics_service(get_profile(ctx))
    items = svc.get_grouped_history(
        date_from, date_to,
        brand_names=_parse_str_list(brands),
        subject_ids=_parse_int_list(subjects),
        aggregation=aggregation,
    )

    if not items:
        renderer.success('No grouped history data available.')
        return

    data = [asdict(item) for item in items]
    headers = ['NM ID', 'Title', 'History']
    renderer.display(data, headers=headers, title='Grouped History', fields=get_fields(ctx))


# ── Search Report commands ───────────────────────────────────────────


@search_app.command('main')
def search_main(
        ctx: typer.Context,
        date_from: str = _FROM_OPT,
        date_to: str = _TO_OPT,
        nm_ids: str | None = typer.Option(None, '--nm-ids', help='Comma-separated NM IDs'),
        limit: int = _LIMIT_OPT,
        offset: int = _OFFSET_OPT,
) -> None:
    """Main search report page with general info and groups."""
    from wb.services._factory import create_analytics_service

    renderer = get_renderer(ctx)
    svc = create_analytics_service(get_profile(ctx))
    data = svc.get_search_report(
        date_from, date_to,
        nm_ids=_parse_int_list(nm_ids),
        limit=limit,
        offset=offset,
    )

    if not data:
        renderer.success('No search report data available.')
        return

    renderer.display(data, headers=[], title='Search Report', fields=get_fields(ctx))


@search_app.command('groups')
def search_groups(
        ctx: typer.Context,
        date_from: str = _FROM_OPT,
        date_to: str = _TO_OPT,
        nm_ids: str | None = typer.Option(None, '--nm-ids', help='Comma-separated NM IDs'),
        subjects: str | None = typer.Option(None, '--subjects', help='Comma-separated subject IDs'),
        brands: str | None = typer.Option(None, '--brands', help='Comma-separated brand names'),
        limit: int = _LIMIT_OPT,
        offset: int = _OFFSET_OPT,
) -> None:
    """Search report groups with pagination."""
    from wb.services._factory import create_analytics_service

    renderer = get_renderer(ctx)
    svc = create_analytics_service(get_profile(ctx))
    groups = svc.get_search_groups(
        date_from, date_to,
        nm_ids=_parse_int_list(nm_ids),
        subject_ids=_parse_int_list(subjects),
        brand_names=_parse_str_list(brands),
        limit=limit,
        offset=offset,
    )

    if not groups:
        renderer.success('No search groups available.')
        return

    data = [asdict(g) for g in groups]
    headers = ['Subject', 'Brand', 'Tag ID', 'Products']
    renderer.display(data, headers=headers, title='Search Groups', fields=get_fields(ctx))


@search_app.command('details')
def search_details(
        ctx: typer.Context,
        date_from: str = _FROM_OPT,
        date_to: str = _TO_OPT,
        subject_id: int | None = typer.Option(None, '--subject', help='Subject ID'),
        brand_name: str | None = typer.Option(None, '--brand', help='Brand name'),
        tag_id: int | None = typer.Option(None, '--tag', help='Tag ID'),
        nm_ids: str | None = typer.Option(None, '--nm-ids', help='Comma-separated NM IDs'),
        limit: int = _LIMIT_OPT,
        offset: int = _OFFSET_OPT,
) -> None:
    """Product details within a search report group."""
    from wb.services._factory import create_analytics_service

    renderer = get_renderer(ctx)
    svc = create_analytics_service(get_profile(ctx))
    products = svc.get_search_details(
        date_from, date_to,
        subject_id=subject_id,
        brand_name=brand_name,
        tag_id=tag_id,
        nm_ids=_parse_int_list(nm_ids),
        limit=limit,
        offset=offset,
    )

    if not products:
        renderer.success('No product details available.')
        return

    data = [asdict(p) for p in products]
    headers = ['NM ID', 'Name', 'Opens', 'Cart', 'Orders', 'Avg Pos', 'Visibility']
    renderer.display(data, headers=headers, title='Search Details', fields=get_fields(ctx))


@search_app.command('search-texts')
def search_texts(
        ctx: typer.Context,
        date_from: str = _FROM_OPT,
        date_to: str = _TO_OPT,
        nm_id: int = typer.Option(..., '--nm-id', '-n', help='Single WB article number'),
        limit: int = typer.Option(30, '--limit', '-l', help='Number of texts (max 100)'),
) -> None:
    """Top search texts for a product."""
    from wb.services._factory import create_analytics_service

    renderer = get_renderer(ctx)
    svc = create_analytics_service(get_profile(ctx))
    texts = svc.get_search_texts(date_from, date_to, nm_id, limit=limit)

    if not texts:
        renderer.success('No search texts available.')
        return

    data = [asdict(t) for t in texts]
    headers = ['Text', 'Frequency', 'Avg Pos', 'Opens', 'Cart', 'Orders', 'Visibility']
    renderer.display(data, headers=headers, title='Search Texts', fields=get_fields(ctx))


@search_app.command('orders')
def search_orders(
        ctx: typer.Context,
        date_from: str = _FROM_OPT,
        date_to: str = _TO_OPT,
        nm_id: int = typer.Option(..., '--nm-id', '-n', help='Single WB article number'),
        texts: str = typer.Option(..., '--texts', '-t', help='Comma-separated search texts'),
) -> None:
    """Orders and positions by product search texts."""
    from wb.services._factory import create_analytics_service

    renderer = get_renderer(ctx)
    text_list = _parse_str_list(texts) or []
    svc = create_analytics_service(get_profile(ctx))
    data = svc.get_search_orders(date_from, date_to, nm_id, text_list)

    if not data:
        renderer.success('No order data available.')
        return

    renderer.display(data, headers=[], title='Search Orders', fields=get_fields(ctx))


# ── CSV Report commands ──────────────────────────────────────────────


@csv_app.command('create')
def csv_create(
        ctx: typer.Context,
        report_type: str = typer.Option(..., '--type', '-t', help='Report type (e.g. DETAIL_HISTORY_REPORT)'),
        name: str = typer.Option(..., '--name', '-n', help='User-defined report name'),
        params_file: Path = typer.Option(
            ..., '--params-file', '-f',
            help='JSON file with report-specific params',
            exists=True, readable=True,
        ),
) -> None:
    """Create a CSV report generation task."""
    from wb.services._factory import create_analytics_service

    renderer = get_renderer(ctx)

    try:
        params = json.loads(params_file.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        renderer.error(f'Failed to read params file: {exc}')
        raise typer.Exit(ExitCode.VALIDATION_ERROR)

    svc = create_analytics_service(get_profile(ctx))
    status = svc.create_csv_report(report_type, name, params)

    data = asdict(status)
    renderer.display(data, headers=[], title='Report Created', fields=get_fields(ctx))


@csv_app.command('list')
def csv_list(
        ctx: typer.Context,
        ids: str | None = typer.Option(None, '--ids', help='Comma-separated report UUIDs'),
) -> None:
    """List CSV report generation tasks."""
    from wb.services._factory import create_analytics_service

    renderer = get_renderer(ctx)
    id_list = _parse_str_list(ids)
    svc = create_analytics_service(get_profile(ctx))
    reports = svc.list_csv_reports(id_list)

    if not reports:
        renderer.success('No reports found.')
        return

    data = [asdict(r) for r in reports]
    headers = ['ID', 'Name', 'Status', 'Size', 'Created', 'Start', 'End']
    renderer.display(data, headers=headers, title='CSV Reports', fields=get_fields(ctx))


@csv_app.command('retry')
def csv_retry(
        ctx: typer.Context,
        download_id: str = typer.Option(..., '--id', help='Report UUID to retry'),
) -> None:
    """Retry a failed CSV report generation."""
    from wb.services._factory import create_analytics_service

    renderer = get_renderer(ctx)
    svc = create_analytics_service(get_profile(ctx))
    message = svc.retry_csv_report(download_id)
    renderer.success(f'Retry requested: {message}')


@csv_app.command('download')
def csv_download(
        ctx: typer.Context,
        download_id: str = typer.Option(..., '--id', help='Report UUID to download'),
        output: Path = typer.Option(
            None, '--output', '-o',
            help='Output file path (default: report-{id}.zip)',
        ),
) -> None:
    """Download a generated CSV report as ZIP."""
    from wb.services._factory import create_analytics_service

    renderer = get_renderer(ctx)
    if output is None:
        output = Path(f'report-{download_id}.zip')

    svc = create_analytics_service(get_profile(ctx))
    saved = svc.download_csv_report(download_id, output)
    renderer.success(f'Report saved to {saved}')
