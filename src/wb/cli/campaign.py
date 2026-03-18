"""CLI commands for campaign management."""

from __future__ import annotations

from dataclasses import asdict

import typer

from wb.core.output import OutputRenderer
from wb.domain.enums import CampaignStatus, CampaignType, OutputFormat, VerbosityLevel

campaign_app = typer.Typer(
    help='Campaign management',
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

    renderer = _get_renderer(ctx)
    svc = create_campaign_service(_get_profile(ctx))
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

    renderer = _get_renderer(ctx)
    svc = create_campaign_service(_get_profile(ctx))
    campaign = svc.get_campaign(campaign_id)

    data = asdict(campaign)
    headers = ['Field', 'Value']
    rows = [
        ['ID', str(campaign.campaign_id)],
        ['Name', campaign.name],
        ['Status', campaign.status.name],
        ['Type', campaign.campaign_type.name],
        ['Payment', campaign.payment_type.value],
        ['Daily Budget', str(campaign.daily_budget)],
        ['Created', campaign.create_time or ''],
        ['Started', campaign.start_time or ''],
        ['Ended', campaign.end_time or ''],
    ]
    renderer.display(data, headers=headers, title=f'Campaign {campaign_id}')


@campaign_app.command('eligible-subjects')
def campaign_eligible_subjects(ctx: typer.Context) -> None:
    """List subjects eligible for campaign creation."""
    from wb.services._factory import create_campaign_service

    renderer = _get_renderer(ctx)
    svc = create_campaign_service(_get_profile(ctx))
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

    renderer = _get_renderer(ctx)
    svc = create_campaign_service(_get_profile(ctx))
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
