"""CLI commands for bid management."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import typer

from wb.core.output import OutputRenderer
from wb.domain.enums import OutputFormat, VerbosityLevel
from wb.domain.models import BidMutation

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
        cpm: int = typer.Option(..., '--cpm', help='CPM bid value in kopecks'),
        subject_id: int = typer.Option(0, '--subject', help='Subject scope (0 = all)'),
        dry_run: bool = typer.Option(False, '--dry-run', help='Plan without executing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Set a CPM bid for a single item in a campaign."""
    from wb.services._factory import create_bid_service

    renderer = _get_renderer(ctx)
    mutation = BidMutation(nm_id=nm_id, cpm=cpm, subject_id=subject_id)
    action = f'set cpm={cpm} for nm={nm_id} in campaign {campaign_id}'

    if not (yes or dry_run or renderer.is_json):
        confirmed = typer.confirm(f'About to: {action}. Proceed?', default=False)
        if not confirmed:
            raise typer.Abort()

    svc = create_bid_service(_get_profile(ctx))
    result = svc.set_item_bid(campaign_id, mutation, dry_run=dry_run)

    if not dry_run:
        _log_bid_mutation(_get_profile(ctx), 'bid set-item', result)

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
    """Set CPM bids for multiple items from a JSON file.

    File format: [{"nm_id": 123, "cpm": 450, "subject_id": 0}, ...]
    """
    from wb.services._factory import create_bid_service

    renderer = _get_renderer(ctx)

    try:
        raw = json.loads(file.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        renderer.error(f'Failed to read bid file: {exc}')
        raise typer.Exit(2)

    if not isinstance(raw, list):
        renderer.error('Bid file must contain a JSON array')
        raise typer.Exit(2)

    try:
        mutations = [
            BidMutation(
                nm_id=item['nm_id'],
                cpm=item['cpm'],
                subject_id=item.get('subject_id', 0),
            )
            for item in raw
        ]
    except (KeyError, TypeError) as exc:
        renderer.error(f'Invalid bid entry: {exc}')
        raise typer.Exit(2)

    action = f'set {len(mutations)} bids in campaign {campaign_id}'
    if not (yes or dry_run or renderer.is_json):
        confirmed = typer.confirm(f'About to: {action}. Proceed?', default=False)
        if not confirmed:
            raise typer.Abort()

    svc = create_bid_service(_get_profile(ctx))
    results = svc.set_item_bids(campaign_id, mutations, dry_run=dry_run)

    for result in results:
        if not dry_run:
            _log_bid_mutation(_get_profile(ctx), 'bid set-items', result)

    prefix = '[DRY-RUN] ' if dry_run else ''
    success_count = sum(1 for r in results if r.success)
    renderer.success(f'{prefix}Set {success_count}/{len(results)} bids')
