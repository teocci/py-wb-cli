"""Shared helper functions for CLI command modules.

Centralizes common patterns that were previously duplicated
across every CLI module: renderer creation, profile extraction,
and confirmation prompts.
"""

from __future__ import annotations

import typer

from wb.core.output import OutputRenderer
from wb.domain.enums import OutputFormat, VerbosityLevel

__all__ = [
    'get_renderer',
    'get_profile',
    'resolve_profile_name',
    'get_fields',
    'confirm_or_abort',
]


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
    return OutputRenderer(fmt, verb, compact=obj.get('compact', False))


def get_profile(ctx: typer.Context) -> str | None:
    """Extract profile name from CLI context.

    Args:
        ctx: Typer context carrying global options.

    Returns:
        Profile name or None.
    """
    return (ctx.obj or {}).get('profile')


def resolve_profile_name(ctx: typer.Context) -> str:
    """Return the effective profile name: --profile flag, or active from ProfileStore.

    Used by CLI commands that need a concrete profile name for cache scoping
    or user-visible prompts. Mirrors ProfileStore's own active-profile fallback
    so commands never invent the literal 'default'.

    Args:
        ctx: Typer context carrying global options.

    Returns:
        Profile name from --profile flag, or the active profile name from
        ~/.wb-cli/profiles.json.
    """
    explicit = get_profile(ctx)
    if explicit:
        return explicit
    from wb.auth.profiles import ProfileStore
    from wb.services._factory import _Container
    return ProfileStore(_Container.settings().config_dir).active_profile_name


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
