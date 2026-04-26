"""CLI diagnostic command for rate-limit state (I-13, R-3).

``wb rate status`` is a pure read of the ``~/.wb-cli/rate_limits.db``
``endpoint_budget`` table populated by every WB response's
``X-Ratelimit-*`` headers (see :mod:`wb.core.endpoint_budget`). Output
is grouped by plaintext seller_id, then by token fingerprint, then by
endpoint, so every operator sees every active cooldown regardless of
which token their shell is currently configured with.

R-5 removed the previously-shipped ``wb rate probe`` command — it was
vestigial after the R-1..R-4 header-driven redesign. Use
:command:`wb auth ping` to verify connectivity and :command:`wb rate
status` to read the live budget; any real WB call refreshes the budget
naturally through ``EndpointBudget.observe(...)``.
"""

from __future__ import annotations

import json
import time

import typer

from wb.cli._helpers import get_profile, get_renderer
from wb.core.constants import RATE_LIMIT_DB_FILE

__all__ = ['rate_app']

rate_app = typer.Typer(
    help='Local rate-limit diagnostic',
    no_args_is_help=True,
)


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
    fp_to_type = _build_fp_to_token_type(store)

    now = time.time()
    sellers = _group_rows_by_seller(rows, now, fp_to_type)

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


def _build_fp_to_token_type(store) -> dict[str, str]:
    """Map known token fingerprints to the token_type from their profile.

    Walks the local :class:`ProfileStore` once, computes the fingerprint
    for every category token in every profile, and emits
    ``{token_fp: token_type}``. Used by ``rate status`` to annotate
    budget rows with the type WB will enforce — rows whose fingerprint
    matches no local profile carry a ``None`` type and the renderer
    shows ``unknown``.
    """
    from wb.core.rate_limiter import compute_token_fingerprint

    mapping: dict[str, str] = {}
    try:
        profiles = store.list_profiles()
    except Exception:  # noqa: BLE001 — profiles file missing / corrupt
        return mapping
    for profile in profiles:
        for token in profile.tokens.values():
            if token:
                mapping[compute_token_fingerprint(token)] = profile.token_type
    return mapping


def _group_rows_by_seller(
        rows,
        now: float,
        fp_to_type: dict[str, str] | None = None,
) -> list[dict]:
    """Group budget rows by seller, then token, then endpoint.

    Args:
        rows: Sequence of :class:`BudgetRow` from
            :meth:`EndpointBudget.read_all`.
        now: Wall-clock epoch seconds; used to compute ``reset_in_s`` and
            ``last_seen_ago_s`` once for the whole snapshot.
        fp_to_type: Optional ``{token_fp: token_type}`` map — usually
            built by :func:`_build_fp_to_token_type`. Tokens not in the
            map render with ``token_type: null``.

    Returns:
        List of ``{seller_id, tokens: [{token_fp, token_type, endpoints: [...]}]}``
        dicts. Sellers and tokens are alphabetically ordered for stable
        diffing; endpoints within a token are ordered by reset deadline
        (locked endpoints first).
    """
    fp_to_type = fp_to_type or {}
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
            tokens_list.append({
                'token_fp': token_fp,
                'token_type': fp_to_type.get(token_fp),
                'endpoints': endpoints,
            })
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
            ttype = token.get('token_type') or 'unknown'
            render_table(
                ['Endpoint', 'Remaining', 'Reset (s)', 'Last seen (s ago)', 'State'],
                rows,
                title=f'Token {token["token_fp"]} (type: {ttype})',
            )


def _format_remaining(ep: dict) -> str:
    """Render ``remaining/limit`` with sensible fallbacks for missing values."""
    remaining = ep['remaining']
    bucket_limit = ep['bucket_limit']
    left = '?' if remaining is None else str(remaining)
    right = '?' if bucket_limit is None else str(bucket_limit)
    return f'{left}/{right}'


