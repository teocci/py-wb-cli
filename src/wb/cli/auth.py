"""CLI commands for authentication and profile management."""

from __future__ import annotations

import typer

from wb.auth.bootstrap_env import BootstrapEnv
from wb.auth.profiles import ProfileStore
from wb.auth.token_utils import extract_token_claims
from wb.auth.token_validation import validate_promotion_token
from wb.core.config import Settings
from wb.core.constants import (
    ALL_CATEGORY,
    DEFAULT_PROFILE_NAME,
    DEFAULT_TOKEN_TYPE,
    ExitCode,
    PROFILE_NAME_TEMPLATE,
    PROFILE_SLUG_RE,
    TOKEN_CATEGORIES,
    TOKEN_TYPES,
)
from wb.core.exceptions import ConfigError, ValidationError, WbCliError
from wb.core.output import _stdout_console

auth_app = typer.Typer(
    help=(
        'Authentication and profile management. Two auth methods: '
        '`login` registers an OFFICIAL WB API token (JWT) for the '
        'documented `/api/advert`, `/analytics`, `/statistics` etc. '
        'endpoints; `login-portal` registers an UNOFFICIAL seller-portal '
        'browser session (cookie + authorizev3) used to scrape data the '
        'public API does not expose. Use both on the same profile when a '
        'workflow needs both.'
    ),
    no_args_is_help=True,
)


def _get_profile_store() -> ProfileStore:
    """Create a ProfileStore from current settings."""
    settings = Settings()
    settings.ensure_config_dir()
    return ProfileStore(settings.config_dir)


def _bootstrap_token_from_env(category: str) -> str | None:
    """Resolve a JWT from env / ``.env`` for ``wb auth login`` bootstrap.

    Analytics-only profiles prefer ``WB_ANALYTICS_TOKEN`` so a seller
    who keeps that env var separate isn't forced to alias it into
    ``WB_API_TOKEN`` first. Every other category (and the ``all``
    meta-category) falls back to ``WB_API_TOKEN``.

    Args:
        category: ``--category`` value from the CLI.

    Returns:
        Token string when env has one, otherwise ``None`` (the caller
        translates that into a :data:`ExitCode.CONFIG_ERROR`).
    """
    env = BootstrapEnv()
    if category == 'analytics':
        return env.analytics_token or env.api_token
    return env.api_token


def _validate_slug(name: str) -> None:
    """Reject profile names with spaces or special characters.

    Raises:
        ValidationError: If ``name`` doesn't match :data:`PROFILE_SLUG_RE`.
    """
    if not PROFILE_SLUG_RE.match(name):
        raise ValidationError(
            f'Invalid profile name {name!r}. Must match {PROFILE_SLUG_RE.pattern} '
            f'(lowercase letters/digits/underscores; no spaces or special chars).'
        )


def _resolve_profile_name(
        explicit: str | None,
        claims: dict,
        resolved_type: str,
        store: ProfileStore,
) -> str:
    """Pick the profile name for an ``auth login`` invocation.

    - When ``explicit`` is given: slug-validate and return it.
    - When ``explicit`` is None and ``claims['seller_id']`` is known:
      return ``'{seller_id}_{token_type}'``. Raise on collision.
    - When ``explicit`` is None and seller_id is unknown (undecodable
      token): fall back to the active profile name, else
      :data:`DEFAULT_PROFILE_NAME`.

    Raises:
        ValidationError: On invalid slug or auto-name collision.
    """
    if explicit is not None:
        _validate_slug(explicit)
        return explicit

    seller_id = claims.get('seller_id')
    if not seller_id:
        return store.active_profile_name or DEFAULT_PROFILE_NAME

    candidate = PROFILE_NAME_TEMPLATE.format(
        seller_id=seller_id, token_type=resolved_type,
    )
    if any(p.name == candidate for p in store.list_profiles()):
        raise ValidationError(
            f'Profile {candidate!r} already exists for seller {seller_id}. '
            f'Use --profile <name> to choose a different name.'
        )
    return candidate


@auth_app.command('login')
def auth_login(
        ctx: typer.Context,
        profile: str | None = typer.Option(
            None, '--profile', '-p',
            help=(
                'Profile name (slug: lowercase letters/digits/underscore). '
                'When omitted, auto-named "{seller_id}_{token_type}" '
                'from the JWT.'
            ),
        ),
        category: str | None = typer.Option(
            None, '--category', '-c',
            help=(
                'Token category (run `wb auth categories` to list valid '
                "values). Default: 'promotion' when --token is passed, "
                "'all' when bootstrapping from env (single full-scope "
                'token covers every category)'
            ),
        ),
        token: str | None = typer.Option(
            None, '--token', '-t',
            help=(
                'WB API token. When omitted, falls back to WB_API_TOKEN '
                '(or WB_ANALYTICS_TOKEN for --category analytics) from '
                'env / .env — the rare single-seller bootstrap case.'
            ),
        ),
        token_type: str | None = typer.Option(
            None, '--token-type',
            help=(
                'Token type for rate-limit prior selection: '
                f'{", ".join(TOKEN_TYPES)}. When omitted, falls back to '
                '"test" if the JWT marks the token as test, otherwise to '
                '"base" (the safe default).'
            ),
        ),
        skip_validation: bool = typer.Option(False, '--skip-validation', help='Skip token validation'),
) -> None:
    """Store an OFFICIAL WB API token (JWT) for a profile.

    This is the documented WB authentication path — the token is the JWT
    you generate from the seller portal UI under "API tokens". Used by
    every official endpoint the CLI calls:

    - Promotion (`/api/advert/...`) — campaigns, bids, budgets
    - Analytics (`/api/v2/...`) — sales funnel, search reports
    - Statistics (`/api/v1/...`) — orders, stocks, prices
    - Content / Marketplace / Finance / etc. — 11 token categories total

    For unofficial seller-portal scraping (product cards, render-token
    generation), use ``wb auth login-portal`` instead — that path takes
    browser cookies, not a JWT.

    The token's payload is decoded (no signature verification) to
    populate:
        - ``oid``  → ``Profile.seller_id``
        - ``exp``  → ``Profile.token_expires_at``
        - ``t``    → auto-detects ``token_type='test'`` when true

    When ``--token`` is omitted, ``WB_API_TOKEN`` is read from the
    environment / ``.env`` and used as if it had been passed. For
    ``--category analytics`` the lookup falls back to
    ``WB_ANALYTICS_TOKEN`` before ``WB_API_TOKEN``. In this bootstrap
    mode ``--category`` defaults to ``'all'`` (a single full-scope env
    token is the common case); pass ``--category`` explicitly to scope
    it down. The explicit-``--token`` path keeps the historical
    ``'promotion'`` default.

    This bootstrap path matters only for single-seller setups;
    multi-profile users should pass ``--token`` explicitly.
    """
    store = _get_profile_store()

    bootstrapped_from_env = token is None
    if bootstrapped_from_env:
        # Resolve category early because the env lookup may want to honor
        # an explicit --category analytics override.
        env_category = category or ALL_CATEGORY
        token = _bootstrap_token_from_env(env_category)
        if token is None:
            typer.secho(
                'No --token flag and no WB_API_TOKEN in env / .env. '
                'Pass --token <JWT> or set WB_API_TOKEN before running '
                '`wb auth login`.',
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=ExitCode.CONFIG_ERROR)
        category = env_category
    else:
        category = category or 'promotion'

    if token_type is not None and token_type not in TOKEN_TYPES:
        typer.secho(
            f'Invalid --token-type {token_type!r}. '
            f'Valid types: {", ".join(TOKEN_TYPES)}.',
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=ExitCode.VALIDATION_ERROR)

    if not skip_validation and category in ('promotion', ALL_CATEGORY):
        typer.echo('Validating token...')
        try:
            validate_promotion_token(token)
            typer.secho('Token validated successfully.', fg=typer.colors.GREEN)
        except WbCliError as exc:
            typer.secho(f'Validation failed: {exc}', fg=typer.colors.RED, err=True)
            raise typer.Abort() from exc

    claims = extract_token_claims(token)
    is_test = claims['is_test']

    # Tentative type for auto-name resolution (`{oid}_{type}`).
    tentative_type = token_type or ('test' if is_test else DEFAULT_TOKEN_TYPE)

    try:
        resolved_profile = _resolve_profile_name(profile, claims, tentative_type, store)
    except ValidationError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=ExitCode.VALIDATION_ERROR) from exc

    # Final type: explicit flag wins, then JWT test, else preserve existing
    # (re-login on a known profile must not reset token_type to the default),
    # else default.
    existing = next(
        (p for p in store.list_profiles() if p.name == resolved_profile),
        None,
    )
    if token_type is not None:
        resolved_type = token_type
    elif is_test:
        resolved_type = 'test'
    elif existing is not None:
        resolved_type = existing.token_type
    else:
        resolved_type = DEFAULT_TOKEN_TYPE

    store.save_token(resolved_profile, category, token)
    try:
        store.set_token_type(resolved_profile, resolved_type)
    except ValidationError as exc:  # pragma: no cover — guarded above
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=ExitCode.VALIDATION_ERROR) from exc
    if claims['seller_id']:
        store.set_seller_id(resolved_profile, claims['seller_id'])
    if claims['expires_at']:
        store.set_token_expires_at(resolved_profile, claims['expires_at'])
    store.set_active(resolved_profile)

    saved_type = store.get_profile(resolved_profile).token_type
    if category == ALL_CATEGORY:
        typer.secho(
            f'Token saved to profile {resolved_profile!r} '
            f'[all {len(TOKEN_CATEGORIES)} categories, type={saved_type}].',
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(
            f'Token saved to profile {resolved_profile!r} '
            f'[{category}, type={saved_type}].',
            fg=typer.colors.GREEN,
        )


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
                'token_type': p.token_type,
                'categories': list(p.tokens.keys()),
                'seller_id': p.seller_id,
                'token_expires_at': p.token_expires_at,
                'created_at': p.created_at,
                'last_used': p.last_used,
            })
        typer.echo(json.dumps(data, indent=2))
        return

    from rich.table import Table

    table = Table(title='WB CLI Profiles')
    table.add_column('Profile', style='cyan')
    table.add_column('Active', justify='center')
    table.add_column('Type', style='magenta')
    table.add_column('Seller ID', style='yellow')
    table.add_column('Categories', style='green')
    table.add_column('Created', style='dim')

    for p in profiles:
        is_active = '*' if p.name == store.active_profile_name else ''
        categories = ', '.join(p.tokens.keys()) or 'none'
        table.add_row(
            p.name, is_active, p.token_type,
            p.seller_id or '', categories, p.created_at[:10],
        )

    _stdout_console.print(table)


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
            'token_type': profile.token_type,
            'categories': list(profile.tokens.keys()),
            'seller_id': profile.seller_id,
            'token_expires_at': profile.token_expires_at,
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
    typer.echo(f'Token type: {profile.token_type}')
    typer.echo(f'Token categories: {", ".join(profile.tokens.keys()) or "none"}')
    if profile.seller_id:
        typer.echo(f'Seller ID: {profile.seller_id}')
    if profile.token_expires_at:
        from datetime import datetime, timezone
        exp_dt = datetime.fromtimestamp(profile.token_expires_at, tz=timezone.utc)
        typer.echo(f'Token expires: {exp_dt.isoformat()}')
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

    from rich.table import Table

    table = Table(title='Token Categories')
    table.add_column('Slug', style='cyan')
    table.add_column('Display Name', style='green')
    table.add_column('Note', style='dim')
    for slug in TOKEN_CATEGORIES:
        table.add_row(slug, CATEGORY_DISPLAY_NAMES[slug], '')
    table.add_row(ALL_CATEGORY, 'All categories', 'saves token under all above')
    _stdout_console.print(table)


@auth_app.command('login-portal')
def auth_login_portal(
        profile: str = typer.Option('default', '--profile', '-p', help='Profile name'),
        authorizev3: str | None = typer.Option(
            None, '--authorizev3', '-a',
            help=(
                'authorizev3 header value from browser DevTools. When '
                'omitted, falls back to WB_AUTHORIZEV3 from env / .env.'
            ),
        ),
        cookie: str | None = typer.Option(
            None, '--cookie', '-c',
            help=(
                'Browser cookie string (required for portal auth). When '
                'omitted, falls back to WB_PORTAL_COOKIE from env / .env.'
            ),
        ),
        skip_auth: bool = typer.Option(
            False, '--skip-auth',
            help='Store credentials without authenticating',
        ),
) -> None:
    """Store UNOFFICIAL seller-portal session credentials for a profile.

    This is NOT the official WB API. It logs into the WB seller portal
    (https://seller.wildberries.ru) the same way the manager's browser
    does — by replaying ``authorizev3`` + ``cookie`` headers copied from
    a logged-in browser session. There is no public documentation for
    these endpoints; the CLI uses them to read data the official API
    does not expose. Today that includes:

    - Product cards via the portal ``tableListv6`` endpoint
      (``wb portal products``).
    - Render-token generation via the portal JRPC endpoint
      (``wb auth generate-token``).

    For documented operations (campaigns, bids, analytics, statistics),
    use ``wb auth login`` with a JWT instead — that path is faster, has
    real rate limits, and survives portal session expiry.

    How to obtain the credentials:
        1. Log into https://seller.wildberries.ru in a browser.
        2. Open DevTools → Application → Cookies, copy the full Cookie
           header for the seller.wildberries.ru domain.
        3. Network tab → pick any request → Headers → copy
           ``authorizev3``.

    Both values are required — either via ``--authorizev3`` / ``--cookie``
    or via ``WB_AUTHORIZEV3`` / ``WB_PORTAL_COOKIE`` in env / ``.env``.
    The env path is the rare single-seller bootstrap case;
    multi-profile users should pass the flags explicitly.
    """
    from wb.client.portal import PortalClient

    store = _get_profile_store()

    if authorizev3 is None or cookie is None:
        env = BootstrapEnv()
        authorizev3 = authorizev3 or env.authorizev3
        cookie = cookie or env.portal_cookie
    if not authorizev3 or not cookie:
        typer.secho(
            'Portal auth requires both --authorizev3 and --cookie '
            '(or WB_AUTHORIZEV3 + WB_PORTAL_COOKIE in env / .env). '
            'Run `wb auth login-portal --help` for details.',
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=ExitCode.CONFIG_ERROR)

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
    """Generate a render token via the UNOFFICIAL portal JRPC endpoint.

    Requires a portal session registered with ``wb auth login-portal``.
    The render token is a short-lived credential used by the portal's
    front-end for some operations the official API does not cover.
    """
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
