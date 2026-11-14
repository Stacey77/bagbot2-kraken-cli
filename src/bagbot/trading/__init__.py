"""Trading engine: wraps an exchange client with dry-run (paper) execution."""

from .engine import PaperOrder, TradingEngine

__all__ = ["PaperOrder", "TradingEngine"]
