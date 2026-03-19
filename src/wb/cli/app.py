"""Main CLI application entry point using Typer."""

from __future__ import annotations

import logging
import sys

import typer

from wb import __version__
from wb.cli.auth import auth_app
from wb.cli.bid import bid_app
from wb.cli.budget import budget_app
from wb.cli.campaign import campaign_app
from wb.cli.cluster import cluster_app
from wb.cli.portal import portal_app
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
) -> None:
    """WB CLI global options."""
    _configure_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['quiet'] = quiet
    ctx.obj['json_output'] = json_output
    ctx.obj['profile'] = profile


@app.command()
def version() -> None:
    """Show the CLI version."""
    typer.echo(f'wb-cli {__version__}')


def main() -> None:
    """CLI entry point with top-level exception handling."""
    try:
        app()
    except WbCliError as exc:
        typer.secho(f'Error: {exc}', fg=typer.colors.RED, err=True)
        sys.exit(exc.exit_code)
    except KeyboardInterrupt:
        typer.echo('\nAborted.', err=True)
        sys.exit(130)
