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
            str(c.cluster_id),
            c.cluster_name,
            str(c.count),
            'Yes' if c.is_active else 'No',
            str(c.bid),
            str(c.recommended_bid),
        ]
        for c in clusters
    ]


_CLUSTER_HEADERS = ['ID', 'Name', 'Count', 'Active', 'Bid', 'Recommended']


@cluster_app.command('list')
def cluster_list(
        ctx: typer.Context,
        campaign_id: int = typer.Option(
            ..., '--campaign', '-c', help='Campaign ID',
        ),
) -> None:
    """List all search clusters for a campaign."""
    from wb.services._factory import create_cluster_service

    renderer = _get_renderer(ctx)
    svc = create_cluster_service(_get_profile(ctx))
    clusters = svc.list_clusters(campaign_id)

    if not clusters:
        renderer.success('No clusters found.')
        return

    data = [asdict(c) for c in clusters]
    rows = _cluster_rows(clusters)
    renderer.display(data, headers=_CLUSTER_HEADERS, title='Search Clusters')


@cluster_app.command('active')
def cluster_active(
        ctx: typer.Context,
        campaign_id: int = typer.Option(
            ..., '--campaign', '-c', help='Campaign ID',
        ),
) -> None:
    """List active search clusters for a campaign."""
    from wb.services._factory import create_cluster_service

    renderer = _get_renderer(ctx)
    svc = create_cluster_service(_get_profile(ctx))
    clusters = svc.get_active_clusters(campaign_id)

    if not clusters:
        renderer.success('No active clusters found.')
        return

    data = [asdict(c) for c in clusters]
    rows = _cluster_rows(clusters)
    renderer.display(data, headers=_CLUSTER_HEADERS, title='Active Clusters')


@cluster_app.command('inactive')
def cluster_inactive(
        ctx: typer.Context,
        campaign_id: int = typer.Option(
            ..., '--campaign', '-c', help='Campaign ID',
        ),
) -> None:
    """List inactive search clusters for a campaign."""
    from wb.services._factory import create_cluster_service

    renderer = _get_renderer(ctx)
    svc = create_cluster_service(_get_profile(ctx))
    clusters = svc.get_inactive_clusters(campaign_id)

    if not clusters:
        renderer.success('No inactive clusters found.')
        return

    data = [asdict(c) for c in clusters]
    rows = _cluster_rows(clusters)
    renderer.display(data, headers=_CLUSTER_HEADERS, title='Inactive Clusters')


@cluster_app.command('bids')
def cluster_bids(
        ctx: typer.Context,
        campaign_id: int = typer.Option(
            ..., '--campaign', '-c', help='Campaign ID',
        ),
) -> None:
    """List clusters with bids set for a campaign."""
    from wb.services._factory import create_cluster_service

    renderer = _get_renderer(ctx)
    svc = create_cluster_service(_get_profile(ctx))
    clusters = svc.get_cluster_bids(campaign_id)

    if not clusters:
        renderer.success('No cluster bids found.')
        return

    data = [asdict(c) for c in clusters]
    rows = _cluster_rows(clusters)
    renderer.display(data, headers=_CLUSTER_HEADERS, title='Cluster Bids')


@cluster_app.command('stats')
def cluster_stats(
        ctx: typer.Context,
        campaign_id: int = typer.Option(
            ..., '--campaign', '-c', help='Campaign ID',
        ),
) -> None:
    """Show statistics for search clusters in a campaign."""
    from wb.services._factory import create_stats_service

    renderer = _get_renderer(ctx)
    svc = create_stats_service(_get_profile(ctx))
    stats = svc.get_cluster_stats(campaign_id)

    if not stats:
        renderer.success('No cluster statistics available.')
        return

    data = [asdict(s) for s in stats]
    headers = ['ID', 'Name', 'Views', 'Clicks', 'CTR', 'Orders', 'Spend']
    rows = [
        [
            str(s.cluster_id),
            s.cluster_name,
            str(s.views),
            str(s.clicks),
            f'{s.ctr:.2f}%',
            str(s.orders),
            str(s.spend),
        ]
        for s in stats
    ]
    renderer.display(data, headers=headers, title='Cluster Statistics')
