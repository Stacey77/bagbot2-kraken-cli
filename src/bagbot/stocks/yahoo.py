"""Equities market data via yfinance (Yahoo Finance).

The DataFrame-to-Candle conversion is a pure function so it can be tested
offline; only :class:`YahooFeed` touches the network.
"""

from __future__ import annotations

from dataclasses import dataclass

from bagbot.strategy import Candle


def frame_to_candles(df) -> list[Candle]:
    """Convert a yfinance single-ticker OHLCV DataFrame to candles.

    Rows with missing values (market holidays / gaps) are skipped.
    """
    candles = []
    for ts, row in df.iterrows():
        values = [row.get(c) for c in ("Open", "High", "Low", "Close", "Volume")]
        if any(v is None or v != v for v in values):  # None or NaN
            continue
        candles.append(Candle(
            time=int(ts.timestamp()),
            open=float(values[0]),
            high=float(values[1]),
            low=float(values[2]),
            close=float(values[3]),
            volume=float(values[4]),
        ))
    return candles


def extract_ticker_frame(data, symbol: str):
    """Pull one ticker's frame out of a ``group_by="ticker"`` download."""
    if symbol in getattr(data, "columns", {}).get_level_values(0):
        return data[symbol]
    return data  # single-ticker download without the extra level


@dataclass
class YahooFeed:
    """Fetches equities OHLCV from Yahoo Finance.

    ``downloader`` may be injected for offline tests (same signature as
    ``yfinance.download``).
    """

    downloader: object = None

    def _download(self, symbols, start: str, end: str):
        dl = self.downloader
        if dl is None:
            import yfinance as yf
            dl = yf.download
        return dl(symbols, start=start, end=end, group_by="ticker", progress=False)

    def ohlc(self, symbol: str, start: str, end: str) -> list[Candle]:
        """Daily candles for ``symbol`` between ``start`` and ``end`` (YYYY-MM-DD)."""
        data = self._download([symbol], start, end)
        return frame_to_candles(extract_ticker_frame(data, symbol))

    def ohlc_many(self, symbols: list[str], start: str, end: str) -> dict[str, list[Candle]]:
        """Daily candles for several symbols in one download."""
        data = self._download(symbols, start, end)
        return {s: frame_to_candles(extract_ticker_frame(data, s)) for s in symbols}

    def latest_close(self, symbol: str) -> float:
        """Most recent close for ``symbol`` (last few days of data)."""
        data = self._download([symbol], start="2024-01-01", end="2100-01-01")
        candles = frame_to_candles(extract_ticker_frame(data, symbol))
        if not candles:
            raise ValueError(f"no data returned for {symbol!r}")
        return candles[-1].close
