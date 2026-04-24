"""CLI diagnostic commands for rate-limit state (I-13).

Reads ``~/.wb-cli/rate_limits.db`` only — no network calls. Intended for
post-429 triage ("am I locked, and for how long?") and for agents to
check before planning a burst of calls.
"""

from __future__ import annotations

import json
import sqlite3
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
    """Show current seller cooldown and recent endpoint activity.

    Reads the shared ``rate_limits.db`` file only. Safe to call without
    any API token loaded; when no token is available the output shows an
    empty seller fingerprint and skips the cooldown section.
    """
    from wb.auth.profiles import ProfileStore
    from wb.core.config import Settings
    from wb.core.rate_limiter import (
        SellerCooldownLock,
        compute_seller_fingerprint,
        compute_token_fingerprint,
    )

    renderer = get_renderer(ctx)
    settings = Settings()
    settings.ensure_config_dir()

    profile_hint = get_profile(ctx)
    store = ProfileStore(settings.config_dir)
    try:
        active_profile = profile_hint or store.active_profile_name
    except Exception:  # noqa: BLE001 — no profile registered yet
        active_profile = profile_hint or settings.active_profile

    token = _resolve_any_token(settings, ProfileStore, profile_hint)
    seller_fp = compute_seller_fingerprint(token) if token else ''
    token_fp = compute_token_fingerprint(token) if token else ''

    db_path = settings.config_dir / RATE_LIMIT_DB_FILE

    # Seller cooldown (F-13 lock)
    remaining = 0.0
    if token and db_path.exists():
        lock = SellerCooldownLock(db_path=db_path)
        r = lock.read_remaining(seller_fp)
        if r is not None:
            remaining = r

    # Recent per-endpoint activity (last 5 min, across all tokens — a
    # broader view lets operators see cross-profile pressure without
    # needing to flip profiles)
    activity = _recent_activity(db_path)

    payload = {
        'profile': active_profile,
        'seller_fingerprint': seller_fp,
        'token_fingerprint': token_fp,
        'seller_cooldown_seconds': round(remaining, 1),
        'locked': remaining > 0,
        'endpoint_activity_5min': activity,
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

    from wb.core.output import render_table

    typer.echo(f"Profile            : {active_profile}")
    typer.echo(f"Seller fingerprint : {seller_fp or '(no token)'}")
    lock_line = (
        f"LOCKED — {remaining:.0f}s remaining"
        if remaining > 0
        else 'clear'
    )
    typer.echo(f"Seller cooldown    : {lock_line}")
    typer.echo('')

    if not activity:
        typer.echo('No endpoint activity recorded in the last 5 minutes.')
        return

    rows = [
        [row['endpoint'], str(row['count']), f"{row['newest_age_s']:.0f}"]
        for row in activity
    ]
    render_table(
        ['Endpoint', 'Acquires (5m)', 'Newest age (s)'],
        rows,
        title='Recent rate-limiter activity',
    )


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
    """Single-call probe to refresh cooldown visibility safely.

    Makes exactly one GET to ``/adv/v1/balance`` (1/s documented limit,
    lightweight response) and interprets the result:

    - If the F-13 cooldown lock is already active, skip the network call
      entirely and report the lock state. Same safety as ``rate status``.
    - On HTTP 200, read ``x-ratelimit-remaining`` and display how many
      calls are safe before throttling. No side-effects.
    - On HTTP 429, read ``x-ratelimit-reset``, persist it to the lock,
      and exit ``RATE_LIMITED``. Future ``wb`` calls short-circuit
      through the lock until the deadline passes.
    """
    import httpx

    from wb.auth.profiles import ProfileStore
    from wb.core.config import Settings
    from wb.core.rate_limiter import (
        SellerCooldownLock,
        compute_seller_fingerprint,
        compute_token_fingerprint,
    )

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
                'seller_fingerprint': '',
                'outcome': 'no-token',
                'locked': False,
                'cooldown_seconds': 0.0,
                'calls_remaining': None,
            },
            exit_code=7,
        )
        return

    seller_fp = compute_seller_fingerprint(token)
    token_fp = compute_token_fingerprint(token)
    db_path = settings.config_dir / RATE_LIMIT_DB_FILE
    lock = SellerCooldownLock(db_path=db_path)

    # Pre-flight: respect the lock, skip the network entirely if locked.
    existing = lock.read_remaining(seller_fp)
    if existing is not None and existing > 0:
        _emit_probe_result(
            renderer, ctx,
            {
                'profile': active_profile,
                'seller_fingerprint': seller_fp,
                'token_fingerprint': token_fp,
                'outcome': 'lock-active',
                'locked': True,
                'cooldown_seconds': round(existing, 1),
                'calls_remaining': None,
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
                'seller_fingerprint': seller_fp,
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

    payload = {
        'profile': active_profile,
        'seller_fingerprint': seller_fp,
        'token_fingerprint': token_fp,
        'http_status': response.status_code,
    }

    if response.status_code == 429:
        from wb.client.http import _parse_rate_limit_reset
        reset_seconds = _parse_rate_limit_reset(response) or 0.0
        if reset_seconds > 0:
            lock.record(seller_fp, reset_seconds)
        payload.update({
            'outcome': '429',
            'locked': True,
            'cooldown_seconds': round(reset_seconds, 1),
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

    # 2xx — happy path. `x-ratelimit-remaining` may or may not be present.
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
        typer.echo(f"Seller fingerprint : {payload.get('seller_fingerprint', '(none)')}")
        typer.echo(f"Outcome            : {payload.get('outcome', 'unknown')}")
        if payload.get('locked'):
            typer.echo(
                f"Seller cooldown    : LOCKED — {payload['cooldown_seconds']:.0f}s remaining"
            )
        else:
            typer.echo('Seller cooldown    : clear')
        if payload.get('calls_remaining') is not None:
            typer.echo(f"Calls remaining    : {payload['calls_remaining']}")
        if 'error' in payload:
            typer.echo(f"Error              : {payload['error']}")
        if 'error_body' in payload:
            typer.echo(f"Error body         : {payload['error_body']}")

    if exit_code != 0:
        raise typer.Exit(exit_code)


def _recent_activity(db_path) -> list[dict]:
    """Summarise `rate_limit_log` rows in the last 5 minutes.

    Returns a list of dicts ordered by newest activity first. Empty when
    the DB doesn't exist, has no recent rows, or fails to open.
    """
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
    except sqlite3.Error:
        return []
    try:
        now = time.time()
        cutoff = now - 300.0
        rows = conn.execute(
            'SELECT endpoint, COUNT(*) AS n, MAX(ts) AS newest '
            'FROM rate_limit_log WHERE ts >= ? '
            'GROUP BY endpoint ORDER BY newest DESC',
            (cutoff,),
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    return [
        {
            'endpoint': endpoint,
            'count': int(count),
            'newest_age_s': round(now - newest, 1),
        }
        for endpoint, count, newest in rows
    ]
