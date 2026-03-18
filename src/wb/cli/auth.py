"""CLI commands for authentication and profile management."""

from __future__ import annotations

import typer

from wb.auth.profiles import ProfileStore
from wb.auth.token_validation import validate_promotion_token
from wb.core.config import Settings
from wb.core.exceptions import WbCliError

auth_app = typer.Typer(
    help='Authentication and profile management',
    no_args_is_help=True,
)


def _get_profile_store() -> ProfileStore:
    """Create a ProfileStore from current settings."""
    settings = Settings()
    settings.ensure_config_dir()
    return ProfileStore(settings.config_dir)


@auth_app.command('login')
def auth_login(
        ctx: typer.Context,
        profile: str = typer.Option('default', '--profile', '-p', help='Profile name'),
        category: str = typer.Option('promotion', '--category', '-c', help='Token category'),
        token: str = typer.Option(..., '--token', '-t', help='WB API token', prompt=True, hide_input=True),
        skip_validation: bool = typer.Option(False, '--skip-validation', help='Skip token validation'),
) -> None:
    """Store an API token for a profile."""
    store = _get_profile_store()

    if not skip_validation and category == 'promotion':
        typer.echo('Validating token...')
        try:
            validate_promotion_token(token)
            typer.secho('Token validated successfully.', fg=typer.colors.GREEN)
        except WbCliError as exc:
            typer.secho(f'Validation failed: {exc}', fg=typer.colors.RED, err=True)
            raise typer.Abort() from exc

    store.save_token(profile, category, token)
    store.set_active(profile)
    typer.secho(f'Token saved to profile {profile!r} [{category}].', fg=typer.colors.GREEN)


@auth_app.command('logout')
def auth_logout(
        profile: str = typer.Option(None, '--profile', '-p', help='Profile to remove'),
) -> None:
    """Remove a profile and its tokens."""
    store = _get_profile_store()
    target = profile or store.active_profile_name

    if not typer.confirm(f'Delete profile {target!r}?'):
        raise typer.Abort()

    store.delete_profile(target)
    typer.secho(f'Profile {target!r} deleted.', fg=typer.colors.GREEN)


@auth_app.command('list')
def auth_list(
        ctx: typer.Context,
) -> None:
    """List all stored profiles."""
    store = _get_profile_store()
    profiles = store.list_profiles()

    if not profiles:
        typer.echo('No profiles configured. Use `wb auth login` to add one.')
        return

    json_output = ctx.obj.get('json_output', False) if ctx.obj else False

    if json_output:
        import json
        data = []
        for p in profiles:
            data.append({
                'name': p.name,
                'active': p.name == store.active_profile_name,
                'categories': list(p.tokens.keys()),
                'created_at': p.created_at,
                'last_used': p.last_used,
            })
        typer.echo(json.dumps(data, indent=2))
        return

    from rich.console import Console
    from rich.table import Table

    table = Table(title='WB CLI Profiles')
    table.add_column('Profile', style='cyan')
    table.add_column('Active', justify='center')
    table.add_column('Categories', style='green')
    table.add_column('Created', style='dim')

    for p in profiles:
        is_active = '*' if p.name == store.active_profile_name else ''
        categories = ', '.join(p.tokens.keys()) or 'none'
        table.add_row(p.name, is_active, categories, p.created_at[:10])

    Console().print(table)


@auth_app.command('use')
def auth_use(
        profile_name: str = typer.Argument(..., help='Profile to activate'),
) -> None:
    """Switch the active profile."""
    store = _get_profile_store()
    store.set_active(profile_name)
    typer.secho(f'Active profile set to {profile_name!r}.', fg=typer.colors.GREEN)


@auth_app.command('status')
def auth_status(
        ctx: typer.Context,
) -> None:
    """Show current authentication status."""
    store = _get_profile_store()
    try:
        profile = store.get_profile()
    except WbCliError:
        typer.secho('No active profile. Use `wb auth login`.', fg=typer.colors.YELLOW)
        return

    json_output = ctx.obj.get('json_output', False) if ctx.obj else False

    if json_output:
        import json
        typer.echo(json.dumps({
            'profile': profile.name,
            'categories': list(profile.tokens.keys()),
            'last_used': profile.last_used,
        }, indent=2))
        return

    typer.echo(f'Active profile: {profile.name}')
    typer.echo(f'Token categories: {", ".join(profile.tokens.keys()) or "none"}')
    typer.echo(f'Last used: {profile.last_used or "never"}')


@auth_app.command('ping')
def auth_ping(
        profile: str | None = typer.Option(None, '--profile', '-p', help='Profile to test'),
) -> None:
    """Test API connectivity with the current token."""
    store = _get_profile_store()
    p = store.get_profile(profile)

    if not p.has_token('promotion'):
        typer.secho(
            f'Profile {p.name!r} has no promotion token.',
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=3)

    typer.echo('Testing API connectivity...')
    try:
        validate_promotion_token(p.get_token('promotion'))
        typer.secho('API connection successful.', fg=typer.colors.GREEN)
    except WbCliError as exc:
        typer.secho(f'Connection failed: {exc}', fg=typer.colors.RED, err=True)
        raise typer.Exit(code=3) from exc
