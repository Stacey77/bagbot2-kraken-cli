"""Kraken WebSocket v2 market-data client.

Parsing is kept as pure module-level functions so the message handling can
be tested offline; only :class:`KrakenWSClient` touches the network.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Iterator

from .models import Ticker

WS_URL = "wss://ws.kraken.com/v2"


def subscribe_message(channel: str, symbols: list[str]) -> str:
    """Build a Kraken WS v2 subscribe frame."""
    return json.dumps({
        "method": "subscribe",
        "params": {"channel": channel, "symbol": symbols},
    })


def parse_ticker_message(message: str | dict) -> Ticker | None:
    """Parse a ticker channel frame into a :class:`Ticker`.

    Returns ``None`` for non-ticker frames (heartbeats, status, subscribe
    acks) so callers can simply skip them.
    """
    msg = json.loads(message) if isinstance(message, str) else message
    if msg.get("channel") != "ticker":
        return None
    data = msg.get("data") or []
    if not data:
        return None
    d = data[0]
    return Ticker(
        pair=d.get("symbol", ""),
        last=float(d.get("last", 0.0)),
        bid=float(d.get("bid", 0.0)),
        ask=float(d.get("ask", 0.0)),
        volume_24h=float(d.get("volume", 0.0)),
        raw=d,
    )


class KrakenWSClient:
    """Async WebSocket client for Kraken public market data (WS API v2)."""

    def __init__(self, url: str = WS_URL) -> None:
        self.url = url

    async def stream_ticker(
        self,
        symbols: list[str],
        on_ticker: Callable[[Ticker], None],
        stop: asyncio.Event | None = None,
    ) -> None:
        """Subscribe to the ticker channel and invoke ``on_ticker`` per update.

        Runs until ``stop`` is set, the server closes the connection, or the
        task is cancelled (e.g. Ctrl+C in the CLI).
        """
        import websockets

        async with websockets.connect(self.url) as ws:
            await ws.send(subscribe_message("ticker", symbols))
            async for raw in ws:
                if stop is not None and stop.is_set():
                    break
                ticker = parse_ticker_message(raw)
                if ticker is not None:
                    on_ticker(ticker)


def stream_ticker_sync(symbols: list[str], on_ticker: Callable[[Ticker], None]) -> None:
    """Synchronous wrapper around :meth:`KrakenWSClient.stream_ticker`."""
    client = KrakenWSClient()
    asyncio.run(client.stream_ticker(symbols, on_ticker))
