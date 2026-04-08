"""CLI commands for authentication and profile management."""

from __future__ import annotations

import typer

from wb.auth.profiles import ProfileStore
from wb.auth.token_validation import validate_promotion_token
from wb.core.config import Settings
from wb.core.constants import ALL_CATEGORY, ExitCode, TOKEN_CATEGORIES
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
        category: str = typer.Option(
            'promotion', '--category', '-c',
            help='Token category (run `wb auth categories` to list valid values)',
        ),
        token: str = typer.Option(..., '--token', '-t', help='WB API token'),
        skip_validation: bool = typer.Option(False, '--skip-validation', help='Skip token validation'),
) -> None:
    """Store an API token for a profile."""
    store = _get_profile_store()

    if not skip_validation and category in ('promotion', ALL_CATEGORY):
        typer.echo('Validating token...')
        try:
            validate_promotion_token(token)
            typer.secho('Token validated successfully.', fg=typer.colors.GREEN)
        except WbCliError as exc:
            typer.secho(f'Validation failed: {exc}', fg=typer.colors.RED, err=True)
            raise typer.Abort() from exc

    store.save_token(profile, category, token)
    store.set_active(profile)
    if category == ALL_CATEGORY:
        typer.secho(
            f'Token saved to profile {profile!r} [all {len(TOKEN_CATEGORIES)} categories].',
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(f'Token saved to profile {profile!r} [{category}].', fg=typer.colors.GREEN)


@auth_app.command('logout')
def auth_logout(
        profile: str = typer.Option(None, '--profile', '-p', help='Profile to remove'),
        yes: bool = typer.Option(False, '--yes', '-y', help='Skip confirmation prompt'),
) -> None:
    """Remove a profile and its tokens."""
    store = _get_profile_store()
    target = profile or store.active_profile_name

    if not yes and not typer.confirm(f'Delete profile {target!r}?'):
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

    has_portal = profile.has_portal_session()

    if json_output:
        import json
        data = {
            'profile': profile.name,
            'categories': list(profile.tokens.keys()),
            'portal_session': has_portal,
            'last_used': profile.last_used,
        }
        if has_portal:
            ps = profile.get_portal_session()
            if not ps:
                typer.secho('Error: Portal session data is missing or corrupted.', fg=typer.colors.RED, err=True)
                raise typer.Exit(code=ExitCode.CONFIG_ERROR)

            data['portal_user_id'] = ps.get('user_id')
            data['portal_exp'] = ps.get('exp')
        typer.echo(json.dumps(data, indent=2))
        return

    typer.echo(f'Active profile: {profile.name}')
    typer.echo(f'Token categories: {", ".join(profile.tokens.keys()) or "none"}')
    typer.echo(f'Portal session: {"yes" if has_portal else "no"}')
    if has_portal:
        ps = profile.get_portal_session()
        if not ps:
            typer.secho('Error: Portal session data is missing or corrupted.', fg=typer.colors.RED, err=True)
            raise typer.Exit(code=ExitCode.CONFIG_ERROR)
        
        typer.echo(f'Portal user ID: {ps.get("user_id", "unknown")}')
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
        raise typer.Exit(code=ExitCode.AUTH_FAILURE)

    typer.echo('Testing API connectivity...')
    try:
        validate_promotion_token(p.get_token('promotion'))
        typer.secho('API connection successful.', fg=typer.colors.GREEN)
    except WbCliError as exc:
        typer.secho(f'Connection failed: {exc}', fg=typer.colors.RED, err=True)
        raise typer.Exit(code=ExitCode.AUTH_FAILURE) from exc


@auth_app.command('categories')
def auth_categories(ctx: typer.Context) -> None:
    """List all valid token categories for use with --category."""
    from wb.core.constants import CATEGORY_DISPLAY_NAMES

    json_output = ctx.obj.get('json_output', False) if ctx.obj else False

    if json_output:
        import json
        data = [
            {'slug': s, 'display': CATEGORY_DISPLAY_NAMES[s], 'meta': False}
            for s in TOKEN_CATEGORIES
        ]
        data.append({'slug': ALL_CATEGORY, 'display': 'All categories', 'meta': True})
        typer.echo(json.dumps(data, indent=2))
        return

    from rich.console import Console
    from rich.table import Table

    table = Table(title='Token Categories')
    table.add_column('Slug', style='cyan')
    table.add_column('Display Name', style='green')
    table.add_column('Note', style='dim')
    for slug in TOKEN_CATEGORIES:
        table.add_row(slug, CATEGORY_DISPLAY_NAMES[slug], '')
    table.add_row(ALL_CATEGORY, 'All categories', 'saves token under all above')
    Console().print(table)


@auth_app.command('login-portal')
def auth_login_portal(
        profile: str = typer.Option('default', '--profile', '-p', help='Profile name'),
        authorizev3: str = typer.Option(
            ..., '--authorizev3', '-a',
            help='authorizev3 header value from browser DevTools',
        ),
        cookie: str = typer.Option(
            ..., '--cookie', '-c',
            help='Browser cookie string (required for portal auth)',
        ),
        skip_auth: bool = typer.Option(
            False, '--skip-auth',
            help='Store credentials without authenticating',
        ),
) -> None:
    """Authenticate with the WB seller portal using browser credentials.

    Both authorizev3 and cookie are required. Copy them from browser DevTools.
    """
    from wb.client.portal import PortalClient

    store = _get_profile_store()

    try:
        client = PortalClient(authorizev3=authorizev3, cookie=cookie)
    except WbCliError as exc:
        typer.secho(f'Error: {exc}', fg=typer.colors.RED, err=True)
        raise typer.Abort() from exc

    if skip_auth:
        store.save_portal_session(
            profile_name=profile,
            authorizev3=authorizev3,
            cookie=cookie,
        )
        store.set_active(profile)
        typer.secho(
            f'Portal session saved to profile {profile!r} (not validated).',
            fg=typer.colors.YELLOW,
        )
        return

    typer.echo('Authenticating with seller portal...')
    try:
        session = client.authenticate()
    except WbCliError as exc:
        typer.secho(f'Portal auth failed: {exc}', fg=typer.colors.RED, err=True)
        raise typer.Abort() from exc

    store.save_portal_session(
        profile_name=profile,
        authorizev3=authorizev3,
        cookie=cookie,
        session_token=session.token,
        user_id=str(session.user_id),
        exp=str(session.exp),
    )
    store.set_active(profile)

    from datetime import datetime, timezone
    exp_dt = datetime.fromtimestamp(session.exp, tz=timezone.utc)
    typer.secho('Portal authentication successful.', fg=typer.colors.GREEN)
    typer.echo(f'  User ID: {session.user_id}')
    typer.echo(f'  Expires: {exp_dt.isoformat()}')
    typer.echo(f'  Profile: {profile!r}')


@auth_app.command('generate-token')
def auth_generate_token(
        profile: str | None = typer.Option(
            None, '--profile', '-p', help='Profile to use',
        ),
) -> None:
    """Generate a render token using stored portal session credentials."""
    try:
        from wb.services._factory import create_portal_client
        client = create_portal_client(profile)
    except WbCliError as exc:
        typer.secho(f'Error: {exc}', fg=typer.colors.RED, err=True)
        raise typer.Exit(code=ExitCode.CONFIG_ERROR) from exc

    typer.echo('Generating token via portal...')
    try:
        token = client.generate_token()
    except WbCliError as exc:
        typer.secho(f'Token generation failed: {exc}', fg=typer.colors.RED, err=True)
        raise typer.Exit(code=ExitCode.API_ERROR) from exc

    masked = f'{token[:8]}...{token[-4:]}' if len(token) > 12 else '***'
    typer.secho('Token generated successfully.', fg=typer.colors.GREEN)
    typer.echo(f'  Token: {masked}')
    typer.echo(f'  Length: {len(token)} chars')
