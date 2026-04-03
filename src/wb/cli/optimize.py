"""CLI commands for optimization workflows."""

from __future__ import annotations

from dataclasses import asdict

import typer

from wb.core.output import OutputRenderer
from wb.domain.enums import OutputFormat, VerbosityLevel

optimize_app = typer.Typer(
    help='Optimization workflows (recommendation-first)',
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


def _confirm_apply(renderer: OutputRenderer, count: int, yes: bool) -> None:
    """Prompt for apply confirmation unless --yes is set.

    Args:
        renderer: Current output renderer.
        count: Number of decisions to apply.
        yes: Skip prompt if True.
    """
    if yes or renderer.is_json:
        return
    confirmed = typer.confirm(
        f'Apply {count} optimization decision(s)?', default=False,
    )
    if not confirmed:
        raise typer.Abort()


def _render_decisions(renderer: OutputRenderer, decisions, title: str) -> None:
    """Render a list of optimization decisions.

    Args:
        renderer: Output renderer.
        decisions: List of OptimizationDecision objects.
        title: Table title.
    """
    if not decisions:
        renderer.success('No optimization actions recommended.')
        return

    data = [asdict(d) for d in decisions]
    headers = [
        'Action', 'Target', 'ID', 'Current', 'Proposed',
        'Confidence', 'Reason',
    ]
    renderer.display(data, headers=headers, title=title)


def _render_results(renderer: OutputRenderer, results) -> None:
    """Render apply results.

    Args:
        renderer: Output renderer.
        results: List of MutationResult objects.
    """
    if not results:
        renderer.success('No mutations applied.')
        return

    success_count = sum(1 for r in results if r.success)
    data = [asdict(r) for r in results]
    renderer.display(data, headers=[], title='Applied Results')
    renderer.success(f'Applied {success_count}/{len(results)} decision(s)')


_CAMPAIGN_OPT = typer.Option(..., '--campaign', '-c', help='Campaign ID')
_NM_OPT = typer.Option(..., '--nm', '-n', help='Product NM ID')
_FROM_OPT = typer.Option(..., '--from', help='Start date (YYYY-MM-DD)')
_TO_OPT = typer.Option(..., '--to', help='End date (YYYY-MM-DD)')
_APPLY_OPT = typer.Option(False, '--apply', help='Apply recommended changes')
_YES_OPT = typer.Option(False, '--yes', '-y', help='Skip confirmation')
_DRY_RUN_OPT = typer.Option(False, '--dry-run', help='Simulate apply without executing')


@optimize_app.command('plan')
def optimize_plan(
        ctx: typer.Context,
        campaign_id: int = _CAMPAIGN_OPT,
        nm_id: int = _NM_OPT,
        date_from: str = _FROM_OPT,
        date_to: str = _TO_OPT,
) -> None:
    """Show full optimization plan for a campaign (read-only)."""
    from wb.services._factory import create_optimizer_service

    renderer = _get_renderer(ctx)
    svc = create_optimizer_service(_get_profile(ctx))
    decisions = svc.plan_all(campaign_id, nm_id, date_from, date_to)
    _render_decisions(renderer, decisions, 'Optimization Plan')


@optimize_app.command('run')
def optimize_run(
        ctx: typer.Context,
        campaign_id: int = _CAMPAIGN_OPT,
        nm_id: int = _NM_OPT,
        date_from: str = _FROM_OPT,
        date_to: str = _TO_OPT,
        apply: bool = _APPLY_OPT,
        yes: bool = _YES_OPT,
        dry_run: bool = _DRY_RUN_OPT,
) -> None:
    """Generate and optionally apply full optimization plan."""
    from wb.services._factory import create_optimizer_service

    renderer = _get_renderer(ctx)
    svc = create_optimizer_service(_get_profile(ctx))
    decisions = svc.plan_all(campaign_id, nm_id, date_from, date_to)
    _render_decisions(renderer, decisions, 'Optimization Plan')

    if not apply or not decisions:
        return

    _confirm_apply(renderer, len(decisions), yes or dry_run)
    results = svc.apply_all(
        campaign_id, nm_id, date_from, date_to, dry_run=dry_run,
    )
    prefix = '[DRY-RUN] ' if dry_run else ''
    _render_results(renderer, results)
    if dry_run:
        renderer.success(f'{prefix}No mutations executed')


@optimize_app.command('clusters')
def optimize_clusters(
        ctx: typer.Context,
        campaign_id: int = _CAMPAIGN_OPT,
        nm_id: int = _NM_OPT,
        date_from: str = _FROM_OPT,
        date_to: str = _TO_OPT,
        apply: bool = _APPLY_OPT,
        yes: bool = _YES_OPT,
        dry_run: bool = _DRY_RUN_OPT,
) -> None:
    """Optimize search cluster bids for a campaign/product."""
    from wb.services._factory import create_optimizer_service

    renderer = _get_renderer(ctx)
    svc = create_optimizer_service(_get_profile(ctx))
    decisions = svc.plan_clusters(campaign_id, nm_id, date_from, date_to)
    _render_decisions(renderer, decisions, 'Cluster Optimization')

    if not apply or not decisions:
        return

    _confirm_apply(renderer, len(decisions), yes or dry_run)
    results = svc.apply_clusters(
        campaign_id, nm_id, date_from, date_to, dry_run=dry_run,
    )
    _render_results(renderer, results)


@optimize_app.command('budget')
def optimize_budget(
        ctx: typer.Context,
        campaign_id: int = _CAMPAIGN_OPT,
        apply: bool = _APPLY_OPT,
        yes: bool = _YES_OPT,
        dry_run: bool = _DRY_RUN_OPT,
) -> None:
    """Optimize campaign budget allocation."""
    from wb.services._factory import create_optimizer_service

    renderer = _get_renderer(ctx)
    svc = create_optimizer_service(_get_profile(ctx))
    decisions = svc.plan_budget(campaign_id)
    _render_decisions(renderer, decisions, 'Budget Optimization')

    if not apply or not decisions:
        return

    _confirm_apply(renderer, len(decisions), yes or dry_run)
    results = svc.apply_budget(campaign_id, dry_run=dry_run)
    _render_results(renderer, results)


@optimize_app.command('negatives')
def optimize_negatives(
        ctx: typer.Context,
        campaign_id: int = _CAMPAIGN_OPT,
        nm_id: int = _NM_OPT,
        date_from: str = _FROM_OPT,
        date_to: str = _TO_OPT,
        apply: bool = _APPLY_OPT,
        yes: bool = _YES_OPT,
        dry_run: bool = _DRY_RUN_OPT,
) -> None:
    """Recommend minus phrases based on cluster waste."""
    from wb.services._factory import create_optimizer_service

    renderer = _get_renderer(ctx)
    svc = create_optimizer_service(_get_profile(ctx))
    decisions = svc.plan_negatives(campaign_id, nm_id, date_from, date_to)
    _render_decisions(renderer, decisions, 'Negative Phrase Recommendations')

    if not apply or not decisions:
        return

    _confirm_apply(renderer, len(decisions), yes or dry_run)
    results = svc.apply_negatives(
        campaign_id, nm_id, date_from, date_to, dry_run=dry_run,
    )
    _render_results(renderer, results)


@optimize_app.command('portfolio')
def optimize_portfolio(
        ctx: typer.Context,
        campaign_id: int = _CAMPAIGN_OPT,
        date_from: str = _FROM_OPT,
        date_to: str = _TO_OPT,
        apply: bool = _APPLY_OPT,
        yes: bool = _YES_OPT,
        dry_run: bool = _DRY_RUN_OPT,
) -> None:
    """Optimize product mix in a campaign."""
    from wb.services._factory import create_optimizer_service

    renderer = _get_renderer(ctx)
    svc = create_optimizer_service(_get_profile(ctx))
    decisions = svc.plan_portfolio(campaign_id, date_from, date_to)
    _render_decisions(renderer, decisions, 'Portfolio Optimization')

    if not apply or not decisions:
        return

    _confirm_apply(renderer, len(decisions), yes or dry_run)
    results = [
        svc._apply_decision(d, campaign_id, dry_run)
        for d in decisions
    ]
    _render_results(renderer, results)
