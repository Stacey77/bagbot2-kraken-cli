"""Momentum strategy: follow strong N-candle moves."""

from __future__ import annotations

from .base import Candle, Signal, Strategy


class MomentumStrategy(Strategy):
    """Buy when the N-candle return exceeds +threshold; sell below -threshold."""

    name = "momentum"

    def __init__(self, lookback: int = 10, threshold: float = 0.03) -> None:
        if lookback < 1:
            raise ValueError("lookback must be positive")
        if threshold <= 0:
            raise ValueError("threshold must be positive")
        self.lookback = lookback
        self.threshold = threshold

    def on_candle(self, index: int, candle: Candle, history: list[Candle]) -> Signal:
        closes = [c.close for c in history]
        if len(closes) < self.lookback + 1:
            return Signal.HOLD
        past = closes[-1 - self.lookback]
        if past <= 0:
            return Signal.HOLD
        ret = closes[-1] / past - 1.0
        if ret > self.threshold:
            return Signal.BUY
        if ret < -self.threshold:
            return Signal.SELL
        return Signal.HOLD
