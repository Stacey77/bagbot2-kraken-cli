"""Simple moving-average crossover strategy."""

from __future__ import annotations

from .base import Candle, Signal, Strategy


def sma(values: list[float], period: int) -> float | None:
    """Simple moving average of the last ``period`` values, or None."""
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


class SmaCrossStrategy(Strategy):
    """Buy when the fast SMA crosses above the slow SMA; sell on the reverse."""

    name = "sma"

    def __init__(self, fast: int = 10, slow: int = 30) -> None:
        if fast >= slow:
            raise ValueError("fast period must be smaller than slow period")
        self.fast = fast
        self.slow = slow

    def on_candle(self, index: int, candle: Candle, history: list[Candle]) -> Signal:
        closes = [c.close for c in history]
        if len(closes) < self.slow + 1:
            return Signal.HOLD
        fast_now = sma(closes, self.fast)
        slow_now = sma(closes, self.slow)
        fast_prev = sma(closes[:-1], self.fast)
        slow_prev = sma(closes[:-1], self.slow)
        assert None not in (fast_now, slow_now, fast_prev, slow_prev)
        if fast_prev <= slow_prev and fast_now > slow_now:
            return Signal.BUY
        if fast_prev >= slow_prev and fast_now < slow_now:
            return Signal.SELL
        return Signal.HOLD
