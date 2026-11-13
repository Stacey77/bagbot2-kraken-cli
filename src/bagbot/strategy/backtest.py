"""Minimal long-only backtester.

Runs a strategy over historical candles: a BUY signal while flat invests all
cash at the candle close; a SELL signal while long liquidates at the close.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import Candle, Signal, Strategy


@dataclass(frozen=True)
class Trade:
    side: str
    time: int
    price: float
    quantity: float


@dataclass(frozen=True)
class BacktestResult:
    initial_cash: float
    final_equity: float
    return_pct: float
    trades: list[Trade] = field(default_factory=list)
    wins: int = 0
    losses: int = 0

    @property
    def win_rate(self) -> float | None:
        closed = self.wins + self.losses
        return (self.wins / closed) if closed else None


def run_backtest(
    strategy: Strategy,
    candles: list[Candle],
    initial_cash: float = 10_000.0,
) -> BacktestResult:
    if initial_cash <= 0:
        raise ValueError("initial_cash must be positive")
    cash = initial_cash
    quantity = 0.0
    entry_price = 0.0
    wins = losses = 0
    trades: list[Trade] = []

    for i, candle in enumerate(candles):
        signal = strategy.on_candle(i, candle, candles[: i + 1])
        if signal is Signal.BUY and cash > 0:
            quantity = cash / candle.close
            entry_price = candle.close
            cash = 0.0
            trades.append(Trade("buy", candle.time, candle.close, quantity))
        elif signal is Signal.SELL and quantity > 0:
            cash = quantity * candle.close
            if candle.close > entry_price:
                wins += 1
            else:
                losses += 1
            trades.append(Trade("sell", candle.time, candle.close, quantity))
            quantity = 0.0

    final_equity = cash + quantity * (candles[-1].close if candles else 0.0)
    return BacktestResult(
        initial_cash=initial_cash,
        final_equity=final_equity,
        return_pct=(final_equity - initial_cash) / initial_cash * 100.0,
        trades=trades,
        wins=wins,
        losses=losses,
    )
