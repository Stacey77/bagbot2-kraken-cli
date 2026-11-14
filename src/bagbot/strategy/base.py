"""Core strategy abstractions."""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass


class Signal(enum.Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass(frozen=True)
class Candle:
    """One OHLCV candle."""

    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @classmethod
    def from_kraken(cls, row: list) -> "Candle":
        """Build from a Kraken OHLC row: [time, open, high, low, close, vwap, volume, count]."""
        return cls(
            time=int(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[6]),
        )


class Strategy(ABC):
    """Base class: inspect each candle and emit a signal."""

    name: str = "abstract"

    @abstractmethod
    def on_candle(self, index: int, candle: Candle, history: list[Candle]) -> Signal:
        """Return the signal for ``candle`` given all candles up to it."""
