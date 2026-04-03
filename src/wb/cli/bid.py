"""CLI commands for bid management."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import typer

from wb.cli._helpers import confirm_or_abort, get_profile, get_renderer
from wb.core.constants import ExitCode
from wb.domain.models import BidMutation

bid_app = typer.Typer(
    help='Bid management',
    no_args_is_help=True,
)


@bid_app.command('recommend')
def bid_recommend(
        ctx: typer.Context,
        campaign_id: int = typer.Option(
            ..., '--campaign', '-c', help='Campaign ID',
        ),
) -> None:
    """Show recommended bids for a campaign."""
    from wb.services._factory import create_bid_service

    renderer = get_renderer(ctx)
    svc = create_bid_service(get_profile(ctx))
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

    renderer = get_renderer(ctx)
    svc = create_bid_service(get_profile(ctx))
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

    renderer = get_renderer(ctx)
    svc = create_bid_service(get_profile(ctx))
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


def _log_bid_mutation(profile: str | None, command: str, result) -> None:
    """Write an audit entry for a bid mutation.

    Args:
        profile: Active profile name.
        command: CLI command invoked.
        result: MutationResult from the service.
    """
    from wb.services._factory import create_audit_logger
    audit = create_audit_logger(profile)
    audit.log(
        profile=profile or 'default',
        command=command,
        target_id=result.target_id,
        payload={'action': result.action},
        result=result.message,
    )


@bid_app.command('set-item')
def bid_set_item(
        ctx: typer.Context,
        campaign_id: int = typer.Option(..., '--campaign', '-c', help='Campaign ID'),
        nm_id: int = typer.Option(..., '--nm', help='Product NM ID'),
        cpm: int = typer.Option(..., '--cpm', help='Bid value in kopecks'),
        placement: str = typer.Option('search', '--placement', help='Placement type'),
        dry_run: bool = typer.Option(False, '--dry-run', help='Plan without executing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Set a bid for a single item in a campaign."""
    from wb.services._factory import create_bid_service

    renderer = get_renderer(ctx)
    mutation = BidMutation(nm_id=nm_id, bid_kopecks=cpm, placement=placement)
    action = f'set bid={cpm} for nm={nm_id} in campaign {campaign_id}'
    confirm_or_abort(renderer, action, yes or dry_run)

    svc = create_bid_service(get_profile(ctx))
    result = svc.set_item_bid(campaign_id, mutation, dry_run=dry_run)

    if not dry_run:
        _log_bid_mutation(get_profile(ctx), 'bid set-item', result)

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')


@bid_app.command('set-items')
def bid_set_items(
        ctx: typer.Context,
        campaign_id: int = typer.Option(..., '--campaign', '-c', help='Campaign ID'),
        file: Path = typer.Option(
            ..., '--file', '-f', help='JSON file with bid mutations',
            exists=True, readable=True,
        ),
        dry_run: bool = typer.Option(False, '--dry-run', help='Plan without executing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Set bids for multiple items from a JSON file.

    File format: [{"nm_id": 123, "bid_kopecks": 450, "placement": "search"}, ...]
    """
    from wb.services._factory import create_bid_service

    renderer = get_renderer(ctx)

    try:
        raw = json.loads(file.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        renderer.error(f'Failed to read bid file: {exc}')
        raise typer.Exit(ExitCode.VALIDATION_ERROR)

    if not isinstance(raw, list):
        renderer.error('Bid file must contain a JSON array')
        raise typer.Exit(ExitCode.VALIDATION_ERROR)

    try:
        mutations = [
            BidMutation(
                nm_id=item['nm_id'],
                bid_kopecks=item.get('bid_kopecks', item.get('cpm', 0)),
                placement=item.get('placement', 'search'),
            )
            for item in raw
        ]
    except (KeyError, TypeError) as exc:
        renderer.error(f'Invalid bid entry: {exc}')
        raise typer.Exit(ExitCode.VALIDATION_ERROR)

    action = f'set {len(mutations)} bids in campaign {campaign_id}'
    confirm_or_abort(renderer, action, yes or dry_run)

    svc = create_bid_service(get_profile(ctx))
    results = svc.set_item_bids(campaign_id, mutations, dry_run=dry_run)

    for result in results:
        if not dry_run:
            _log_bid_mutation(get_profile(ctx), 'bid set-items', result)

    prefix = '[DRY-RUN] ' if dry_run else ''
    success_count = sum(1 for r in results if r.success)
    renderer.success(f'{prefix}Set {success_count}/{len(results)} bids')
