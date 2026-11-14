"""Strategy framework and backtesting."""

from .backtest import BacktestResult, Trade, run_backtest
from .base import Candle, Signal, Strategy
from .meanrev import MeanReversionStrategy
from .momentum import MomentumStrategy
from .sma import SmaCrossStrategy

STRATEGY_NAMES = ("sma", "meanrev", "momentum")

__all__ = [
    "BacktestResult",
    "Candle",
    "MeanReversionStrategy",
    "MomentumStrategy",
    "Signal",
    "SmaCrossStrategy",
    "Strategy",
    "Trade",
    "create_strategy",
    "run_backtest",
    "STRATEGY_NAMES",
]


def create_strategy(name: str, **params) -> Strategy:
    """Build a strategy by name: ``sma``, ``meanrev``, or ``momentum``."""
    registry: dict[str, type[Strategy]] = {
        SmaCrossStrategy.name: SmaCrossStrategy,
        MeanReversionStrategy.name: MeanReversionStrategy,
        MomentumStrategy.name: MomentumStrategy,
    }
    cls = registry.get(name)
    if cls is None:
        raise ValueError(
            f"unknown strategy {name!r} (available: {', '.join(STRATEGY_NAMES)})"
        )
    return cls(**params)
