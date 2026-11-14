"""Mean-reversion strategy (Bollinger-style bands around a moving average)."""

from __future__ import annotations

from .base import Candle, Signal, Strategy


class MeanReversionStrategy(Strategy):
    """Buy below ``mean - num_std*stdev``; sell above ``mean + num_std*stdev``."""

    name = "meanrev"

    def __init__(self, lookback: int = 20, num_std: float = 2.0) -> None:
        if lookback < 2:
            raise ValueError("lookback must be at least 2")
        if num_std <= 0:
            raise ValueError("num_std must be positive")
        self.lookback = lookback
        self.num_std = num_std

    def on_candle(self, index: int, candle: Candle, history: list[Candle]) -> Signal:
        closes = [c.close for c in history]
        if len(closes) < self.lookback:
            return Signal.HOLD
        window = closes[-self.lookback:]
        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / len(window)
        std = variance ** 0.5
        if std == 0:
            return Signal.HOLD
        if candle.close < mean - self.num_std * std:
            return Signal.BUY
        if candle.close > mean + self.num_std * std:
            return Signal.SELL
        return Signal.HOLD
