"""CLI commands for budget and balance management."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

import typer

from wb.core.output import OutputRenderer
from wb.domain.enums import OutputFormat, VerbosityLevel

budget_app = typer.Typer(
    help='Budget and balance management',
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


@budget_app.command('balance')
def budget_balance(ctx: typer.Context) -> None:
    """Show account balance."""
    from wb.services._factory import create_budget_service

    renderer = _get_renderer(ctx)
    svc = create_budget_service(_get_profile(ctx))
    balance = svc.get_balance()

    data = asdict(balance)
    headers = ['Field', 'Value']
    rows = [
        ['Balance', str(balance.balance)],
        ['Net', str(balance.net)],
        ['Bonus', str(balance.bonus)],
    ]
    renderer.display(data, headers=headers, title='Account Balance')


@budget_app.command('get')
def budget_get(
        ctx: typer.Context,
        campaign_id: int = typer.Option(
            ..., '--campaign', '-c', help='Campaign ID',
        ),
) -> None:
    """Show budget for a campaign."""
    from wb.services._factory import create_budget_service

    renderer = _get_renderer(ctx)
    svc = create_budget_service(_get_profile(ctx))
    budget = svc.get_budget(campaign_id)

    data = asdict(budget)
    headers = ['Field', 'Value']
    rows = [
        ['Campaign ID', str(budget.campaign_id)],
        ['Total', str(budget.total)],
        ['Cash', str(budget.cash)],
        ['Netting', str(budget.netting)],
    ]
    renderer.display(data, headers=headers, title=f'Budget — Campaign {campaign_id}')


@budget_app.command('topup')
def budget_topup(
        ctx: typer.Context,
        campaign_id: int = typer.Option(..., '--campaign', '-c', help='Campaign ID'),
        amount: int = typer.Option(..., '--sum', '-s', help='Amount to deposit in kopecks'),
        dry_run: bool = typer.Option(False, '--dry-run', help='Plan without executing'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation'),
) -> None:
    """Deposit funds into a campaign budget."""
    from wb.services._factory import create_audit_logger, create_budget_service

    renderer = _get_renderer(ctx)
    action = f'deposit {amount} kopecks to campaign {campaign_id}'

    if not (yes or dry_run or renderer.is_json):
        confirmed = typer.confirm(f'About to: {action}. Proceed?', default=False)
        if not confirmed:
            raise typer.Abort()

    svc = create_budget_service(_get_profile(ctx))
    result = svc.topup(campaign_id, amount, dry_run=dry_run)

    if not dry_run:
        audit = create_audit_logger(_get_profile(ctx))
        audit.log(
            profile=_get_profile(ctx) or 'default',
            command='budget topup',
            target_id=result.target_id,
            payload={'action': result.action},
            result=result.message,
        )

    if not dry_run:
        _record_topup_event(
            profile=_get_profile(ctx) or 'default',
            campaign_id=campaign_id,
            amount=amount,
        )

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')


def _record_topup_event(
        profile: str,
        campaign_id: int,
        amount: int,
) -> None:
    """Persist a budget topup event to the local cache."""
    import json
    from wb.domain.cache_models import BudgetEvent
    from wb.services._factory import create_cache_store
    try:
        store = create_cache_store(profile)
        evt = BudgetEvent(
            profile=profile,
            campaign_id=campaign_id,
            event_type='topup',
            amount=amount,
            balance_after=0,
            created_at=datetime.now(timezone.utc).isoformat(),
            payload_json=json.dumps({'campaign_id': campaign_id, 'amount': amount}),
        )
        store.save_budget_event(evt)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning('Could not record budget event: %s', exc)


@budget_app.command('history')
def budget_history(
        ctx: typer.Context,
        campaign_id: int | None = typer.Option(
            None, '--campaign', '-c', help='Filter by campaign ID',
        ),
        limit: int = typer.Option(100, '--limit', '-l', help='Max events to show'),
) -> None:
    """Show recorded budget topup events from local cache."""
    from wb.services._factory import create_cache_store

    renderer = _get_renderer(ctx)
    profile = _get_profile(ctx) or 'default'
    store = create_cache_store(profile)
    events = store.list_budget_events(profile, campaign_id, limit)
    data = [asdict(e) for e in events]
    renderer.display(
        data,
        headers=['Time', 'Campaign', 'Type', 'Amount', 'Balance After'],
        title='Budget Event History',
    )
