"""Main CLI application entry point using Typer."""

from __future__ import annotations

import json
import logging
import sys

import typer

from wb import __version__
from wb.cli.analytics import analytics_app
from wb.cli.assess import assess_command
from wb.cli.auth import auth_app
from wb.cli.cache import cache_app
from wb.cli.optimize import optimize_app
from wb.cli.bid import bid_app
from wb.cli.budget import budget_app
from wb.cli.campaign import campaign_app
from wb.cli.cluster import cluster_app
from wb.cli.portal import portal_app
from wb.cli.prices import prices_app
from wb.cli.product import product_app
from wb.cli.pulse import pulse_command
from wb.cli.report import report_app
from wb.cli.stats import stats_app
from wb.core.exceptions import WbCliError

app = typer.Typer(
    name='wb',
    help='WB CLI - Wildberries Advertising Operations Framework',
    no_args_is_help=True,
    rich_markup_mode='rich',
)

app.add_typer(auth_app, name='auth', help='Authentication and profile management')
app.add_typer(campaign_app, name='campaign', help='Campaign management')
app.add_typer(bid_app, name='bid', help='Bid management')
app.add_typer(budget_app, name='budget', help='Budget and balance')
app.add_typer(stats_app, name='stats', help='Campaign and cluster statistics')
app.add_typer(cluster_app, name='cluster', help='Search cluster management')
app.add_typer(portal_app, name='portal', help='Seller portal operations')
app.add_typer(prices_app, name='prices', help='Prices and discounts')
app.add_typer(analytics_app, name='analytics', help='Analytics operations')
app.add_typer(optimize_app, name='optimize', help='Optimization workflows')
app.add_typer(report_app, name='report', help='Reports (warehouse, orders, sales)')
app.add_typer(cache_app, name='cache', help='Local snapshot cache')
app.add_typer(product_app, name='product', help='Product summary and analysis')
app.command('assess', help='Morning account snapshot: balance, campaigns, 7-day spend')(
    assess_command,
)
app.command('pulse', help='Intraday health check: bid drift, budget, campaign status')(
    pulse_command,
)


def _configure_logging(verbose: bool = False) -> None:
    """Set up logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )


@app.callback()
def main_callback(
        ctx: typer.Context,
        verbose: bool = typer.Option(False, '--verbose', '-v', help='Enable verbose output'),
        quiet: bool = typer.Option(False, '--quiet', '-q', help='Suppress non-essential output'),
        json_output: bool = typer.Option(False, '--json', help='Output in JSON format'),
        profile: str | None = typer.Option(None, '--profile', '-p', help='Use a specific profile'),
        fields: str | None = typer.Option(
            None, '--fields',
            help='Comma-separated output fields to include (e.g. nm_id,orders,views)',
        ),
        compact: bool = typer.Option(
            False, '--compact',
            help='Output JSON as a single line (reduces token count for agents)',
        ),
) -> None:
    """WB CLI global options."""
    _configure_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['quiet'] = quiet
    ctx.obj['json_output'] = json_output
    ctx.obj['profile'] = profile
    ctx.obj['fields'] = [f.strip() for f in fields.split(',')] if fields else None
    ctx.obj['compact'] = compact


@app.command()
def version() -> None:
    """Show the CLI version."""
    typer.echo(f'wb-cli {__version__}')


def _is_json_mode() -> bool:
    """Detect --json flag from sys.argv (before Typer context is available)."""
    return '--json' in sys.argv


def main() -> None:
    """CLI entry point with top-level exception handling."""
    # WB content is in Russian — reconfigure to UTF-8 so piped output never
    # crashes with cp437 (the Windows legacy console default).
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    try:
        app()
    except WbCliError as exc:
        if _is_json_mode():
            print(json.dumps(exc.to_dict(), ensure_ascii=False))
        else:
            typer.secho(f'Error: {exc}', fg=typer.colors.RED, err=True)
        sys.exit(exc.exit_code)
    except KeyboardInterrupt:
        typer.echo('\nAborted.', err=True)
        sys.exit(130)
