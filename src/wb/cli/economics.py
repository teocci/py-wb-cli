"""CLI commands for per-product unit economics (I-26).

``wb economics product`` joins the warehouse-remains stock snapshot with the
finance settlement detail rows to answer, per product: how much it costs to
sell on WB, whether it is profitable, and how much stock is left.

Distinct from sibling money commands:

- ``wb budget balance``   — ad-deposit balance (promotion API).
- ``wb finance …``        — raw settlement statements (finance API).
- ``wb economics …``      — the derived per-product join (this module).

Branches strictly on ``renderer.is_json`` per CLAUDE.md: JSON emits a list of
dicts (with ``--fields`` / ``--compact`` support), table mode a lean
``list[list[str]]`` plus a period-reconciliation footer.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import typer

from wb.cli._helpers import get_fields, get_profile, get_renderer
from wb.cli.finance import _validate_date_range, _validate_period
from wb.core.constants import ECONOMICS_DEFAULT_MIN_STOCK, ExitCode
from wb.core.exceptions import WbCliError
from wb.core.output import render_table

__all__ = ['economics_app']

economics_app = typer.Typer(
    help='Per-product unit economics: stock + WB fees + margin.',
    no_args_is_help=True,
)

_VALID_SCOPES = ('in-stock', 'sold', 'all')

_TABLE_HEADERS = [
    'nm_id', 'vendor', 'in_stock', 'sold', 'avg_price',
    'wb_cost/sold', 'margin/sold', 'margin%', 'net/sold',
]

_EXACT_NOTE = (
    'Exact mode: per-SKU costs only (commission/acquiring/logistics); margin is '
    'an upper bound. Period storage+deductions are in the summary below; pass '
    '--apportion to fold them into each row (estimate).'
)
_APPORTION_NOTE = (
    'Apportioned: period storage+deductions spread pro-rata by revenue '
    '(estimates). Stock is a current snapshot vs a historical period; COGS not '
    'from WB.'
)


def _validate_scope(scope: str) -> str:
    """Return ``scope`` when valid; raise BadParameter otherwise.

    Args:
        scope: User-supplied scope value.

    Raises:
        typer.BadParameter: When not one of the valid scopes.
    """
    if scope not in _VALID_SCOPES:
        raise typer.BadParameter(
            f'--scope must be one of {", ".join(_VALID_SCOPES)}; got {scope!r}.'
        )
    return scope


def _load_cogs_map(path: str | None) -> dict[int, float] | None:
    """Parse a COGS JSON file ``{nm_id: rub}`` into a typed map.

    Args:
        path: Path to the JSON file, or None when not supplied.

    Returns:
        Map of nmId → cost, or None when no file was given.

    Raises:
        typer.BadParameter: On a missing file, bad JSON, or invalid entries.
    """
    if path is None:
        return None
    try:
        raw = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(f'--cogs-file {path!r}: {exc}') from exc
    if not isinstance(raw, dict):
        raise typer.BadParameter('--cogs-file must contain a JSON object.')
    return {k: v for k, v in (_cogs_entry(path, k, v) for k, v in raw.items())}


def _cogs_entry(path: str, key: str, value: object) -> tuple[int, float]:
    """Validate and coerce a single COGS entry to ``(nm_id, cost)``."""
    try:
        nm_id, cost = int(key), float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise typer.BadParameter(
            f'--cogs-file {path!r}: invalid entry {key!r}: {value!r}.'
        ) from exc
    if cost < 0:
        raise typer.BadParameter(
            f'--cogs-file {path!r}: negative cost for {nm_id}: {cost}.'
        )
    return nm_id, cost


def _service(profile: str | None):
    """Lazy-import factory to keep CLI startup fast."""
    from wb.services._factory import create_economics_service
    return create_economics_service(profile)


def _table_rows(results: list) -> list[list[str]]:
    """Project economics rows to lean table cells."""
    return [
        [
            str(e.nm_id), e.vendor_code, str(e.units_in_stock), str(e.units_sold),
            f'{e.avg_sale_price:.2f}', _cell(e.wb_cost_per_sold),
            _cell(e.margin_per_sold), _cell(e.margin_pct), _cell(e.net_profit_per_sold),
        ]
        for e in results
    ]


def _cell(value: float | None) -> str:
    """Format an optional float for a table cell ('—' when None)."""
    return '—' if value is None else f'{value:.2f}'


def _echo_period(period) -> None:
    """Print the period reconciliation as a footer (non-JSON mode)."""
    typer.echo(
        f'\nPeriod — revenue {period.revenue:.2f} | gross_payout '
        f'{period.gross_payout:.2f} | logistics {period.logistics:.2f} | '
        f'storage {period.storage:.2f} | deductions {period.deductions:.2f} | '
        f'bank_payment {period.bank_payment:.2f} | wb_cost {period.wb_cost_total:.2f} '
        f'({period.wb_cost_pct:.1f}%)'
    )


@economics_app.command('product')
def economics_product(
        ctx: typer.Context,
        date_from: str = typer.Option(
            ..., '--from', help='Reporting period start (YYYY-MM-DD).',
        ),
        date_to: str = typer.Option(
            ..., '--to', help='Reporting period end (YYYY-MM-DD).',
        ),
        period_opt: str | None = typer.Option(
            None, '--period', help='Report periodicity: weekly (default) or daily.',
        ),
        scope: str = typer.Option(
            'in-stock', '--scope',
            help='Which products: in-stock (default), sold, or all.',
        ),
        apportion: bool = typer.Option(
            False, '--apportion/--no-apportion',
            help='Fold period storage+deductions into each row pro-rata (estimate).',
        ),
        cogs_file: str | None = typer.Option(
            None, '--cogs-file',
            help='JSON {nm_id: rub} of unit cost for true net-profit columns.',
        ),
        min_stock: int = typer.Option(
            ECONOMICS_DEFAULT_MIN_STOCK, '--min-stock',
            help='Minimum total stock to qualify under the in-stock scope.',
        ),
        fetch_all: bool = typer.Option(
            True, '--all/--no-all',
            help='Exhaust the finance cursor (throttled 1 req/min; minutes for big sellers).',
        ),
) -> None:
    """Per-product unit economics over a reporting period.

    Joins current warehouse stock with finance settlement costs. For each
    product it reports units in stock / sold, average sale price, the WB cost
    breakdown, gross/net payout, and per-unit margin.

    WB's settlement identity is
    ``bank_payment = gross_payout - logistics - storage - deductions``. Two cost
    modes:

    - default (exact): only costs WB ties to a specific nmId (commission,
      acquiring, logistics). No estimates; margin is an upper bound. Period
      storage+deductions appear in the summary footer.
    - ``--apportion``: folds period storage+deductions into each row pro-rata
      by revenue (estimate); margin becomes all-in and reconciles to WB's bank
      payment.

    ``--cogs-file`` adds true net profit per sold unit. Requires analytics +
    finance tokens on the profile.

    Examples:
        wb economics product --from 2026-05-01 --to 2026-05-31
        wb --json economics product --from 2026-05-01 --to 2026-05-31 --apportion
        wb economics product --from 2026-05-01 --to 2026-05-31 --cogs-file cogs.json
    """
    renderer = get_renderer(ctx)
    _validate_date_range(date_from, date_to)
    period_opt = _validate_period(period_opt)
    scope = _validate_scope(scope)
    cogs_map = _load_cogs_map(cogs_file)

    try:
        results, period = _service(get_profile(ctx)).get_product_economics(
            date_from=date_from, date_to=date_to, period=period_opt,
            scope=scope, apportion=apportion, cogs_map=cogs_map,
            min_stock=min_stock,
            use_cache=not (ctx.obj or {}).get('no_cache', False),
            fetch_all=fetch_all,
        )
    except WbCliError as exc:
        renderer.error(str(exc))
        raise typer.Exit(code=exc.exit_code) from exc

    if renderer.is_json:
        renderer.display([asdict(e) for e in results], fields=get_fields(ctx))
        return

    if not results:
        typer.echo(f'No products for {date_from} … {date_to} (scope={scope}).')
        _echo_period(period)
        return

    mode = 'apportioned' if apportion else 'exact'
    render_table(
        _TABLE_HEADERS, _table_rows(results),
        title=f'Unit economics ({mode}) — {date_from} … {date_to} ({len(results)} products)',
    )
    _echo_period(period)
    typer.echo(_APPORTION_NOTE if apportion else _EXACT_NOTE, err=True)
