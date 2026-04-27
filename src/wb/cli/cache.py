"""CLI diagnostic commands for the HTTP response cache.

``wb cache status`` and ``wb cache clear`` are the operator equivalents
of ``wb rate status`` for the request cache. They read
``~/.wb-cli/request_cache.db`` directly — no network calls — so they
never consume rate-limit budget. Both work alongside ``--no-cache`` /
``WB_REQUEST_CACHE=disabled`` when an operator wants to bypass cached
data for one invocation.

For domain-level snapshots (campaign configs, daily stats, clusters,
budget events) see ``wb snapshot ...`` instead.
"""

from __future__ import annotations

import json
import time

import typer

from wb.cli._helpers import get_profile, get_renderer
from wb.core.constants import REQUEST_CACHE_DB_FILE

__all__ = ['cache_app']

cache_app = typer.Typer(
    help='HTTP response cache (transparent, cooldown-tied TTL)',
    no_args_is_help=True,
)


@cache_app.command('status')
def cache_status(ctx: typer.Context) -> None:
    """Show per-(seller, token, endpoint) cache state.

    Reads the shared ``request_cache.db`` only — no network calls. Rows
    are grouped by plaintext ``seller_id`` (extracted from the JWT
    ``sid`` claim of profiles that match a row's ``token_fp``), then by
    token, then by endpoint. For each endpoint group: row count, total
    bytes, oldest ``cached_at``, soonest ``expires_at``, and a flag for
    whether at least one row is still fresh (``expires_at > now``).

    Safe to call without any token loaded; when no rows exist the
    output shows an empty ``sellers`` list.
    """
    from wb.auth.profiles import ProfileStore
    from wb.core.config import Settings
    from wb.storage.request_cache import RequestCache

    renderer = get_renderer(ctx)
    settings = Settings()
    settings.ensure_config_dir()

    profile_hint = get_profile(ctx)
    store = ProfileStore(settings.config_dir)
    try:
        active_profile = profile_hint or store.active_profile_name
    except Exception:  # noqa: BLE001 — no profile registered yet
        active_profile = profile_hint or settings.active_profile

    db_path = settings.config_dir / REQUEST_CACHE_DB_FILE
    cache = RequestCache(db_path=db_path)
    rows = cache.read_all()
    fp_to_seller = _build_fp_to_seller(store)

    now = time.time()
    sellers = _group_rows_by_seller(rows, now, fp_to_seller)

    payload = {
        'now_epoch': round(now, 3),
        'profile': active_profile,
        'sellers': sellers,
    }

    if renderer.is_json:
        compact = (ctx.obj or {}).get('compact', False)
        typer.echo(
            json.dumps(
                payload,
                separators=(',', ':') if compact else (',', ': '),
                indent=None if compact else 2,
                ensure_ascii=False,
            )
        )
        return

    _render_status_table(active_profile, sellers)


@cache_app.command('clear')
def cache_clear(
        ctx: typer.Context,
        endpoint: str | None = typer.Option(
            None, '--endpoint',
            help='Clear only entries for this endpoint path '
                 '(e.g. /api/advert/v2/adverts).',
        ),
        token_fp: str | None = typer.Option(
            None, '--token',
            help='Clear only entries for this token fingerprint prefix '
                 '(matches the values shown by `wb cache status`).',
        ),
        all_entries: bool = typer.Option(
            False, '--all',
            help='Clear every entry across every token. Requires --yes '
                 'unless --json is active.',
        ),
        yes: bool = typer.Option(
            False, '--yes', '-y',
            help='Skip the interactive confirmation for --all.',
        ),
) -> None:
    """Delete cached HTTP responses; surgical or full wipe.

    With no flags, drops entries for the active profile's promotion
    token only — the safe default. ``--endpoint`` and ``--token``
    narrow the wipe further. ``--all`` wipes everything but requires
    ``--yes`` (or JSON mode) to proceed without prompting.
    """
    from wb.auth.profiles import ProfileStore
    from wb.core.config import Settings
    from wb.storage.request_cache import RequestCache

    renderer = get_renderer(ctx)
    settings = Settings()
    settings.ensure_config_dir()

    if all_entries and not (yes or renderer.is_json):
        confirmed = typer.confirm(
            'Clear ALL cached HTTP responses across every token?',
            default=False,
        )
        if not confirmed:
            raise typer.Abort()

    db_path = settings.config_dir / REQUEST_CACHE_DB_FILE
    cache = RequestCache(db_path=db_path)

    scope_token: str | None = None
    if not all_entries:
        if token_fp is not None:
            scope_token = _resolve_token_fp(token_fp, ProfileStore(settings.config_dir))
        else:
            scope_token = _active_token_fp(ctx, settings, ProfileStore(settings.config_dir))
        if scope_token is None:
            typer.secho(
                'Cannot resolve a token to scope the wipe to. Pass --all '
                'to clear everything explicitly, or --token <fp> to '
                'scope by a known fingerprint.',
                fg=typer.colors.YELLOW, err=True,
            )
            raise typer.Exit(code=2)

    deleted = cache.clear(token_fp=scope_token, endpoint=endpoint)

    payload = {
        'deleted': deleted,
        'scope': {
            'all': all_entries,
            'token_fp': scope_token,
            'endpoint': endpoint,
        },
    }

    if renderer.is_json:
        compact = (ctx.obj or {}).get('compact', False)
        typer.echo(
            json.dumps(
                payload,
                separators=(',', ':') if compact else (',', ': '),
                indent=None if compact else 2,
                ensure_ascii=False,
            )
        )
        return

    typer.echo(f'Deleted {deleted} cache row{"s" if deleted != 1 else ""}.')
    if all_entries:
        typer.echo('Scope: all tokens, all endpoints.')
    else:
        typer.echo(
            f'Scope: token={scope_token or "(none)"}, '
            f'endpoint={endpoint or "(any)"}.'
        )


# ── Helpers ──────────────────────────────────────────────────────────


def _build_fp_to_seller(store) -> dict[str, str | None]:
    """Map known token fingerprints to the seller_id from their profile.

    Walks :class:`ProfileStore` once. For every category token in every
    profile, computes the fingerprint and (when possible) extracts the
    seller_id from the JWT ``sid`` claim. Used by ``cache status`` to
    annotate cache rows with a human-readable seller label.
    """
    from wb.core.rate_limiter import compute_token_fingerprint, extract_seller_id

    mapping: dict[str, str | None] = {}
    try:
        profiles = store.list_profiles()
    except Exception:  # noqa: BLE001
        return mapping
    for profile in profiles:
        for token in profile.tokens.values():
            if token:
                fp = compute_token_fingerprint(token)
                mapping[fp] = extract_seller_id(token)
    return mapping


def _group_rows_by_seller(
        rows,
        now: float,
        fp_to_seller: dict[str, str | None] | None = None,
) -> list[dict]:
    """Group cache rows by seller, then token, then endpoint.

    Returns a JSON-friendly tree:
    ``[{seller_id, tokens: [{token_fp, endpoints: [...]}]}, ...]``.
    """
    fp_to_seller = fp_to_seller or {}
    by_seller: dict[str | None, dict[str, list]] = {}
    for row in rows:
        seller_id = fp_to_seller.get(row.token_fp)
        token_endpoints = by_seller.setdefault(seller_id, {})
        token_endpoints.setdefault(row.token_fp, []).append(row)

    sellers: list[dict] = []
    for seller_id in sorted(by_seller, key=_seller_sort_key):
        tokens_list = []
        for token_fp in sorted(by_seller[seller_id]):
            endpoints = _summarise_endpoints(by_seller[seller_id][token_fp], now)
            tokens_list.append({
                'token_fp': token_fp,
                'endpoints': endpoints,
            })
        sellers.append({'seller_id': seller_id, 'tokens': tokens_list})
    return sellers


def _summarise_endpoints(rows, now: float) -> list[dict]:
    """Aggregate per-endpoint stats over a flat list of rows."""
    by_ep: dict[str, list] = {}
    for row in rows:
        by_ep.setdefault(row.endpoint, []).append(row)
    out: list[dict] = []
    for endpoint, group in sorted(by_ep.items()):
        oldest = min(r.cached_at for r in group)
        soonest = min(r.expires_at for r in group)
        latest_expires = max(r.expires_at for r in group)
        total_bytes = sum(len(r.payload) for r in group)
        fresh = any(r.expires_at > now for r in group)
        out.append({
            'endpoint': endpoint,
            'rows': len(group),
            'bytes': total_bytes,
            'oldest_cached_at': round(oldest, 3),
            'soonest_expires_at': round(soonest, 3),
            'soonest_expires_in_s': round(max(0.0, soonest - now), 1),
            'latest_expires_at': round(latest_expires, 3),
            'fresh': fresh,
        })
    return out


def _seller_sort_key(seller_id: str | None) -> tuple[int, str]:
    """Sort known sellers before unknowns; alphabetical within each group."""
    return (1, '') if seller_id is None else (0, seller_id)


def _render_status_table(active_profile: str, sellers: list[dict]) -> None:
    """Print the human-readable view of ``cache status``."""
    from wb.core.output import render_table

    typer.echo(f'Profile : {active_profile}')
    if not sellers:
        typer.echo('')
        typer.echo('No cached responses yet.')
        return

    for seller in sellers:
        sid = seller['seller_id'] or '(unknown sid)'
        tokens = seller['tokens']
        typer.echo('')
        typer.echo(
            f'Seller {sid} ({len(tokens)} token{"s" if len(tokens) != 1 else ""})'
        )
        for token in tokens:
            rows = [
                [
                    ep['endpoint'],
                    str(ep['rows']),
                    _human_bytes(ep['bytes']),
                    f"{ep['soonest_expires_in_s']:.0f}",
                    'fresh' if ep['fresh'] else 'expired',
                ]
                for ep in token['endpoints']
            ]
            render_table(
                ['Endpoint', 'Rows', 'Bytes', 'Soonest expires (s)', 'State'],
                rows,
                title=f'Token {token["token_fp"]}',
            )


def _human_bytes(n: int) -> str:
    """Compact byte-size formatter."""
    if n < 1024:
        return f'{n} B'
    if n < 1024 * 1024:
        return f'{n / 1024:.1f} KB'
    return f'{n / (1024 * 1024):.1f} MB'


def _resolve_token_fp(prefix: str, store) -> str | None:
    """Match a fingerprint prefix against known profile tokens.

    Args:
        prefix: User-supplied prefix.
        store: ProfileStore to walk.

    Returns:
        The full fingerprint when exactly one match exists, the prefix
        itself when no profile match is found (passes through to the
        DB), or ``None`` when the input is empty.
    """
    from wb.core.rate_limiter import compute_token_fingerprint

    if not prefix:
        return None
    candidates: set[str] = set()
    try:
        profiles = store.list_profiles()
    except Exception:  # noqa: BLE001
        return prefix
    for profile in profiles:
        for token in profile.tokens.values():
            if not token:
                continue
            fp = compute_token_fingerprint(token)
            if fp.startswith(prefix):
                candidates.add(fp)
    if len(candidates) == 1:
        return next(iter(candidates))
    return prefix


def _active_token_fp(ctx, settings, store) -> str | None:
    """Return the fingerprint of the active profile's promotion token.

    Falls back to ``None`` when no profile is registered or the active
    profile lacks a promotion token. ``None`` means "no token scope" —
    ``cache.clear(token_fp=None, ...)`` then drops everything (so this
    helper should never return ``None`` on the cautious code path; the
    caller guards with ``--all`` requirement).
    """
    from wb.core.rate_limiter import compute_token_fingerprint

    profile_hint = (ctx.obj or {}).get('profile')
    try:
        profile = store.get_profile(profile_hint)
    except Exception:  # noqa: BLE001
        return None
    token = profile.get_token('promotion') if profile else None
    if not token:
        return None
    return compute_token_fingerprint(token)
