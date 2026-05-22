"""CLI commands for seller portal operations."""

from __future__ import annotations

import typer

from wb.cli._helpers import get_profile, get_renderer
from wb.core.constants import ExitCode
from wb.core.exceptions import WbCliError
from wb.core.output import _stdout_console
from wb.domain.enums import BidType, PaymentType

portal_app = typer.Typer(
    help=(
        'UNOFFICIAL seller-portal scraping. Reaches data that the public '
        'WB API does not expose (e.g. detailed product cards) by replaying '
        'a logged-in manager browser session. No public documentation '
        'covers these endpoints — they may change without notice. Requires '
        '`wb auth login-portal` first to store the cookie + authorizev3 '
        'credentials. For documented operations, prefer the official '
        '`wb campaign`, `wb stats`, `wb analytics`, etc. command trees.'
    ),
    no_args_is_help=True,
)

# F-21 — map BidType enum value → integer expected by the portal endpoints.
# WB's "new campaign typology": 1 = manual, 2 = unified.
_BID_TYPE_INT = {
    BidType.MANUAL.value: 1,
    BidType.UNIFIED.value: 2,
}


def _get_portal_client():
    """Create a PortalClient from current settings."""
    from wb.services._factory import create_portal_client
    return create_portal_client()


@portal_app.command('products')
def portal_products(
        ctx: typer.Context,
        limit: int = typer.Option(20, '--limit', '-n', help='Number of products'),
        search: str = typer.Option('', '--search', '-s', help='Search query'),
) -> None:
    """List product cards via the UNOFFICIAL portal ``tableListv6`` endpoint.

    Returns richer per-product data (vendor codes, stocks, ratings,
    feedback counts) than the public WB API exposes. Used when an agent
    or workflow needs portal-only fields the documented endpoints do
    not provide.
    """
    from wb.domain.models import PortalProductCard

    json_output = ctx.obj.get('json_output', False) if ctx.obj else False

    try:
        client = _get_portal_client()
    except WbCliError as exc:
        typer.secho(f'Error: {exc}', fg=typer.colors.RED, err=True)
        raise typer.Exit(code=ExitCode.CONFIG_ERROR) from exc

    try:
        raw_cards = client.list_products(page_size=limit, search=search)
    except WbCliError as exc:
        typer.secho(f'Portal error: {exc}', fg=typer.colors.RED, err=True)
        raise typer.Exit(code=ExitCode.API_ERROR) from exc

    cards = [PortalProductCard.from_portal(c) for c in raw_cards]

    if json_output:
        import json
        from dataclasses import asdict
        typer.echo(json.dumps([asdict(c) for c in cards], indent=2, ensure_ascii=False))
        return

    if not cards:
        typer.echo('No products found.')
        return

    from rich.table import Table

    table = Table(title=f'Products ({len(cards)})')
    table.add_column('nmID', style='cyan', justify='right')
    table.add_column('Vendor', style='dim')
    table.add_column('Title', max_width=40)
    table.add_column('Stock', justify='right')
    table.add_column('Price', justify='right', style='green')
    table.add_column('Rating', justify='center')
    table.add_column('Reviews', justify='right')

    for c in cards:
        table.add_row(
            str(c.nm_id),
            c.vendor_code,
            c.title[:40],
            str(c.stocks),
            f'{c.price}',
            f'{c.feedback_rating:.1f}',
            str(c.feedback_count),
        )

    _stdout_console.print(table)


@portal_app.command('bids')
def portal_bids(
        ctx: typer.Context,
        campaign_id: int | None = typer.Option(
            None, '--campaign', '-c',
            help='Campaign ID — auto-discovers NMs, payment_type, and bid_type from /api/advert/v2/adverts.',
        ),
        nm_ids: list[int] | None = typer.Option(
            None, '--nm',
            help='Explicit NM IDs (repeatable). Overrides --campaign NM discovery.',
        ),
        payment_type: str | None = typer.Option(
            None, '--payment-type',
            help='cpm or cpc. Auto-picked from campaign settings when --campaign is given.',
        ),
        bid_type: str | None = typer.Option(
            None, '--bid-type',
            help='manual or unified. Defaults to manual when no campaign is given.',
        ),
) -> None:
    """Fetch CPC/CPM bid recommendations from the UNOFFICIAL portal.

    Queries ``cmp.wildberries.ru/api/v1/advert/bids[-cpc]`` — the portal's
    own bid-suggestion endpoint, which exposes a per-tier reach forecast
    (max/medium/min reach × bid/budget/shows/clicks) that the official
    API does not surface. Required for CPC campaigns because the official
    ``wb bid recommend`` is CPM-only.
    """
    from wb.domain.models import parse_portal_bids_response

    renderer = get_renderer(ctx)
    profile = get_profile(ctx)

    try:
        resolved_nm_ids, resolved_payment_type, resolved_bid_type_int = (
            _resolve_bids_inputs(
                profile, campaign_id, nm_ids, payment_type, bid_type,
            )
        )
    except _PortalBidsValidationError as exc:
        renderer.error(str(exc))
        raise typer.Exit(ExitCode.VALIDATION_ERROR) from exc

    try:
        client = _get_portal_client()
    except WbCliError as exc:
        typer.secho(f'Error: {exc}', fg=typer.colors.RED, err=True)
        raise typer.Exit(code=ExitCode.CONFIG_ERROR) from exc

    try:
        raw = client.fetch_bid_recommendations(
            resolved_nm_ids, resolved_payment_type, resolved_bid_type_int,
        )
    except WbCliError as exc:
        typer.secho(f'Portal error: {exc}', fg=typer.colors.RED, err=True)
        raise typer.Exit(code=ExitCode.API_ERROR) from exc

    records = parse_portal_bids_response(raw, payment_type=resolved_payment_type)

    if renderer.is_json:
        import json
        from dataclasses import asdict
        typer.echo(json.dumps(
            [asdict(r) for r in records], indent=2, ensure_ascii=False,
        ))
        return

    if not records:
        renderer.success('No bid recommendations returned.')
        return

    _render_bids_table(records)


class _PortalBidsValidationError(Exception):
    """Internal — raised to flip the CLI into a VALIDATION_ERROR exit."""


def _resolve_bids_inputs(
        profile: str | None,
        campaign_id: int | None,
        nm_ids: list[int] | None,
        payment_type: str | None,
        bid_type: str | None,
) -> tuple[list[int], str, int]:
    """Resolve effective NMs, payment_type, and bid_type for the portal call.

    Args:
        profile: Profile name (forwarded to the promotion-client factory
            when campaign info is fetched).
        campaign_id: Optional campaign ID to read defaults from.
        nm_ids: Optional explicit NM IDs.
        payment_type: Optional 'cpm'/'cpc' override.
        bid_type: Optional 'manual'/'unified' override.

    Returns:
        Tuple of (nm_ids, payment_type_value, bid_type_int).

    Raises:
        _PortalBidsValidationError: When inputs are insufficient.
    """
    if not nm_ids and campaign_id is None:
        raise _PortalBidsValidationError(
            'Provide --campaign or one or more --nm values'
        )

    campaign: dict | None = None
    if campaign_id is not None and (not nm_ids or not payment_type or not bid_type):
        campaign = _fetch_campaign_settings(profile, campaign_id)

    effective_nm_ids = list(nm_ids) if nm_ids else _campaign_nm_ids(campaign, campaign_id)
    if not effective_nm_ids:
        raise _PortalBidsValidationError(
            f'No NMs to query (campaign {campaign_id} has no items)'
        )

    effective_payment_type = (
        _normalize_payment_type(payment_type)
        if payment_type
        else _campaign_payment_type(campaign)
    )
    if not effective_payment_type:
        raise _PortalBidsValidationError(
            'Cannot determine payment_type — pass --payment-type cpm|cpc'
        )

    effective_bid_type_int = (
        _normalize_bid_type(bid_type)
        if bid_type
        else _campaign_bid_type_int(campaign)
    )
    return effective_nm_ids, effective_payment_type, effective_bid_type_int


def _fetch_campaign_settings(profile: str | None, campaign_id: int) -> dict:
    """Fetch raw /api/advert/v2/adverts entry for a campaign."""
    from wb.services._factory import create_promotion_client
    promotion = create_promotion_client(profile)
    campaign = promotion.get_campaign(campaign_id)
    if not isinstance(campaign, dict):
        raise _PortalBidsValidationError(f'Campaign {campaign_id} not found')
    return campaign


def _campaign_nm_ids(campaign: dict | None, campaign_id: int | None) -> list[int]:
    if not isinstance(campaign, dict):
        return []
    nm_settings = campaign.get('nm_settings') or []
    return [nm['nm_id'] for nm in nm_settings if isinstance(nm, dict) and 'nm_id' in nm]


def _campaign_payment_type(campaign: dict | None) -> str | None:
    if not isinstance(campaign, dict):
        return None
    settings = campaign.get('settings') or {}
    value = settings.get('payment_type')
    return _normalize_payment_type(value) if value else None


def _campaign_bid_type_int(campaign: dict | None) -> int:
    if isinstance(campaign, dict):
        settings = campaign.get('settings') or {}
        raw = settings.get('bid_type')
        if raw:
            try:
                return _normalize_bid_type(raw)
            except _PortalBidsValidationError:
                pass
    return _BID_TYPE_INT[BidType.MANUAL.value]


def _normalize_payment_type(value: str) -> str:
    key = str(value).strip().lower()
    try:
        return PaymentType(key).value
    except ValueError as exc:
        raise _PortalBidsValidationError(
            f'Invalid --payment-type {value!r}. Use cpm or cpc.'
        ) from exc


def _normalize_bid_type(value: str) -> int:
    key = str(value).strip().lower()
    if key in _BID_TYPE_INT:
        return _BID_TYPE_INT[key]
    raise _PortalBidsValidationError(
        f'Invalid --bid-type {value!r}. Use manual or unified.'
    )


def _render_bids_table(records: list) -> None:
    """Render PortalBidRecommendation list as a rich table."""
    from wb.core.output import render_table

    headers = [
        'NM ID', 'Pay', 'Placement', 'Min',
        'Max bid', 'Med bid', 'Min bid', 'Min clicks',
    ]
    rows = [
        [
            str(r.nm_id),
            r.payment_type,
            r.placement or '-',
            str(r.min_bid),
            str(r.reach_max.bid),
            str(r.reach_medium.bid),
            str(r.reach_min.bid),
            str(r.reach_min.clicks),
        ]
        for r in records
    ]
    render_table(headers, rows, title='Portal Bid Recommendations (kopecks)')
