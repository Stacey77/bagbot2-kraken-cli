"""Command-line interface for bagbot.

Dry-run is the default: pass ``--live`` (and set BAGBOT_DRY_RUN=false) to
place real orders on Kraken.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass

import typer

from bagbot.config import Settings, load_settings
from bagbot.kraken.client import KrakenClient, KrakenError
from bagbot.trading.engine import TradingEngine

app = typer.Typer(
    name="bagbot",
    help="Crypto trading bot CLI for Kraken (spot). Dry-run by default.",
    no_args_is_help=True,
)


class _State:
    def __init__(self) -> None:
        self.settings: Settings = load_settings(env_file=None)
        self.dry_run: bool = True
        self._engine: TradingEngine | None = None

    def engine(self) -> TradingEngine:
        if self._engine is None:
            client = KrakenClient(
                api_key=self.settings.api_key,
                api_secret=self.settings.api_secret,
                base_url=self.settings.base_url,
            )
            self._engine = TradingEngine(client, dry_run=self.dry_run)
        return self._engine


_STATE = _State()


def _echo(data) -> None:
    def default(o):
        return asdict(o) if is_dataclass(o) else str(o)

    typer.echo(json.dumps(data, indent=2, default=default))


def _require_credentials() -> None:
    if not _STATE.settings.has_credentials:
        typer.secho(
            "Error: KRAKEN_API_KEY and KRAKEN_API_SECRET are required for this "
            "command. Copy .env.example to .env and fill in your keys.",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=2)


def _mode_banner() -> None:
    if _STATE.dry_run:
        typer.secho("[dry-run] no real orders will be placed", fg=typer.colors.YELLOW)


@app.callback()
def main(
    live: bool = typer.Option(
        False, "--live", help="Disable dry-run and place REAL orders (requires BAGBOT_DRY_RUN=false)."
    ),
    env_file: str = typer.Option(".env", "--env-file", help="Path to a .env config file."),
) -> None:
    settings = load_settings(env_file=env_file)
    _STATE.settings = settings
    _STATE.dry_run = settings.dry_run or not live
    _STATE._engine = None
    if live and settings.dry_run:
        typer.secho(
            "Warning: --live was passed but BAGBOT_DRY_RUN is still true; "
            "staying in dry-run. Set BAGBOT_DRY_RUN=false to trade live.",
            err=True,
            fg=typer.colors.YELLOW,
        )


@app.command()
def ticker(pair: str = typer.Argument(..., help="Market pair, e.g. XBTUSD")) -> None:
    """Show the latest ticker for a market pair."""
    try:
        _echo(_STATE.engine().client.ticker(pair))
    except KrakenError as exc:
        typer.secho(f"Error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def orderbook(
    pair: str = typer.Argument(..., help="Market pair, e.g. XBTUSD"),
    depth: int = typer.Option(10, "--depth", "-d", help="Order book depth."),
) -> None:
    """Show the order book for a market pair."""
    try:
        _echo(_STATE.engine().client.order_book(pair, depth))
    except KrakenError as exc:
        typer.secho(f"Error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def balance() -> None:
    """Show account balances (requires API credentials)."""
    _require_credentials()
    try:
        _echo(_STATE.engine().balance())
    except KrakenError as exc:
        typer.secho(f"Error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def orders() -> None:
    """List open orders (paper orders in dry-run mode)."""
    if not _STATE.dry_run:
        _require_credentials()
    _mode_banner()
    try:
        _echo(_STATE.engine().open_orders())
    except KrakenError as exc:
        typer.secho(f"Error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)


def _place(side: str, pair: str, volume: float, price: float | None) -> None:
    _mode_banner()
    if not _STATE.dry_run:
        _require_credentials()
        typer.confirm(f"Place REAL {side} order: {volume} {pair}?", abort=True)
    order_type = "limit" if price is not None else "market"
    try:
        result = _STATE.engine().place_order(pair, side, volume, order_type, price)
    except (KrakenError, ValueError) as exc:
        typer.secho(f"Error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)
    _echo(result)


@app.command()
def buy(
    pair: str = typer.Argument(..., help="Market pair, e.g. XBTUSD"),
    volume: float = typer.Argument(..., help="Amount of the base asset to buy."),
    price: float | None = typer.Option(None, "--price", "-p", help="Limit price (omit for market order)."),
) -> None:
    """Place a buy order (simulated unless --live)."""
    _place("buy", pair, volume, price)


@app.command()
def sell(
    pair: str = typer.Argument(..., help="Market pair, e.g. XBTUSD"),
    volume: float = typer.Argument(..., help="Amount of the base asset to sell."),
    price: float | None = typer.Option(None, "--price", "-p", help="Limit price (omit for market order)."),
) -> None:
    """Place a sell order (simulated unless --live)."""
    _place("sell", pair, volume, price)


@app.command()
def cancel(txid: str = typer.Argument(..., help="Transaction ID of the order to cancel.")) -> None:
    """Cancel an open order."""
    _mode_banner()
    if not _STATE.dry_run:
        _require_credentials()
    try:
        canceled = _STATE.engine().cancel_order(txid)
    except KrakenError as exc:
        typer.secho(f"Error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if canceled:
        typer.secho(f"Canceled {txid}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"No open order found for {txid}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)
