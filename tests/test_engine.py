import pytest

from bagbot.trading.engine import TradingEngine


class FakeClient:
    """Stand-in for KrakenClient; records calls, never touches network."""

    def __init__(self):
        self.added = []
        self.canceled = []

    def add_order(self, pair, side, order_type, volume, price=None):
        self.added.append((pair, side, order_type, volume, price))
        from bagbot.kraken.models import OrderResult
        return OrderResult(txid="REAL-1", description="live order")

    def cancel_order(self, txid):
        self.canceled.append(txid)
        return True

    def balance(self):
        return {"ZUSD": "1000.0"}

    def open_orders(self):
        return {"REAL-1": {"status": "open"}}


def test_dry_run_places_paper_order_without_client():
    client = FakeClient()
    engine = TradingEngine(client, dry_run=True)
    result = engine.place_order("XBTUSD", "buy", 0.5)
    assert result.dry_run is True
    assert result.txid.startswith("DRYRUN-")
    assert "buy 0.5 XBTUSD @ market" in result.description
    assert client.added == []  # nothing sent to the exchange


def test_dry_run_open_orders_and_cancel():
    engine = TradingEngine(FakeClient(), dry_run=True)
    result = engine.place_order("XBTUSD", "sell", 1.0, "limit", 60000.0)
    open_orders = engine.open_orders()
    assert result.txid in open_orders
    assert open_orders[result.txid]["ordertype"] == "limit"

    assert engine.cancel_order(result.txid) is True
    assert engine.open_orders() == {}
    assert engine.cancel_order(result.txid) is False  # already canceled


def test_dry_run_rejects_unknown_txid():
    engine = TradingEngine(FakeClient(), dry_run=True)
    assert engine.cancel_order("NOPE") is False


def test_live_mode_delegates_to_client():
    client = FakeClient()
    engine = TradingEngine(client, dry_run=False)
    result = engine.place_order("XBTUSD", "buy", 0.1, "limit", 50000.0)
    assert result.txid == "REAL-1"
    assert result.dry_run is False
    assert client.added == [("XBTUSD", "buy", "limit", 0.1, 50000.0)]
    assert engine.cancel_order("REAL-1") is True
    assert client.canceled == ["REAL-1"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"pair": "", "side": "buy", "volume": 1},
        {"pair": "XBTUSD", "side": "hold", "volume": 1},
        {"pair": "XBTUSD", "side": "buy", "volume": 0},
        {"pair": "XBTUSD", "side": "buy", "volume": -1},
        {"pair": "XBTUSD", "side": "buy", "volume": 1, "order_type": "limit"},
        {"pair": "XBTUSD", "side": "buy", "volume": 1, "order_type": "limit", "price": 0},
        {"pair": "XBTUSD", "side": "buy", "volume": 1, "order_type": "iceberg"},
    ],
)
def test_invalid_orders_rejected(kwargs):
    engine = TradingEngine(FakeClient(), dry_run=True)
    with pytest.raises(ValueError):
        engine.place_order(**kwargs)
