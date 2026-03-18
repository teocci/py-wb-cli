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
