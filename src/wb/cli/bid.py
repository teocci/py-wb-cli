"""CLI commands for bid management."""

from __future__ import annotations

from dataclasses import asdict

import typer

from wb.core.output import OutputRenderer
from wb.domain.enums import OutputFormat, VerbosityLevel

bid_app = typer.Typer(
    help='Bid management',
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


@bid_app.command('recommend')
def bid_recommend(
        ctx: typer.Context,
        campaign_id: int = typer.Option(
            ..., '--campaign', '-c', help='Campaign ID',
        ),
) -> None:
    """Show recommended bids for a campaign."""
    from wb.services._factory import create_bid_service

    renderer = _get_renderer(ctx)
    svc = create_bid_service(_get_profile(ctx))
    bids = svc.get_recommended_bids(campaign_id)

    if not bids:
        renderer.success('No bid recommendations available.')
        return

    data = [asdict(b) for b in bids]
    headers = ['NM ID', 'Recommended', 'Minimum']
    rows = [
        [str(b.nm_id), str(b.recommended), str(b.minimum)]
        for b in bids
    ]
    renderer.display(data, headers=headers, title='Recommended Bids')


@bid_app.command('minimum')
def bid_minimum(
        ctx: typer.Context,
        campaign_id: int = typer.Option(
            ..., '--campaign', '-c', help='Campaign ID',
        ),
) -> None:
    """Show minimum bids for a campaign."""
    from wb.services._factory import create_bid_service

    renderer = _get_renderer(ctx)
    svc = create_bid_service(_get_profile(ctx))
    bids = svc.get_minimum_bids(campaign_id)

    if not bids:
        renderer.success('No bid data available.')
        return

    data = [asdict(b) for b in bids]
    headers = ['NM ID', 'Minimum', 'Recommended']
    rows = [
        [str(b.nm_id), str(b.minimum), str(b.recommended)]
        for b in bids
    ]
    renderer.display(data, headers=headers, title='Minimum Bids')


@bid_app.command('get-items')
def bid_get_items(
        ctx: typer.Context,
        campaign_id: int = typer.Option(
            ..., '--campaign', '-c', help='Campaign ID',
        ),
) -> None:
    """Show per-item bid details for a campaign."""
    from wb.services._factory import create_bid_service

    renderer = _get_renderer(ctx)
    svc = create_bid_service(_get_profile(ctx))
    bids = svc.get_item_bids(campaign_id)

    if not bids:
        renderer.success('No item bid data available.')
        return

    data = [asdict(b) for b in bids]
    headers = ['NM ID', 'Recommended', 'Minimum']
    rows = [
        [str(b.nm_id), str(b.recommended), str(b.minimum)]
        for b in bids
    ]
    renderer.display(data, headers=headers, title='Item Bids')
