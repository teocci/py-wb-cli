"""CLI commands for search cluster management."""

from __future__ import annotations

from dataclasses import asdict

import typer

from wb.core.output import OutputRenderer
from wb.domain.enums import OutputFormat, VerbosityLevel

cluster_app = typer.Typer(
    help='Search cluster management',
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


def _cluster_rows(clusters):
    """Build table rows from cluster list."""
    return [
        [
            c.norm_query,
            'Yes' if c.is_active else 'No',
            str(c.bid),
            str(c.nm_id),
        ]
        for c in clusters
    ]


_CLUSTER_HEADERS = ['Norm Query', 'Active', 'Bid', 'NM ID']

_NM_OPT = typer.Option(..., '--nm', '-n', help='Product NM ID (WB article)')
_CAMPAIGN_OPT = typer.Option(..., '--campaign', '-c', help='Campaign ID')


@cluster_app.command('list')
def cluster_list(
        ctx: typer.Context,
        campaign_id: int = _CAMPAIGN_OPT,
        nm_id: int = _NM_OPT,
) -> None:
    """List all search clusters for a campaign/product."""
    from wb.services._factory import create_cluster_service

    renderer = _get_renderer(ctx)
    svc = create_cluster_service(_get_profile(ctx))
    clusters = svc.list_clusters(campaign_id, nm_id)

    if not clusters:
        renderer.success('No clusters found.')
        return

    data = [asdict(c) for c in clusters]
    renderer.display(data, headers=_CLUSTER_HEADERS, title='Search Clusters')


@cluster_app.command('active')
def cluster_active(
        ctx: typer.Context,
        campaign_id: int = _CAMPAIGN_OPT,
        nm_id: int = _NM_OPT,
) -> None:
    """List active search clusters for a campaign/product."""
    from wb.services._factory import create_cluster_service

    renderer = _get_renderer(ctx)
    svc = create_cluster_service(_get_profile(ctx))
    clusters = svc.get_active_clusters(campaign_id, nm_id)

    if not clusters:
        renderer.success('No active clusters found.')
        return

    data = [asdict(c) for c in clusters]
    renderer.display(data, headers=_CLUSTER_HEADERS, title='Active Clusters')


@cluster_app.command('inactive')
def cluster_inactive(
        ctx: typer.Context,
        campaign_id: int = _CAMPAIGN_OPT,
        nm_id: int = _NM_OPT,
) -> None:
    """List inactive search clusters for a campaign/product."""
    from wb.services._factory import create_cluster_service

    renderer = _get_renderer(ctx)
    svc = create_cluster_service(_get_profile(ctx))
    clusters = svc.get_inactive_clusters(campaign_id, nm_id)

    if not clusters:
        renderer.success('No inactive clusters found.')
        return

    data = [asdict(c) for c in clusters]
    renderer.display(data, headers=_CLUSTER_HEADERS, title='Inactive Clusters')


@cluster_app.command('bids')
def cluster_bids(
        ctx: typer.Context,
        campaign_id: int = _CAMPAIGN_OPT,
        nm_id: int = _NM_OPT,
) -> None:
    """List clusters with bids set for a campaign/product."""
    from wb.services._factory import create_cluster_service

    renderer = _get_renderer(ctx)
    svc = create_cluster_service(_get_profile(ctx))
    clusters = svc.get_cluster_bids(campaign_id, nm_id)

    if not clusters:
        renderer.success('No cluster bids found.')
        return

    data = [asdict(c) for c in clusters]
    renderer.display(data, headers=_CLUSTER_HEADERS, title='Cluster Bids')


@cluster_app.command('stats')
def cluster_stats(
        ctx: typer.Context,
        campaign_id: int = _CAMPAIGN_OPT,
        nm_id: int = _NM_OPT,
        date_from: str = typer.Option(
            ..., '--from', help='Start date (YYYY-MM-DD)',
        ),
        date_to: str = typer.Option(
            ..., '--to', help='End date (YYYY-MM-DD)',
        ),
) -> None:
    """Show statistics for search clusters in a campaign/product."""
    from wb.services._factory import create_cluster_service

    renderer = _get_renderer(ctx)
    svc = create_cluster_service(_get_profile(ctx))
    stats = svc.get_cluster_stats(campaign_id, nm_id, date_from, date_to)

    if not stats:
        renderer.success('No cluster statistics available.')
        return

    data = [asdict(s) for s in stats]
    headers = [
        'Norm Query', 'Views', 'Clicks', 'CTR',
        'Orders', 'Spend', 'Avg Pos',
    ]
    rows = [
        [
            s.norm_query,
            str(s.views),
            str(s.clicks),
            f'{s.ctr:.2f}%',
            str(s.orders),
            str(s.spend),
            f'{s.avg_pos:.1f}',
        ]
        for s in stats
    ]
    renderer.display(data, headers=headers, title='Cluster Statistics')
