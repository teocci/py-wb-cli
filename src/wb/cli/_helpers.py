"""Shared helper functions for CLI command modules.

Centralizes common patterns that were previously duplicated
across every CLI module: renderer creation, profile extraction,
and confirmation prompts.
"""

from __future__ import annotations

import typer

from wb.core.output import OutputRenderer
from wb.domain.enums import OutputFormat, VerbosityLevel

__all__ = ['get_renderer', 'get_profile', 'get_fields', 'confirm_or_abort']


def get_renderer(ctx: typer.Context) -> OutputRenderer:
    """Build an OutputRenderer from global CLI flags.

    Args:
        ctx: Typer context carrying global options.

    Returns:
        Configured OutputRenderer instance.
    """
    obj = ctx.obj or {}
    fmt = OutputFormat.JSON if obj.get('json_output') else OutputFormat.TABLE
    verb = VerbosityLevel.QUIET if obj.get('quiet') else VerbosityLevel.NORMAL
    if obj.get('verbose'):
        verb = VerbosityLevel.VERBOSE
    return OutputRenderer(fmt, verb)


def get_profile(ctx: typer.Context) -> str | None:
    """Extract profile name from CLI context.

    Args:
        ctx: Typer context carrying global options.

    Returns:
        Profile name or None.
    """
    return (ctx.obj or {}).get('profile')


def get_fields(ctx: typer.Context) -> list[str] | None:
    """Extract field filter list from CLI context.

    Args:
        ctx: Typer context carrying global options.

    Returns:
        List of field names to include, or None (include all).
    """
    return (ctx.obj or {}).get('fields')


def confirm_or_abort(
        renderer: OutputRenderer,
        action: str,
        yes: bool,
) -> None:
    """Prompt for confirmation unless --yes is set or JSON mode is active.

    In JSON mode, prompts are always skipped to avoid blocking
    AI agents that cannot provide stdin input.

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
