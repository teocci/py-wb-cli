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
from wb.core.constants import RATE_LIMIT_DB_FILE

__all__ = ['rate_app']

rate_app = typer.Typer(
    help='Local rate-limit diagnostic (read-only; no network calls)',
    no_args_is_help=True,
)


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
