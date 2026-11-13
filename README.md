# bagbot2-kraken-cli

A command-line crypto trading bot for **Kraken spot trading**, structured to
later support **Solana** on-chain operations. Dry-run (paper trading) is the
default — no real orders are placed unless you explicitly enable live mode.

## Features

- Market data: tickers, OHLC, order book (public Kraken REST endpoints)
- **Live WebSocket feeds**: `bagbot watch` streams ticker updates (Kraken WS v2)
- Account: balances, open orders (signed private endpoints)
- Trading: market/limit buy & sell, order cancellation
- **Strategy framework + backtesting**: SMA crossover strategy and a long-only
  backtester over historical OHLC candles (`bagbot backtest`)
- **Solana adapter**: JSON-RPC balance/blockhash queries (httpx), transfers
  signed via the optional `solders` extra (`pip install bagbot[solana]`)
- **Local web dashboard**: `bagbot gui` serves a dark trading dashboard
  (market data, portfolio, open orders, system alerts, live price chart)
- **Dry-run by default**: orders are simulated locally; nothing is sent to
  Kraken until you opt in with `--live` + `BAGBOT_DRY_RUN=false`
- Secrets come from env vars / a gitignored `.env` file — never hardcoded

## Setup

Requires Python 3.10+.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1        # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
```

Configure credentials (only needed for private endpoints / live trading):

```powershell
copy .env.example .env
# edit .env and fill in KRAKEN_API_KEY / KRAKEN_API_SECRET
```

Get API keys at <https://www.kraken.com/u/security/api>. `.env` is
gitignored — never commit real keys.

## Usage

```
bagbot --help
bagbot ticker XBTUSD
bagbot watch XBT/USD                  # live WebSocket ticker stream (Ctrl+C)
bagbot orderbook XBTUSD --depth 20
bagbot balance
bagbot orders
bagbot buy XBTUSD 0.01                 # dry-run market buy
bagbot sell XBTUSD 0.01 --price 65000  # dry-run limit sell
bagbot cancel DRYRUN-000001
bagbot backtest XBTUSD --strategy sma --fast 10 --slow 30 --interval 60
bagbot solbalance <SOLANA_ADDRESS>     # SOL balance via JSON-RPC
bagbot gui --port 8080                 # local web dashboard
```

### Live trading

Dry-run is the default everywhere. To place **real** orders you must do both:

1. Set `BAGBOT_DRY_RUN=false` in your environment or `.env`
2. Pass `--live` on the command line, e.g. `bagbot --live buy XBTUSD 0.01`

Live orders ask for interactive confirmation before submission. If `--live`
is passed while `BAGBOT_DRY_RUN` is still true, the bot stays in dry-run and
warns you.

## Development

```powershell
pip install -e ".[dev]"
pytest            # offline test suite (no network access required)
```

## Project layout

```
src/bagbot/
  cli.py              # Typer CLI entry point (`bagbot` command)
  config.py           # settings from env / .env (dry-run defaults to true)
  kraken/
    client.py         # thin Kraken REST client (HMAC-SHA512 signing)
    ws.py             # Kraken WebSocket v2 market-data client
    models.py         # Ticker / OrderResult dataclasses
  trading/
    engine.py         # execution layer with dry-run paper orders
  strategy/
    base.py           # Strategy ABC, Signal, Candle
    sma.py            # SMA crossover strategy
    backtest.py       # long-only backtester (PnL, win rate)
  solana/
    adapter.py        # Solana JSON-RPC adapter (transfers via solders extra)
  gui/
    server.py         # stdlib HTTP server + JSON API for the dashboard
    static/index.html # dark trading dashboard UI
tests/                # offline pytest suite
```

## Roadmap

- Full Solana swap support (Jupiter aggregator) and SPL token management
- More strategies (mean reversion, momentum) and strategy parameters from config
- WebSocket-fed live charts and order placement from the dashboard
- Richer GUI toward the full design mockups: portfolio analytics, strategy
  builder canvas, performance charts, and alert rules
