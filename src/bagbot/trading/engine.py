"""Execution layer with dry-run (paper trading) support.

Dry-run is the default everywhere in bagbot: orders are simulated locally
and no signed request ever leaves the process unless live mode is enabled.
"""

from __future__ import annotations

from dataclasses import dataclass

from bagbot.kraken.client import KrakenClient
from bagbot.kraken.models import OrderResult


@dataclass
class PaperOrder:
    txid: str
    pair: str
    side: str
    order_type: str
    volume: float
    price: float | None
    status: str = "open"  # open | canceled


class TradingEngine:
    """Places/cancels orders through a client, or simulates them in dry-run."""

    def __init__(self, client: KrakenClient, dry_run: bool = True) -> None:
        self.client = client
        self.dry_run = dry_run
        self._paper_orders: dict[str, PaperOrder] = {}

    @staticmethod
    def _validate(pair: str, side: str, order_type: str, volume: float, price: float | None) -> None:
        if not pair:
            raise ValueError("pair must not be empty")
        if side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        if order_type not in ("market", "limit"):
            raise ValueError("order_type must be 'market' or 'limit'")
        if volume <= 0:
            raise ValueError("volume must be positive")
        if order_type == "limit":
            if price is None:
                raise ValueError("limit orders require a price")
            if price <= 0:
                raise ValueError("price must be positive")

    def place_order(
        self,
        pair: str,
        side: str,
        volume: float,
        order_type: str = "market",
        price: float | None = None,
    ) -> OrderResult:
        side = side.lower()
        order_type = order_type.lower()
        self._validate(pair, side, order_type, volume, price)

        if self.dry_run:
            txid = f"DRYRUN-{len(self._paper_orders) + 1:06d}"
            order = PaperOrder(
                txid=txid, pair=pair, side=side, order_type=order_type,
                volume=volume, price=price,
            )
            self._paper_orders[txid] = order
            descr = f"{side} {volume} {pair} @ {order_type}"
            if price is not None:
                descr += f" {price}"
            return OrderResult(txid=txid, description=f"[dry-run] {descr}", dry_run=True)

        return self.client.add_order(pair, side, order_type, volume, price)

    def cancel_order(self, txid: str) -> bool:
        if self.dry_run:
            order = self._paper_orders.get(txid)
            if order is None or order.status != "open":
                return False
            order.status = "canceled"
            return True
        return self.client.cancel_order(txid)

    def balance(self) -> dict:
        return self.client.balance()

    def open_orders(self) -> dict:
        if self.dry_run:
            return {
                txid: {
                    "pair": o.pair,
                    "type": o.side,
                    "ordertype": o.order_type,
                    "vol": str(o.volume),
                    "price": None if o.price is None else str(o.price),
                    "status": o.status,
                }
                for txid, o in self._paper_orders.items()
                if o.status == "open"
            }
        return self.client.open_orders()
