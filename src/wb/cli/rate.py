"""CLI diagnostic commands for rate-limit state (I-13/I-14, R-3/R-4).

Two read-only / read-mostly commands surface the live state of the
``~/.wb-cli/rate_limits.db`` ``endpoint_budget`` table populated by
every WB response's ``X-Ratelimit-*`` headers (see
:mod:`wb.core.endpoint_budget`):

- ``wb rate status`` — pure read, no network. Grouped by plaintext
  seller_id, then by token fingerprint, then by endpoint, so every
  operator sees every active cooldown regardless of which token their
  shell is currently configured with.
- ``wb rate probe`` — single-call probe against ``/adv/v1/balance`` to
  refresh the budget for that endpoint. Pre-flight reads the
  ``endpoint_budget`` row for the current token's probe bucket and
  skips the network entirely when ``remaining=0`` and ``reset_at`` is
  still in the future. After the call, the response headers feed back
  into the budget via :meth:`EndpointBudget.observe_headers`.

R-4 cleanup: both commands now go through ``EndpointBudget`` only —
the legacy seller-wide ``SellerCooldownLock`` short-circuit (F-13) is
gone, so a 429 on one endpoint no longer locks unrelated endpoints.
"""

from __future__ import annotations

import json
import time

import typer

from wb.cli._helpers import get_profile, get_renderer
from wb.core.constants import (
    EP_ACCOUNT_BALANCE,
    PROMOTION_BASE_URL,
    RATE_LIMIT_DB_FILE,
)
from wb.core.exceptions import RateLimitError

__all__ = ['rate_app']

rate_app = typer.Typer(
    help='Local rate-limit diagnostic and safe single-call probe',
    no_args_is_help=True,
)

# Endpoint used by `wb rate probe`. Picked for:
# - small response body (balance is a handful of numeric fields)
# - per-seller scope (carries the x-ratelimit-* headers we care about)
# - 1/s documented rate limit (generous, won't itself cause throttling)
_PROBE_ENDPOINT = EP_ACCOUNT_BALANCE

# Hard timeout for a single probe request — deliberately short so a stuck
# probe never compounds a pending cooldown through connection hold time.
_PROBE_TIMEOUT_SECONDS = 10.0


@rate_app.command('status')
def rate_status(ctx: typer.Context) -> None:
    """Show per-(seller, token, endpoint) rate-limit budget state.

    Reads the shared ``rate_limits.db`` file only — no network calls. The
    ``endpoint_budget`` table is populated by every WB response's
    ``x-ratelimit-*`` headers, so this view reflects everything the
    cross-process rate limiter currently knows.

    Output is grouped by plaintext ``seller_id`` (extracted from the JWT
    ``sid`` claim by :class:`EndpointBudget`), then by token fingerprint,
    then by endpoint. Rows where ``remaining == 0`` and ``reset_at > now``
    are flagged ``locked: true`` — that bucket is unreachable until the
    deadline passes. Other endpoints stay usable in the meantime.

    Safe to call without any token loaded; when no rows have ever been
    recorded the output shows an empty ``sellers`` list.
    """
    from wb.auth.profiles import ProfileStore
    from wb.core.config import Settings
    from wb.core.endpoint_budget import EndpointBudget

    renderer = get_renderer(ctx)
    settings = Settings()
    settings.ensure_config_dir()

    profile_hint = get_profile(ctx)
    store = ProfileStore(settings.config_dir)
    try:
        active_profile = profile_hint or store.active_profile_name
    except Exception:  # noqa: BLE001 — no profile registered yet
        active_profile = profile_hint or settings.active_profile

    db_path = settings.config_dir / RATE_LIMIT_DB_FILE
    budget = EndpointBudget(db_path=db_path)
    rows = budget.read_all()

    now = time.time()
    sellers = _group_rows_by_seller(rows, now)

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


def _group_rows_by_seller(rows, now: float) -> list[dict]:
    """Group budget rows by seller, then token, then endpoint.

    Args:
        rows: Sequence of :class:`BudgetRow` from
            :meth:`EndpointBudget.read_all`.
        now: Wall-clock epoch seconds; used to compute ``reset_in_s`` and
            ``last_seen_ago_s`` once for the whole snapshot.

    Returns:
        List of ``{seller_id, tokens: [...]}`` dicts. Sellers and tokens
        are alphabetically ordered for stable diffing; endpoints within a
        token are ordered by reset deadline (locked endpoints first).
    """
    by_seller: dict[str | None, dict[str, list]] = {}
    for row in rows:
        token_endpoints = by_seller.setdefault(row.seller_id, {})
        token_endpoints.setdefault(row.token_fp, []).append(row)

    sellers: list[dict] = []
    for seller_id in sorted(by_seller, key=_seller_sort_key):
        tokens_list = []
        for token_fp in sorted(by_seller[seller_id]):
            endpoints = [
                _endpoint_payload(r, now) for r in by_seller[seller_id][token_fp]
            ]
            endpoints.sort(key=lambda e: (not e['locked'], e['reset_in_s']))
            tokens_list.append({'token_fp': token_fp, 'endpoints': endpoints})
        sellers.append({'seller_id': seller_id, 'tokens': tokens_list})
    return sellers


def _seller_sort_key(seller_id: str | None) -> tuple[int, str]:
    """Sort known sellers before unknowns; alphabetical within each group."""
    return (1, '') if seller_id is None else (0, seller_id)


def _endpoint_payload(row, now: float) -> dict:
    """Convert one :class:`BudgetRow` into the JSON payload shape."""
    reset_in = max(0.0, row.reset_at - now)
    last_seen_ago = max(0.0, now - row.last_seen)
    locked = (
        row.remaining is not None
        and row.remaining == 0
        and row.reset_at > now
    )
    return {
        'endpoint': row.endpoint,
        'remaining': row.remaining,
        'bucket_limit': row.bucket_limit,
        'reset_in_s': round(reset_in, 1),
        'last_seen_ago_s': round(last_seen_ago, 1),
        'locked': locked,
    }


def _render_status_table(active_profile: str, sellers: list[dict]) -> None:
    """Print the human-readable view of ``rate status``."""
    from wb.core.output import render_table

    typer.echo(f'Profile : {active_profile}')
    if not sellers:
        typer.echo('')
        typer.echo('No rate-limit state recorded yet.')
        return

    for seller in sellers:
        sid = seller['seller_id'] or '(unknown sid)'
        tokens = seller['tokens']
        typer.echo('')
        typer.echo(f'Seller {sid} ({len(tokens)} token{"s" if len(tokens) != 1 else ""})')
        for token in tokens:
            rows = [
                [
                    ep['endpoint'],
                    _format_remaining(ep),
                    f"{ep['reset_in_s']:.0f}",
                    f"{ep['last_seen_ago_s']:.0f}",
                    'LOCKED' if ep['locked'] else '',
                ]
                for ep in token['endpoints']
            ]
            render_table(
                ['Endpoint', 'Remaining', 'Reset (s)', 'Last seen (s ago)', 'State'],
                rows,
                title=f'Token {token["token_fp"]}',
            )


def _format_remaining(ep: dict) -> str:
    """Render ``remaining/limit`` with sensible fallbacks for missing values."""
    remaining = ep['remaining']
    bucket_limit = ep['bucket_limit']
    left = '?' if remaining is None else str(remaining)
    right = '?' if bucket_limit is None else str(bucket_limit)
    return f'{left}/{right}'


def _resolve_any_token(settings, profile_store_cls, profile_hint: str | None) -> str:
    """Best-effort token lookup using the standard priority chain.

    Priority: env / .env → promotion token in the named (or active) profile.
    Returns an empty string when no token is available — the command still
    runs, just without a cooldown reading.
    """
    if settings.api_token:
        return settings.api_token
    try:
        profile = profile_store_cls(settings.config_dir).get_profile(profile_hint)
        return profile.get_token('promotion')
    except Exception:  # noqa: BLE001
        return ''


@rate_app.command('probe')
def rate_probe(ctx: typer.Context) -> None:
    """Single-call probe to refresh per-endpoint cooldown visibility.

    Makes at most one GET to ``/adv/v1/balance`` (cheapest per-seller
    endpoint) and interprets the result through ``EndpointBudget``:

    - Pre-flight: read the budget row for ``(token_fp, /adv/v1/balance)``.
      When ``remaining == 0`` and ``reset_at`` is still in the future,
      skip the network entirely and report the lock state. Other
      endpoints stay reachable — the per-endpoint scope is the whole
      point of the R-1..R-4 redesign.
    - On HTTP 200, ``EndpointBudget.observe_headers`` records the live
      ``X-Ratelimit-*`` values and the probe reports
      ``x-ratelimit-remaining`` so agents can see how close we are to
      a trip.
    - On HTTP 429, the same ``observe_headers`` call writes the
      ``reset_at`` deadline; this command exits with ``RATE_LIMITED``
      and future ``wb`` calls to the same endpoint will see the lock
      via :meth:`EndpointBudget.reserve`.
    """
    import httpx

    from wb.auth.profiles import ProfileStore
    from wb.core.config import Settings
    from wb.core.endpoint_budget import EndpointBudget
    from wb.core.rate_limiter import compute_token_fingerprint, extract_seller_id

    renderer = get_renderer(ctx)
    settings = Settings()
    settings.ensure_config_dir()

    profile_hint = get_profile(ctx)
    store = ProfileStore(settings.config_dir)
    try:
        active_profile = profile_hint or store.active_profile_name
    except Exception:  # noqa: BLE001
        active_profile = profile_hint or settings.active_profile

    token = _resolve_any_token(settings, ProfileStore, profile_hint)
    if not token:
        _emit_probe_result(
            renderer, ctx,
            {
                'profile': active_profile,
                'seller_id': None,
                'token_fingerprint': '',
                'outcome': 'no-token',
                'locked': False,
                'cooldown_seconds': 0.0,
                'calls_remaining': None,
            },
            exit_code=7,
        )
        return

    token_fp = compute_token_fingerprint(token)
    seller_id = extract_seller_id(token)
    db_path = settings.config_dir / RATE_LIMIT_DB_FILE
    budget = EndpointBudget(db_path=db_path)

    # Pre-flight: skip the network if WB has already told us this
    # endpoint is locked for the current token.
    cooldown = _compute_endpoint_cooldown(budget, token_fp, _PROBE_ENDPOINT)
    if cooldown > 0:
        _emit_probe_result(
            renderer, ctx,
            {
                'profile': active_profile,
                'seller_id': seller_id,
                'token_fingerprint': token_fp,
                'outcome': 'lock-active',
                'locked': True,
                'cooldown_seconds': round(cooldown, 1),
                'calls_remaining': 0,
            },
            exit_code=5,
        )
        return

    # Make the one controlled request.
    try:
        with httpx.Client(timeout=_PROBE_TIMEOUT_SECONDS) as client:
            response = client.get(
                f'{PROMOTION_BASE_URL}{_PROBE_ENDPOINT}',
                headers={
                    'Authorization': token,
                    'Accept': 'application/json',
                },
            )
    except httpx.RequestError as exc:
        _emit_probe_result(
            renderer, ctx,
            {
                'profile': active_profile,
                'seller_id': seller_id,
                'token_fingerprint': token_fp,
                'outcome': 'network-error',
                'locked': False,
                'cooldown_seconds': 0.0,
                'calls_remaining': None,
                'error': str(exc),
            },
            exit_code=6,
        )
        return

    # Always feed the response headers back into the budget — both 200s
    # (refreshes ``remaining``) and 429s (records ``reset_at``).
    budget.observe_headers(
        token_fp, _PROBE_ENDPOINT, response.headers, seller_id=seller_id,
    )

    payload = {
        'profile': active_profile,
        'seller_id': seller_id,
        'token_fingerprint': token_fp,
        'http_status': response.status_code,
    }

    if response.status_code == 429:
        from wb.core.endpoint_budget import parse_rate_limit_wait
        cooldown_seconds = parse_rate_limit_wait(response.headers) or 0.0
        payload.update({
            'outcome': '429',
            'locked': True,
            'cooldown_seconds': round(cooldown_seconds, 1),
            'calls_remaining': 0,
        })
        _emit_probe_result(renderer, ctx, payload, exit_code=5)
        return

    if response.status_code >= 400:
        payload.update({
            'outcome': 'error',
            'locked': False,
            'cooldown_seconds': 0.0,
            'calls_remaining': None,
            'error_body': response.text[:200],
        })
        _emit_probe_result(renderer, ctx, payload, exit_code=6)
        return

    # 2xx — happy path. ``x-ratelimit-remaining`` may or may not be present.
    remaining_raw = response.headers.get('x-ratelimit-remaining')
    calls_remaining: int | None = None
    if remaining_raw is not None:
        try:
            calls_remaining = int(remaining_raw)
        except ValueError:
            calls_remaining = None

    payload.update({
        'outcome': 'ok',
        'locked': False,
        'cooldown_seconds': 0.0,
        'calls_remaining': calls_remaining,
    })
    _emit_probe_result(renderer, ctx, payload, exit_code=0)


def _compute_endpoint_cooldown(
        budget,
        token_fp: str,
        endpoint: str,
) -> float:
    """Return seconds remaining on the endpoint cooldown, or 0 if clear.

    Walks :meth:`EndpointBudget.read_all` once and filters in Python —
    cheap because the table is small (one row per touched endpoint per
    token) and this command is only ever called interactively.

    Args:
        budget: Live :class:`EndpointBudget` instance.
        token_fp: Token fingerprint for the row's primary key.
        endpoint: API endpoint path constant.

    Returns:
        Positive float seconds remaining when ``remaining == 0`` and
        ``reset_at > now``; ``0.0`` otherwise.
    """
    now = time.time()
    for row in budget.read_all():
        if row.token_fp != token_fp or row.endpoint != endpoint:
            continue
        if row.remaining == 0 and row.reset_at > now:
            return row.reset_at - now
        return 0.0
    return 0.0


def _emit_probe_result(
        renderer,
        ctx: typer.Context,
        payload: dict,
        *,
        exit_code: int,
) -> None:
    """Render probe output then exit with the requested code."""
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
    else:
        typer.echo(f"Profile            : {payload.get('profile', '')}")
        typer.echo(f"Seller             : {payload.get('seller_id') or '(unknown sid)'}")
        typer.echo(f"Token fingerprint  : {payload.get('token_fingerprint') or '(none)'}")
        typer.echo(f"Outcome            : {payload.get('outcome', 'unknown')}")
        if payload.get('locked'):
            typer.echo(
                f"Endpoint cooldown  : LOCKED — {payload['cooldown_seconds']:.0f}s remaining"
            )
        else:
            typer.echo('Endpoint cooldown  : clear')
        if payload.get('calls_remaining') is not None:
            typer.echo(f"Calls remaining    : {payload['calls_remaining']}")
        if 'error' in payload:
            typer.echo(f"Error              : {payload['error']}")
        if 'error_body' in payload:
            typer.echo(f"Error body         : {payload['error_body']}")

    if exit_code != 0:
        raise typer.Exit(exit_code)
