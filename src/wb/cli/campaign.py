"""CLI commands for campaign management."""

from __future__ import annotations

from dataclasses import asdict

import typer

from wb.cli._helpers import confirm_or_abort, get_fields, get_profile, get_renderer
from wb.core.constants import ExitCode
from wb.core.output import OutputRenderer
from wb.domain.enums import CampaignStatus, CampaignType
from wb.domain.models import CampaignCreate, MutationResult, PlacementConfig

campaign_app = typer.Typer(
    help='Campaign management',
    no_args_is_help=True,
)


def _parse_ids_arg(
        renderer: OutputRenderer,
        single: int | None,
        multi: str | None,
) -> list[int]:
    """Parse a single positional ID or --ids comma-separated string into a list.

    Args:
        renderer: For emitting validation errors.
        single: Optional single positional campaign_id argument.
        multi: Optional comma-separated --ids string.

    Returns:
        Non-empty list of campaign IDs.
    """
    if single is None and multi is None:
        renderer.error('Provide a campaign ID or --ids')
        raise typer.Exit(ExitCode.VALIDATION_ERROR)
    if single is not None and multi is not None:
        renderer.error('Use a positional campaign ID or --ids, not both')
        raise typer.Exit(ExitCode.VALIDATION_ERROR)
    if single is not None:
        return [single]
    try:
        return [int(x.strip()) for x in multi.split(',') if x.strip()]  # type: ignore[union-attr]
    except ValueError:
        raise typer.BadParameter('--ids must be comma-separated integers')


def _render_batch_results(
        ctx: typer.Context,
        renderer: OutputRenderer,
        results: list[MutationResult],
        command: str,
        dry_run: bool,
) -> None:
    """Render a list of MutationResults and log successful ones.

    Args:
        ctx: Typer context.
        renderer: Output renderer.
        results: List of results to render.
        command: CLI command name for audit logging.
        dry_run: Whether this was a dry run.
    """
    if not dry_run:
        for r in results:
            if r.success:
                _log_mutation(get_profile(ctx), command, r)
    if renderer.is_json:
        from dataclasses import asdict as _asdict
        renderer.display([_asdict(r) for r in results], fields=get_fields(ctx))
        return
    headers = ['Target ID', 'Success', 'Message']
    rows = [[r.target_id, str(r.success), r.message] for r in results]
    prefix = '[DRY-RUN] ' if dry_run else ''
    ok = sum(1 for r in results if r.success)
    renderer.display(rows, headers=headers, title=f'{prefix}{command}', fields=get_fields(ctx))
    renderer.success(f'{prefix}{ok}/{len(results)} succeeded')


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
    renderer.display(data, headers=headers, title='Campaigns', fields=get_fields(ctx))


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
    renderer.display(data, headers=headers, title=f'Campaign {campaign_id}', fields=get_fields(ctx))


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
    renderer.display(subjects, headers=headers, title='Eligible Subjects', fields=get_fields(ctx))


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
    renderer.display(data, headers=headers, title='Eligible Items', fields=get_fields(ctx))



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
        campaign_id: int | None = typer.Argument(None, help='Single campaign ID'),
        ids: str | None = typer.Option(None, '--ids', help='Comma-separated campaign IDs'),
        dry_run: bool = typer.Option(False, '--dry-run', help='Plan without executing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Start one or more campaigns."""
    from wb.services._factory import create_campaign_service

    renderer = get_renderer(ctx)
    campaign_ids = _parse_ids_arg(renderer, campaign_id, ids)
    action = f'start {len(campaign_ids)} campaign(s): {campaign_ids}'
    confirm_or_abort(renderer, action, yes or dry_run)

    svc = create_campaign_service(get_profile(ctx))
    results = svc.start_campaigns(campaign_ids, dry_run=dry_run)
    _render_batch_results(ctx, renderer, results, 'campaign start', dry_run)


@campaign_app.command('pause')
def campaign_pause(
        ctx: typer.Context,
        campaign_id: int | None = typer.Argument(None, help='Single campaign ID'),
        ids: str | None = typer.Option(None, '--ids', help='Comma-separated campaign IDs'),
        dry_run: bool = typer.Option(False, '--dry-run', help='Plan without executing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Pause one or more running campaigns."""
    from wb.services._factory import create_campaign_service

    renderer = get_renderer(ctx)
    campaign_ids = _parse_ids_arg(renderer, campaign_id, ids)
    action = f'pause {len(campaign_ids)} campaign(s): {campaign_ids}'
    confirm_or_abort(renderer, action, yes or dry_run)

    svc = create_campaign_service(get_profile(ctx))
    results = svc.pause_campaigns(campaign_ids, dry_run=dry_run)
    _render_batch_results(ctx, renderer, results, 'campaign pause', dry_run)


@campaign_app.command('stop')
def campaign_stop(
        ctx: typer.Context,
        campaign_id: int | None = typer.Argument(None, help='Single campaign ID'),
        ids: str | None = typer.Option(None, '--ids', help='Comma-separated campaign IDs'),
        dry_run: bool = typer.Option(False, '--dry-run', help='Plan without executing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Stop (archive) one or more campaigns."""
    from wb.services._factory import create_campaign_service

    renderer = get_renderer(ctx)
    campaign_ids = _parse_ids_arg(renderer, campaign_id, ids)
    action = f'stop {len(campaign_ids)} campaign(s): {campaign_ids}'
    confirm_or_abort(renderer, action, yes or dry_run)

    svc = create_campaign_service(get_profile(ctx))
    results = svc.stop_campaigns(campaign_ids, dry_run=dry_run)
    _render_batch_results(ctx, renderer, results, 'campaign stop', dry_run)


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
        campaign_id: int | None = typer.Argument(None, help='Single campaign ID'),
        ids: str | None = typer.Option(None, '--ids', help='Comma-separated campaign IDs'),
        dry_run: bool = typer.Option(False, '--dry-run', help='Plan without executing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Delete one or more campaigns."""
    from wb.services._factory import create_campaign_service

    renderer = get_renderer(ctx)
    campaign_ids = _parse_ids_arg(renderer, campaign_id, ids)
    action = f'delete {len(campaign_ids)} campaign(s): {campaign_ids}'
    confirm_or_abort(renderer, action, yes or dry_run)

    svc = create_campaign_service(get_profile(ctx))
    results = svc.delete_campaigns(campaign_ids, dry_run=dry_run)
    _render_batch_results(ctx, renderer, results, 'campaign delete', dry_run)


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


@campaign_app.command('overview')
def campaign_overview(
        ctx: typer.Context,
        campaign_id: int = typer.Argument(..., help='Campaign ID'),
        days: int = typer.Option(
            7, '--days', help='Number of days to look back for stats',
        ),
) -> None:
    """Composite campaign snapshot in one call.

    Returns campaign details, budget, stats for the given date range,
    per-NM breakdown, and active/total cluster counts.
    Budget and stats are best-effort: if unavailable those fields show zero.
    """
    import json
    from dataclasses import asdict as _asdict
    from datetime import date as _date, timedelta
    from wb.services._factory import create_product_service

    renderer = get_renderer(ctx)
    profile = get_profile(ctx)
    date_to = _date.today().strftime('%Y-%m-%d')
    date_from = (_date.today() - timedelta(days=days)).strftime('%Y-%m-%d')

    try:
        svc = create_product_service(profile)
    except Exception as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=ExitCode.CONFIG_ERROR) from exc

    try:
        overview = svc.get_campaign_overview(campaign_id, date_from, date_to)
    except Exception as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=ExitCode.API_ERROR) from exc

    if renderer.is_json:
        typer.echo(json.dumps(_asdict(overview), indent=2, ensure_ascii=False))
        return

    _render_campaign_overview(overview, date_from, date_to)


def _render_campaign_overview(overview, date_from: str, date_to: str) -> None:
    """Render CampaignOverview as Rich tables."""
    from rich.console import Console
    from rich.table import Table

    console = Console()

    header = Table(
        title=f'Campaign {overview.campaign_id} Overview ({date_from} \u2192 {date_to})',
        show_header=False, show_lines=False, box=None,
    )
    header.add_column('Field', style='dim', min_width=16)
    header.add_column('Value', style='cyan')
    header.add_row('Name', overview.name)
    header.add_row('Status', overview.status.name)
    header.add_row('Type', overview.campaign_type.name)
    header.add_row('NM IDs', ', '.join(str(n) for n in overview.nm_ids) or 'none')
    header.add_row('Budget (total)', f'{overview.total_budget:,} kopecks')
    header.add_row('Budget (cash)', f'{overview.cash:,} kopecks')
    console.print(header)

    stats = Table(title='Ad Stats', show_lines=False)
    stats.add_column('Views', justify='right')
    stats.add_column('Clicks', justify='right')
    stats.add_column('CTR', justify='right')
    stats.add_column('Orders', justify='right')
    stats.add_column('Spend (\u20bd)', justify='right', style='magenta')
    stats.add_column('CPC', justify='right')
    stats.add_column('Clusters', justify='right')
    stats.add_row(
        str(overview.views),
        str(overview.clicks),
        f'{overview.ctr:.2f}%',
        str(overview.orders),
        f'{overview.spend:,.2f}',
        f'{overview.cpc:,.2f}',
        f'{overview.active_cluster_count}/{overview.cluster_count}',
    )
    console.print(stats)

    if not overview.nm_stats:
        return

    nm_table = Table(title='Per-Product Breakdown', show_lines=False)
    nm_table.add_column('NM ID', style='cyan', justify='right')
    nm_table.add_column('Views', justify='right')
    nm_table.add_column('Clicks', justify='right')
    nm_table.add_column('Orders', justify='right')
    nm_table.add_column('Spend (\u20bd)', justify='right', style='magenta')
    nm_table.add_column('Avg Pos', justify='right')
    for nm in overview.nm_stats:
        nm_table.add_row(
            str(nm.nm_id),
            str(nm.views),
            str(nm.clicks),
            str(nm.orders),
            f'{nm.spend:,.2f}',
            f'{nm.avg_position:.1f}' if nm.avg_position else '\u2014',
        )
    console.print(nm_table)
