"""CLI commands for bid management."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import typer

from wb.cli._helpers import (
    confirm_or_abort,
    get_fields,
    get_profile,
    get_renderer,
    resolve_profile_name,
)
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
        nm_id: int | None = typer.Option(
            None, '--nm',
            help='Scope to a single NM (default: loop over all campaign items)',
        ),
) -> None:
    """Show recommended bids for a CPM campaign.

    Calls ``GET /api/advert/v0/bids/recommendations`` per item. With no
    ``--nm`` flag, loops over every product in the campaign — this may
    take several minutes for campaigns with many items because the
    endpoint is rate-limited to 5 requests per minute on personal tokens.
    """
    from wb.services._factory import create_bid_service

    renderer = get_renderer(ctx)
    svc = create_bid_service(get_profile(ctx))
    bids = svc.get_recommended_bids(campaign_id, nm_id=nm_id)

    if not bids:
        renderer.success('No bid recommendations available.')
        return

    if renderer.is_json:
        typer.echo(
            json.dumps([asdict(b) for b in bids], indent=2, ensure_ascii=False)
        )
        return

    from wb.core.output import render_table
    headers = ['NM ID', 'Competitive', 'Leaders', 'Top-2', 'Error']
    rows = [
        [
            str(b.nm_id),
            str(b.competitive),
            str(b.leaders),
            str(b.top2),
            b.error or '',
        ]
        for b in bids
    ]
    render_table(headers, rows, title='Recommended Bids (kopecks)')


@bid_app.command('minimum')
def bid_minimum(
        ctx: typer.Context,
        campaign_id: int = typer.Option(
            ..., '--campaign', '-c', help='Campaign ID',
        ),
) -> None:
    """Show minimum allowed bids per placement for a campaign.

    Calls ``POST /api/advert/v1/bids/min`` with every product in the
    campaign (batched at 100 per call). Returns the per-placement floor
    that WB will accept.
    """
    from wb.services._factory import create_bid_service

    renderer = get_renderer(ctx)
    svc = create_bid_service(get_profile(ctx))
    bids = svc.get_minimum_bids(campaign_id)

    if not bids:
        renderer.success('No bid data available.')
        return

    if renderer.is_json:
        typer.echo(
            json.dumps([asdict(b) for b in bids], indent=2, ensure_ascii=False)
        )
        return

    from wb.core.output import render_table
    headers = ['NM ID', 'Combined', 'Search', 'Recommendation']
    rows = [
        [str(b.nm_id), str(b.combined), str(b.search), str(b.recommendation)]
        for b in bids
    ]
    render_table(headers, rows, title='Minimum Bids (kopecks)')


@bid_app.command('get-items')
def bid_get_items(
        ctx: typer.Context,
        campaign_id: int = typer.Option(
            ..., '--campaign', '-c', help='Campaign ID',
        ),
) -> None:
    """Show current per-item bids for a campaign.

    Reads bid values directly from ``/api/advert/v2/adverts`` —
    ``nm_settings[].bids_kopecks`` — so no extra API call is needed
    beyond the campaign-info fetch.
    """
    from wb.services._factory import create_bid_service

    renderer = get_renderer(ctx)
    svc = create_bid_service(get_profile(ctx))
    bids = svc.get_item_bids(campaign_id)

    if not bids:
        renderer.success('No item bid data available.')
        return

    if renderer.is_json:
        typer.echo(
            json.dumps([asdict(b) for b in bids], indent=2, ensure_ascii=False)
        )
        return

    from wb.core.output import render_table
    headers = ['NM ID', 'Search', 'Recommendations']
    rows = [
        [str(b.nm_id), str(b.search), str(b.recommendations)]
        for b in bids
    ]
    render_table(headers, rows, title='Current Bids (kopecks)')


def _log_bid_mutation(profile: str, command: str, result) -> None:
    """Write an audit entry for a bid mutation.

    Args:
        profile: Resolved profile name.
        command: CLI command invoked.
        result: MutationResult from the service.
    """
    from wb.services._factory import create_audit_logger
    audit = create_audit_logger(profile)
    audit.log(
        profile=profile,
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
        _log_bid_mutation(resolve_profile_name(ctx), 'bid set-item', result)

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')


@bid_app.command('set-items')
def bid_set_items(
        ctx: typer.Context,
        campaign_id: int = typer.Option(..., '--campaign', '-c', help='Campaign ID'),
        file: Path | None = typer.Option(
            None, '--file', '-f', help='JSON file with bid mutations',
        ),
        bids: str | None = typer.Option(
            None, '--bids',
            help='Inline JSON bid mutations: \'[{"nm_id":123,"bid_kopecks":450}]\'',
        ),
        dry_run: bool = typer.Option(False, '--dry-run', help='Plan without executing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Set bids for multiple items from a JSON file or inline JSON.

    File format: [{"nm_id": 123, "bid_kopecks": 450, "placement": "search"}, ...]
    """
    from wb.services._factory import create_bid_service

    renderer = get_renderer(ctx)

    if file is None and bids is None:
        renderer.error('Provide either --file or --bids')
        raise typer.Exit(ExitCode.VALIDATION_ERROR)
    if file is not None and bids is not None:
        renderer.error('Use --file or --bids, not both')
        raise typer.Exit(ExitCode.VALIDATION_ERROR)

    raw: list
    if file is not None:
        if not file.exists():
            renderer.error(f'File not found: {file}')
            raise typer.Exit(ExitCode.VALIDATION_ERROR)
        try:
            raw = json.loads(file.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            renderer.error(f'Failed to read bid file: {exc}')
            raise typer.Exit(ExitCode.VALIDATION_ERROR)
    else:
        try:
            raw = json.loads(bids)  # type: ignore[arg-type]
        except json.JSONDecodeError as exc:
            renderer.error(f'Invalid --bids JSON: {exc}')
            raise typer.Exit(ExitCode.VALIDATION_ERROR)

    if not isinstance(raw, list):
        renderer.error('Bid input must be a JSON array')
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

    if not dry_run:
        for result in results:
            if result.success:
                _log_bid_mutation(resolve_profile_name(ctx), 'bid set-items', result)

    if renderer.is_json:
        from dataclasses import asdict as _asdict
        renderer.display([_asdict(r) for r in results], fields=get_fields(ctx))
        return

    prefix = '[DRY-RUN] ' if dry_run else ''
    success_count = sum(1 for r in results if r.success)
    renderer.success(f'{prefix}Set {success_count}/{len(results)} bids')
