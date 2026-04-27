"""CLI commands for local domain snapshots (campaigns, stats, clusters, budget events)."""

from __future__ import annotations

from dataclasses import asdict

import typer

from wb.cli._helpers import get_fields, get_renderer, resolve_profile_name

__all__ = ['snapshot_app']

snapshot_app = typer.Typer(
    help='Local domain snapshots (campaigns, stats, clusters, budget events)',
    no_args_is_help=True,
)

history_app = typer.Typer(
    help='Query stored snapshot history',
    no_args_is_help=True,
)

snapshot_app.add_typer(history_app, name='history')


# ── Snapshot management commands ──────────────────────────────────────

@snapshot_app.command('list')
def snapshot_list(
        ctx: typer.Context,
        campaign_id: int | None = typer.Option(
            None, '--campaign', '-c', help='Filter by campaign ID',
        ),
        limit: int = typer.Option(50, '--limit', '-l', help='Max rows to show'),
) -> None:
    """Show stored campaign snapshots (or summary if no campaign given)."""
    from wb.services._factory import create_cache_service

    renderer = get_renderer(ctx)
    profile = resolve_profile_name(ctx)
    svc = create_cache_service(profile)

    if campaign_id is None:
        counts = svc.summary(profile)
        if renderer.is_json:
            renderer.display(counts, fields=get_fields(ctx))
            return
        rows = [[k, str(v)] for k, v in counts.items()]
        renderer.display(rows, headers=['Table', 'Rows'], title='Snapshot Summary', fields=get_fields(ctx))
    else:
        snaps = svc.history_campaigns(profile, campaign_id, limit)
        data = [asdict(s) for s in snaps]
        rows = [
            [s.snapshot_time[:19], str(s.campaign_id), s.name, str(s.status)]
            for s in snaps
        ]
        renderer.display(
            data,
            headers=['Snapshot Time', 'Campaign ID', 'Name', 'Status'],
            title=f'Snapshots — Campaign {campaign_id}',
            fields=get_fields(ctx),
        )


@snapshot_app.command('capture')
def snapshot_capture(
        ctx: typer.Context,
        campaign_id: int = typer.Option(
            ..., '--campaign', '-c', help='Campaign ID to capture',
        ),
        nm_id: int | None = typer.Option(
            None, '--nm', help='Product nm_id (required for cluster capture)',
        ),
        no_stats: bool = typer.Option(False, '--no-stats', help='Skip stats capture'),
        no_clusters: bool = typer.Option(False, '--no-clusters', help='Skip cluster capture'),
) -> None:
    """Capture current WB API state for a campaign to local storage."""
    from wb.services._factory import create_cache_service

    renderer = get_renderer(ctx)
    profile = resolve_profile_name(ctx)
    svc = create_cache_service(profile)

    counts = svc.snapshot_campaign(
        campaign_id,
        profile,
        nm_id=nm_id,
        with_stats=not no_stats,
        with_clusters=not no_clusters,
    )
    renderer.display(
        counts,
        headers=['Type', 'Rows Saved'],
        title=f'Snapshot — Campaign {campaign_id}',
        fields=get_fields(ctx),
    )
    renderer.success(
        f'Capture complete: {counts["campaigns"]} campaign, '
        f'{counts["stats"]} stats, {counts["clusters"]} clusters'
    )


@snapshot_app.command('capture-all')
def snapshot_capture_all(ctx: typer.Context) -> None:
    """Capture config snapshots for all active campaigns."""
    from wb.services._factory import create_cache_service

    renderer = get_renderer(ctx)
    profile = resolve_profile_name(ctx)
    svc = create_cache_service(profile)

    counts = svc.snapshot_all(profile)
    renderer.success(
        f'Captured {counts["campaigns"]} active campaign(s).'
    )


@snapshot_app.command('clear')
def snapshot_clear(
        ctx: typer.Context,
        campaign_id: int | None = typer.Option(
            None, '--campaign', '-c', help='Clear only this campaign (all if omitted)',
        ),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Delete stored snapshots for this profile (optionally scoped to one campaign)."""
    from wb.services._factory import create_cache_service

    renderer = get_renderer(ctx)
    profile = resolve_profile_name(ctx)

    scope = f'campaign {campaign_id}' if campaign_id else 'all campaigns'
    if not (yes or renderer.is_json):
        confirmed = typer.confirm(
            f'Clear snapshot data for {scope} in profile {profile!r}?',
            default=False,
        )
        if not confirmed:
            raise typer.Abort()

    svc = create_cache_service(profile)
    counts = svc.clear(profile, campaign_id)
    total = sum(counts.values())
    renderer.success(f'Cleared {total} rows across {len(counts)} tables.')


# ── History sub-commands ──────────────────────────────────────────────

@history_app.command('campaigns')
def history_campaigns(
        ctx: typer.Context,
        campaign_id: int | None = typer.Option(
            None, '--campaign', '-c', help='Filter by campaign ID',
        ),
        limit: int = typer.Option(50, '--limit', '-l', help='Max rows to show'),
) -> None:
    """Show stored campaign config snapshots."""
    from wb.services._factory import create_cache_service

    renderer = get_renderer(ctx)
    profile = resolve_profile_name(ctx)
    svc = create_cache_service(profile)

    snaps = svc.history_campaigns(profile, campaign_id, limit)
    data = [asdict(s) for s in snaps]
    renderer.display(
        data,
        headers=['Time', 'Campaign ID', 'Name', 'Status', 'Budget'],
        title='Campaign Snapshot History',
        fields=get_fields(ctx),
    )


@history_app.command('stats')
def history_stats(
        ctx: typer.Context,
        campaign_id: int = typer.Option(
            ..., '--campaign', '-c', help='Campaign ID',
        ),
        date_from: str | None = typer.Option(
            None, '--from', help='Start date YYYY-MM-DD',
        ),
        date_to: str | None = typer.Option(
            None, '--to', help='End date YYYY-MM-DD',
        ),
        limit: int = typer.Option(90, '--limit', '-l', help='Max rows to show'),
) -> None:
    """Show stored daily stats snapshots for a campaign."""
    from wb.services._factory import create_cache_service

    renderer = get_renderer(ctx)
    profile = resolve_profile_name(ctx)
    svc = create_cache_service(profile)

    records = svc.history_stats(profile, campaign_id, date_from, date_to, limit)
    data = [asdict(r) for r in records]
    renderer.display(
        data,
        headers=['Date', 'Views', 'Clicks', 'CTR', 'Spend', 'Orders'],
        title=f'Stats History — Campaign {campaign_id}',
        fields=get_fields(ctx),
    )


@history_app.command('clusters')
def history_clusters(
        ctx: typer.Context,
        campaign_id: int = typer.Option(
            ..., '--campaign', '-c', help='Campaign ID',
        ),
        nm_id: int | None = typer.Option(
            None, '--nm', help='Filter by product nm_id',
        ),
        limit: int = typer.Option(200, '--limit', '-l', help='Max rows to show'),
) -> None:
    """Show stored cluster snapshots for a campaign."""
    from wb.services._factory import create_cache_service

    renderer = get_renderer(ctx)
    profile = resolve_profile_name(ctx)
    svc = create_cache_service(profile)

    records = svc.history_clusters(profile, campaign_id, nm_id, limit)
    data = [asdict(r) for r in records]
    renderer.display(
        data,
        headers=['Time', 'NM ID', 'Query', 'Bid', 'Views', 'Clicks'],
        title=f'Cluster History — Campaign {campaign_id}',
        fields=get_fields(ctx),
    )
