"""CLI commands for search cluster management."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import typer

from wb.core.output import OutputRenderer
from wb.domain.enums import OutputFormat, VerbosityLevel
from wb.domain.models import ClusterBidMutation

cluster_app = typer.Typer(
    help='Search cluster management',
    no_args_is_help=True,
)

minus_app = typer.Typer(
    help='Minus phrase management',
    no_args_is_help=True,
)
cluster_app.add_typer(minus_app, name='minus', help='Minus phrase management')


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


def _confirm_or_abort(
        renderer: OutputRenderer,
        action: str,
        yes: bool,
) -> None:
    """Prompt for confirmation unless --yes is set.

    Args:
        renderer: Current output renderer.
        action: Human-readable description of the action.
        yes: Skip prompt if True.
    """
    if yes or renderer.is_json:
        return
    confirmed = typer.confirm(f'About to: {action}. Proceed?', default=False)
    if not confirmed:
        raise typer.Abort()


def _log_mutation(profile: str | None, command: str, result) -> None:
    """Write an audit entry for a completed mutation.

    Args:
        profile: Active profile name.
        command: CLI command that was invoked.
        result: MutationResult from the service call.
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
_DRY_RUN_OPT = typer.Option(False, '--dry-run', help='Plan without executing')
_YES_OPT = typer.Option(False, '--yes', '-y', help='Skip confirmation')


# ── Read commands ────────────────────────────────────────────────────


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
    renderer.display(data, headers=headers, title='Cluster Statistics')


@cluster_app.command('stats-daily')
def cluster_stats_daily(
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
    """Show daily statistics for search clusters in a campaign/product."""
    from wb.services._factory import create_cluster_service

    renderer = _get_renderer(ctx)
    svc = create_cluster_service(_get_profile(ctx))
    daily = svc.get_cluster_stats_daily(
        campaign_id, nm_id, date_from, date_to,
    )

    if not daily:
        renderer.success('No daily cluster statistics available.')
        return

    headers = [
        'Date', 'Norm Query', 'Views', 'Clicks', 'CTR',
        'Orders', 'Spend', 'Avg Pos',
    ]
    renderer.display(daily, headers=headers, title='Daily Cluster Statistics')


# ── Write commands ───────────────────────────────────────────────────


@cluster_app.command('set-bids')
def cluster_set_bids(
        ctx: typer.Context,
        campaign_id: int = _CAMPAIGN_OPT,
        nm_id: int = _NM_OPT,
        query: str = typer.Option(
            ..., '--query', '-q', help='Norm query (cluster phrase)',
        ),
        bid: int = typer.Option(
            ..., '--bid', '-b', help='Bid value in kopecks',
        ),
        dry_run: bool = _DRY_RUN_OPT,
        yes: bool = _YES_OPT,
) -> None:
    """Set a bid for a single search cluster."""
    from wb.services._factory import create_cluster_service

    renderer = _get_renderer(ctx)
    mutation = ClusterBidMutation(nm_id=nm_id, norm_query=query, bid=bid)
    action = f'set cluster bid={bid} for "{query}" in campaign {campaign_id}'
    _confirm_or_abort(renderer, action, yes or dry_run)

    svc = create_cluster_service(_get_profile(ctx))
    result = svc.set_cluster_bids(campaign_id, [mutation], dry_run=dry_run)

    if not dry_run:
        _log_mutation(_get_profile(ctx), 'cluster set-bids', result)

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')


@cluster_app.command('set-bids-file')
def cluster_set_bids_file(
        ctx: typer.Context,
        campaign_id: int = _CAMPAIGN_OPT,
        file: Path = typer.Option(
            ..., '--file', '-f',
            help='JSON file with cluster bid mutations',
            exists=True, readable=True,
        ),
        dry_run: bool = _DRY_RUN_OPT,
        yes: bool = _YES_OPT,
) -> None:
    """Set bids for multiple search clusters from a JSON file.

    File format: [{"nm_id": 123, "norm_query": "sneakers", "bid": 500}, ...]
    """
    from wb.services._factory import create_cluster_service

    renderer = _get_renderer(ctx)
    mutations = _parse_bid_file(renderer, file)
    action = f'set {len(mutations)} cluster bid(s) in campaign {campaign_id}'
    _confirm_or_abort(renderer, action, yes or dry_run)

    svc = create_cluster_service(_get_profile(ctx))
    result = svc.set_cluster_bids(campaign_id, mutations, dry_run=dry_run)

    if not dry_run:
        _log_mutation(_get_profile(ctx), 'cluster set-bids-file', result)

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')


@cluster_app.command('delete-bids')
def cluster_delete_bids(
        ctx: typer.Context,
        campaign_id: int = _CAMPAIGN_OPT,
        nm_id: int = _NM_OPT,
        query: str = typer.Option(
            ..., '--query', '-q', help='Norm query (cluster phrase)',
        ),
        bid: int = typer.Option(
            ..., '--bid', '-b', help='Current bid value in kopecks',
        ),
        dry_run: bool = _DRY_RUN_OPT,
        yes: bool = _YES_OPT,
) -> None:
    """Delete a bid from a single search cluster."""
    from wb.services._factory import create_cluster_service

    renderer = _get_renderer(ctx)
    mutation = ClusterBidMutation(nm_id=nm_id, norm_query=query, bid=bid)
    action = (
        f'delete cluster bid for "{query}" from campaign {campaign_id}'
    )
    _confirm_or_abort(renderer, action, yes or dry_run)

    svc = create_cluster_service(_get_profile(ctx))
    result = svc.delete_cluster_bids(campaign_id, [mutation], dry_run=dry_run)

    if not dry_run:
        _log_mutation(_get_profile(ctx), 'cluster delete-bids', result)

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')


@cluster_app.command('delete-bids-file')
def cluster_delete_bids_file(
        ctx: typer.Context,
        campaign_id: int = _CAMPAIGN_OPT,
        file: Path = typer.Option(
            ..., '--file', '-f',
            help='JSON file with cluster bid mutations to delete',
            exists=True, readable=True,
        ),
        dry_run: bool = _DRY_RUN_OPT,
        yes: bool = _YES_OPT,
) -> None:
    """Delete bids for multiple search clusters from a JSON file.

    File format: [{"nm_id": 123, "norm_query": "sneakers", "bid": 500}, ...]
    """
    from wb.services._factory import create_cluster_service

    renderer = _get_renderer(ctx)
    mutations = _parse_bid_file(renderer, file)
    action = (
        f'delete {len(mutations)} cluster bid(s) '
        f'from campaign {campaign_id}'
    )
    _confirm_or_abort(renderer, action, yes or dry_run)

    svc = create_cluster_service(_get_profile(ctx))
    result = svc.delete_cluster_bids(campaign_id, mutations, dry_run=dry_run)

    if not dry_run:
        _log_mutation(
            _get_profile(ctx), 'cluster delete-bids-file', result,
        )

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')


# ── Minus phrase commands ────────────────────────────────────────────


@minus_app.command('list')
def minus_list(
        ctx: typer.Context,
        campaign_id: int = _CAMPAIGN_OPT,
        nm_id: int = _NM_OPT,
) -> None:
    """List minus phrases for a campaign/product."""
    from wb.services._factory import create_cluster_service

    renderer = _get_renderer(ctx)
    svc = create_cluster_service(_get_profile(ctx))
    phrase_set = svc.get_minus_phrases(campaign_id, nm_id)

    if not phrase_set.phrases:
        renderer.success('No minus phrases set.')
        return

    data = asdict(phrase_set)
    headers = ['Campaign ID', 'NM ID', 'Phrases']
    renderer.display(data, headers=headers, title='Minus Phrases')


@minus_app.command('set')
def minus_set(
        ctx: typer.Context,
        campaign_id: int = _CAMPAIGN_OPT,
        nm_id: int = _NM_OPT,
        phrases: str = typer.Option(
            ..., '--phrases', '-p',
            help='Comma-separated minus phrases',
        ),
        dry_run: bool = _DRY_RUN_OPT,
        yes: bool = _YES_OPT,
) -> None:
    """Set minus phrases for a campaign/product."""
    from wb.services._factory import create_cluster_service

    renderer = _get_renderer(ctx)
    phrase_list = [p.strip() for p in phrases.split(',') if p.strip()]

    if not phrase_list:
        renderer.error('At least one phrase is required. Use "minus clear" to remove all.')
        raise typer.Exit(2)

    action = (
        f'set {len(phrase_list)} minus phrase(s) for '
        f'campaign {campaign_id} nm {nm_id}'
    )
    _confirm_or_abort(renderer, action, yes or dry_run)

    svc = create_cluster_service(_get_profile(ctx))
    result = svc.set_minus_phrases(
        campaign_id, nm_id, phrase_list, dry_run=dry_run,
    )

    if not dry_run:
        _log_mutation(_get_profile(ctx), 'cluster minus set', result)

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')


@minus_app.command('clear')
def minus_clear(
        ctx: typer.Context,
        campaign_id: int = _CAMPAIGN_OPT,
        nm_id: int = _NM_OPT,
        dry_run: bool = _DRY_RUN_OPT,
        yes: bool = _YES_OPT,
) -> None:
    """Clear all minus phrases for a campaign/product."""
    from wb.services._factory import create_cluster_service

    renderer = _get_renderer(ctx)
    action = f'clear all minus phrases for campaign {campaign_id} nm {nm_id}'
    _confirm_or_abort(renderer, action, yes or dry_run)

    svc = create_cluster_service(_get_profile(ctx))
    result = svc.clear_minus_phrases(
        campaign_id, nm_id, dry_run=dry_run,
    )

    if not dry_run:
        _log_mutation(_get_profile(ctx), 'cluster minus clear', result)

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')


# ── Private helpers ──────────────────────────────────────────────────


def _parse_bid_file(
        renderer: OutputRenderer, file: Path,
) -> list[ClusterBidMutation]:
    """Parse a JSON file into a list of ClusterBidMutation objects.

    Args:
        renderer: Output renderer for error messages.
        file: Path to the JSON bid file.

    Returns:
        Parsed list of ClusterBidMutation objects.

    Raises:
        typer.Exit: If the file cannot be parsed.
    """
    try:
        raw = json.loads(file.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        renderer.error(f'Failed to read bid file: {exc}')
        raise typer.Exit(2)

    if not isinstance(raw, list):
        renderer.error('Bid file must contain a JSON array')
        raise typer.Exit(2)

    try:
        return [
            ClusterBidMutation(
                nm_id=item['nm_id'],
                norm_query=item['norm_query'],
                bid=item['bid'],
            )
            for item in raw
        ]
    except (KeyError, TypeError) as exc:
        renderer.error(f'Invalid bid entry: {exc}')
        raise typer.Exit(2)
