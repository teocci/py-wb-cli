"""CLI commands for budget and balance management."""

from __future__ import annotations

from dataclasses import asdict

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
        ['Daily', str(budget.daily)],
        ['Balance', str(budget.balance)],
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

    prefix = '[DRY-RUN] ' if result.dry_run else ''
    renderer.success(f'{prefix}{result.message}')
