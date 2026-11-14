"""Data models for Kraken API responses."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Ticker:
    """Best-effort normalized view of a Kraken Ticker response."""

    pair: str
    last: float
    bid: float
    ask: float
    volume_24h: float
    raw: dict = field(repr=False, default_factory=dict)


@dataclass(frozen=True)
class OrderResult:
    """Result of placing an order (real or simulated)."""

    txid: str
    description: str
    dry_run: bool = False
