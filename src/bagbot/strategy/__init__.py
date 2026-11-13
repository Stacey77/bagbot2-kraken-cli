"""Strategy framework and backtesting."""

from .backtest import BacktestResult, run_backtest
from .base import Candle, Signal, Strategy
from .sma import SmaCrossStrategy

__all__ = [
    "BacktestResult",
    "Candle",
    "Signal",
    "SmaCrossStrategy",
    "Strategy",
    "run_backtest",
]
