"""CLI commands for campaign management."""

from __future__ import annotations

from dataclasses import asdict

import typer

from wb.cli._helpers import confirm_or_abort, get_profile, get_renderer
from wb.domain.enums import CampaignStatus, CampaignType
from wb.domain.models import CampaignCreate, PlacementConfig

campaign_app = typer.Typer(
    help='Campaign management',
    no_args_is_help=True,
)


def _parse_status(value: str | None) -> CampaignStatus | None:
    """Parse status string to enum, or None."""
    if value is None:
        return None
    mapping = {s.name.lower(): s for s in CampaignStatus}
    key = value.strip().lower()
    if key not in mapping:
        valid = ', '.join(mapping.keys())
        raise typer.BadParameter(f'Invalid status {value!r}. Choose from: {valid}')
    return mapping[key]


def _parse_type(value: str | None) -> CampaignType | None:
    """Parse type string to enum, or None."""
    if value is None:
        return None
    mapping = {t.name.lower(): t for t in CampaignType}
    key = value.strip().lower()
    if key not in mapping:
        valid = ', '.join(mapping.keys())
        raise typer.BadParameter(f'Invalid type {value!r}. Choose from: {valid}')
    return mapping[key]


@campaign_app.command('list')
def campaign_list(
        ctx: typer.Context,
        status: str | None = typer.Option(
            None, '--status', '-s',
            help='Filter by status (ready, running, paused, archived)',
        ),
        type_: str | None = typer.Option(
            None, '--type', '-t',
            help='Filter by type (auto, search_plus_catalog)',
        ),
) -> None:
    """List all campaigns."""
    from wb.services._factory import create_campaign_service

    renderer = get_renderer(ctx)
    svc = create_campaign_service(get_profile(ctx))
    campaigns = svc.list_campaigns(
        status=_parse_status(status),
        type_=_parse_type(type_),
    )

    if not campaigns:
        renderer.success('No campaigns found.')
        return

    data = [asdict(c) for c in campaigns]
    headers = ['ID', 'Name', 'Status', 'Type', 'Daily Budget', 'Created']
    rows = [
        [
            str(c.campaign_id),
            c.name,
            c.status.name,
            c.campaign_type.name,
            str(c.daily_budget),
            (c.create_time or '')[:10],
        ]
        for c in campaigns
    ]
    renderer.display(data, headers=headers, title='Campaigns')


@campaign_app.command('get')
def campaign_get(
        ctx: typer.Context,
        campaign_id: int = typer.Argument(..., help='Campaign ID'),
) -> None:
    """Get details for a single campaign."""
    from wb.services._factory import create_campaign_service

    renderer = get_renderer(ctx)
    svc = create_campaign_service(get_profile(ctx))
    campaign = svc.get_campaign(campaign_id)

    data = asdict(campaign)
    headers = ['Field', 'Value']
    nm_ids_str = ', '.join(str(n) for n in campaign.nm_ids) or 'none'
    rows = [
        ['ID', str(campaign.campaign_id)],
        ['Name', campaign.name],
        ['Status', campaign.status.name],
        ['Type', campaign.campaign_type.name],
        ['Payment', campaign.payment_type.value],
        ['Daily Budget', str(campaign.daily_budget)],
        ['NM IDs', nm_ids_str],
        ['Created', campaign.create_time or ''],
        ['Started', campaign.start_time or ''],
        ['Updated', campaign.updated_time or ''],
    ]
    renderer.display(data, headers=headers, title=f'Campaign {campaign_id}')


@campaign_app.command('eligible-subjects')
def campaign_eligible_subjects(ctx: typer.Context) -> None:
    """List subjects eligible for campaign creation."""
    from wb.services._factory import create_campaign_service

    renderer = get_renderer(ctx)
    svc = create_campaign_service(get_profile(ctx))
    subjects = svc.get_eligible_subjects()

    if not subjects:
        renderer.success('No eligible subjects found.')
        return

    headers = ['Subject ID', 'Subject Name']
    rows = [
        [str(s.get('id', '')), s.get('name', '')]
        for s in subjects
    ]
    renderer.display(subjects, headers=headers, title='Eligible Subjects')


@campaign_app.command('eligible-items')
def campaign_eligible_items(
        ctx: typer.Context,
        subject_id: int = typer.Option(
            ..., '--subject', help='Subject ID to list items for',
        ),
) -> None:
    """List product cards eligible for a subject."""
    from wb.services._factory import create_campaign_service

    renderer = get_renderer(ctx)
    svc = create_campaign_service(get_profile(ctx))
    items = svc.get_eligible_items(subject_id)

    if not items:
        renderer.success('No eligible items found.')
        return

    data = [asdict(item) for item in items]
    headers = ['NM ID', 'Name', 'Subject ID', 'Subject Name']
    rows = [
        [
            str(item.nm_id),
            item.name,
            str(item.subject_id),
            item.subject_name,
        ]
        for item in items
    ]
    renderer.display(data, headers=headers, title='Eligible Items')



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


@campaign_app.command('create')
def campaign_create(
        ctx: typer.Context,
        name: str = typer.Option(..., '--name', '-n', help='Campaign name'),
        nms: str = typer.Option(
            ..., '--nms', help='Comma-separated product NM IDs',
        ),
        bid_type: str = typer.Option(
            'manual', '--bid-type',
            help='Bid type (manual, unified)',
        ),
        placements: str = typer.Option(
            'search', '--placements',
            help='Comma-separated placement types (search, recommendations)',
        ),
        dry_run: bool = typer.Option(False, '--dry-run', help='Plan without executing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Create a new campaign."""
    from wb.services._factory import create_campaign_service

    renderer = get_renderer(ctx)

    try:
        nm_list = [int(x.strip()) for x in nms.split(',') if x.strip()]
    except ValueError:
        raise typer.BadParameter('--nms must be comma-separated integers')

    placement_list = [p.strip() for p in placements.split(',') if p.strip()]

    params = CampaignCreate(
        name=name,
        nm_ids=nm_list,
        bid_type=bid_type,
        placement_types=placement_list,
    )
    action = f'create campaign "{name}" bid_type={bid_type}'
    confirm_or_abort(renderer, action, yes or dry_run)

    svc = create_campaign_service(get_profile(ctx))
    result = svc.create_campaign(params, dry_run=dry_run)

    if not dry_run:
        _log_mutation(get_profile(ctx), 'campaign create', result)

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')


@campaign_app.command('clone')
def campaign_clone(
        ctx: typer.Context,
        campaign_id: int = typer.Argument(..., help='Campaign ID to clone'),
        name: str | None = typer.Option(None, '--name', '-n', help='New campaign name (default: original + " (copy)")'),
        nms: str | None = typer.Option(None, '--nms', help='Comma-separated product NM IDs (required)'),
        dry_run: bool = typer.Option(False, '--dry-run', help='Plan without executing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Clone an existing campaign."""
    from wb.services._factory import create_campaign_service

    renderer = get_renderer(ctx)

    if not nms:
        raise typer.BadParameter('--nms is required for clone (WB API does not return current items)')

    try:
        nm_list = [int(x.strip()) for x in nms.split(',') if x.strip()]
    except ValueError:
        raise typer.BadParameter('--nms must be comma-separated integers')

    svc = create_campaign_service(get_profile(ctx))
    source = svc.get_campaign(campaign_id)

    new_name = name or f'{source.name} (copy)'
    action = f'clone campaign {campaign_id} to "{new_name}" with {len(nm_list)} item(s)'
    confirm_or_abort(renderer, action, yes or dry_run)

    params = CampaignCreate(
        name=new_name,
        nm_ids=nm_list,
        bid_type=source.bid_type,
        placement_types=['search'],
    )
    result = svc.create_campaign(params, dry_run=dry_run)

    if not dry_run:
        _log_mutation(get_profile(ctx), 'campaign clone', result)

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')


@campaign_app.command('start')
def campaign_start(
        ctx: typer.Context,
        campaign_id: int = typer.Argument(..., help='Campaign ID'),
        dry_run: bool = typer.Option(False, '--dry-run', help='Plan without executing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Start a campaign."""
    from wb.services._factory import create_campaign_service

    renderer = get_renderer(ctx)
    confirm_or_abort(renderer, f'start campaign {campaign_id}', yes or dry_run)

    svc = create_campaign_service(get_profile(ctx))
    result = svc.start_campaign(campaign_id, dry_run=dry_run)

    if not dry_run:
        _log_mutation(get_profile(ctx), 'campaign start', result)

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')


@campaign_app.command('pause')
def campaign_pause(
        ctx: typer.Context,
        campaign_id: int = typer.Argument(..., help='Campaign ID'),
        dry_run: bool = typer.Option(False, '--dry-run', help='Plan without executing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Pause a running campaign."""
    from wb.services._factory import create_campaign_service

    renderer = get_renderer(ctx)
    confirm_or_abort(renderer, f'pause campaign {campaign_id}', yes or dry_run)

    svc = create_campaign_service(get_profile(ctx))
    result = svc.pause_campaign(campaign_id, dry_run=dry_run)

    if not dry_run:
        _log_mutation(get_profile(ctx), 'campaign pause', result)

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')


@campaign_app.command('stop')
def campaign_stop(
        ctx: typer.Context,
        campaign_id: int = typer.Argument(..., help='Campaign ID'),
        dry_run: bool = typer.Option(False, '--dry-run', help='Plan without executing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Stop (archive) a campaign."""
    from wb.services._factory import create_campaign_service

    renderer = get_renderer(ctx)
    confirm_or_abort(renderer, f'stop campaign {campaign_id}', yes or dry_run)

    svc = create_campaign_service(get_profile(ctx))
    result = svc.stop_campaign(campaign_id, dry_run=dry_run)

    if not dry_run:
        _log_mutation(get_profile(ctx), 'campaign stop', result)

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')


@campaign_app.command('rename')
def campaign_rename(
        ctx: typer.Context,
        campaign_id: int = typer.Argument(..., help='Campaign ID'),
        name: str = typer.Option(..., '--name', '-n', help='New campaign name'),
        dry_run: bool = typer.Option(False, '--dry-run', help='Plan without executing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Rename a campaign."""
    from wb.services._factory import create_campaign_service

    renderer = get_renderer(ctx)
    action = f'rename campaign {campaign_id} to "{name}"'
    confirm_or_abort(renderer, action, yes or dry_run)

    svc = create_campaign_service(get_profile(ctx))
    result = svc.rename_campaign(campaign_id, name, dry_run=dry_run)

    if not dry_run:
        _log_mutation(get_profile(ctx), 'campaign rename', result)

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')


@campaign_app.command('delete')
def campaign_delete(
        ctx: typer.Context,
        campaign_id: int = typer.Argument(..., help='Campaign ID'),
        dry_run: bool = typer.Option(False, '--dry-run', help='Plan without executing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Delete a campaign."""
    from wb.services._factory import create_campaign_service

    renderer = get_renderer(ctx)
    confirm_or_abort(renderer, f'delete campaign {campaign_id}', yes or dry_run)

    svc = create_campaign_service(get_profile(ctx))
    result = svc.delete_campaign(campaign_id, dry_run=dry_run)

    if not dry_run:
        _log_mutation(get_profile(ctx), 'campaign delete', result)

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')


@campaign_app.command('add-items')
def campaign_add_items(
        ctx: typer.Context,
        campaign_id: int = typer.Argument(..., help='Campaign ID'),
        nms: str = typer.Option(
            ..., '--nms', help='Comma-separated product NM IDs',
        ),
        dry_run: bool = typer.Option(False, '--dry-run', help='Plan without executing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Add product items to a campaign."""
    from wb.services._factory import create_campaign_service

    renderer = get_renderer(ctx)
    try:
        nm_list = [int(x.strip()) for x in nms.split(',') if x.strip()]
    except ValueError:
        raise typer.BadParameter('--nms must be comma-separated integers')

    action = f'add {len(nm_list)} item(s) to campaign {campaign_id}'
    confirm_or_abort(renderer, action, yes or dry_run)

    svc = create_campaign_service(get_profile(ctx))
    result = svc.add_items(campaign_id, nm_list, dry_run=dry_run)

    if not dry_run:
        _log_mutation(get_profile(ctx), 'campaign add-items', result)

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')


@campaign_app.command('remove-items')
def campaign_remove_items(
        ctx: typer.Context,
        campaign_id: int = typer.Argument(..., help='Campaign ID'),
        nms: str = typer.Option(
            ..., '--nms', help='Comma-separated product NM IDs',
        ),
        dry_run: bool = typer.Option(False, '--dry-run', help='Plan without executing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Remove product items from a campaign."""
    from wb.services._factory import create_campaign_service

    renderer = get_renderer(ctx)
    try:
        nm_list = [int(x.strip()) for x in nms.split(',') if x.strip()]
    except ValueError:
        raise typer.BadParameter('--nms must be comma-separated integers')

    action = f'remove {len(nm_list)} item(s) from campaign {campaign_id}'
    confirm_or_abort(renderer, action, yes or dry_run)

    svc = create_campaign_service(get_profile(ctx))
    result = svc.remove_items(campaign_id, nm_list, dry_run=dry_run)

    if not dry_run:
        _log_mutation(get_profile(ctx), 'campaign remove-items', result)

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')


@campaign_app.command('set-placements')
def campaign_set_placements(
        ctx: typer.Context,
        campaign_id: int = typer.Argument(..., help='Campaign ID'),
        search: bool = typer.Option(True, '--search/--no-search', help='Enable search placement'),
        catalog: bool = typer.Option(True, '--catalog/--no-catalog', help='Enable catalog placement'),
        dry_run: bool = typer.Option(False, '--dry-run', help='Plan without executing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Set placement configuration for a campaign."""
    from wb.services._factory import create_campaign_service

    renderer = get_renderer(ctx)
    config = PlacementConfig(search_enabled=search, recommendations_enabled=catalog)
    action = (
        f'set placements for campaign {campaign_id}: '
        f'search={search}, recommendations={catalog}'
    )
    confirm_or_abort(renderer, action, yes or dry_run)

    svc = create_campaign_service(get_profile(ctx))
    result = svc.set_placements(campaign_id, config, dry_run=dry_run)

    if not dry_run:
        _log_mutation(get_profile(ctx), 'campaign set-placements', result)

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')
