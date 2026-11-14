import json

from bagbot.gui.server import AlertRule, DashboardData, PriceBuffer, load_alert_rules


def test_alert_rule_triggers():
    rule = AlertRule(pair="XBTUSD", above=150000.0, below=40000.0)
    assert rule.check(160000.0) is not None
    assert "above" in rule.check(160000.0)
    assert "below" in rule.check(39999.0)
    assert rule.check(100000.0) is None


def test_load_alert_rules_missing_file(tmp_path):
    assert load_alert_rules(tmp_path / "nope.json") == []


def test_load_alert_rules_parses_and_skips_bad_entries(tmp_path):
    p = tmp_path / "alerts.json"
    p.write_text(json.dumps([
        {"pair": "XBTUSD", "above": 150000},
        {"pair": "ETHUSD", "below": 2000},
        {"broken": True},
        "not-a-dict",
    ]), encoding="utf-8")
    rules = load_alert_rules(p)
    assert len(rules) == 2
    assert rules[0].above == 150000.0
    assert rules[1].below == 2000.0


def test_load_alert_rules_invalid_json(tmp_path):
    p = tmp_path / "alerts.json"
    p.write_text("{not json", encoding="utf-8")
    assert load_alert_rules(p) == []


def test_price_buffer_rolling():
    buf = PriceBuffer(maxlen=3)
    for price in (1.0, 2.0, 3.0, 4.0):
        buf.add(price)
    assert buf.snapshot() == [2.0, 3.0, 4.0]


class FakeTicker:
    pair = "XXBTZUSD"
    last = 50000.0
    bid = 49999.0
    ask = 50001.0
    volume_24h = 123.0


class FakeClient:
    api_key = None

    def ticker(self, pair):
        return FakeTicker()

    def ohlc(self, pair, interval):
        rows = [[1700000000 + i * 3600, "100", "101", "99", "100", "100", "1", 1]
                for i in range(5)]
        return {"XXBTZUSD": rows, "last": 1700018000}


class FakeEngine:
    dry_run = True
    client = FakeClient()

    def __init__(self):
        self.placed = []

    def open_orders(self):
        return {}

    def place_order(self, pair, side, volume, order_type, price=None):
        from bagbot.kraken.models import OrderResult
        self.placed.append((pair, side, volume, order_type, price))
        return OrderResult(txid="DRYRUN-000001", description="paper", dry_run=True)


def test_dashboard_ohlc_parses_candles():
    data = DashboardData(FakeEngine(), default_pair="XBTUSD", alert_rules=[])
    result = data.ohlc(None, 60)
    assert result["error"] if "error" in result else True
    assert len(result["candles"]) == 5
    assert result["candles"][0]["close"] == 100.0


def test_dashboard_performance_returns_summary():
    data = DashboardData(FakeEngine(), default_pair="XBTUSD", alert_rules=[])
    perf = data.performance()
    assert perf["candles"] == 5
    assert "return_pct" in perf and "max_drawdown_pct" in perf


def test_dashboard_place_order_dry_run():
    engine = FakeEngine()
    data = DashboardData(engine, default_pair="XBTUSD", alert_rules=[])
    result = data.place_order("buy", "XBTUSD", 0.5)
    assert result["txid"] == "DRYRUN-000001"
    assert engine.placed == [("XBTUSD", "buy", 0.5, "market", None)]


def test_dashboard_alert_rule_fires_on_price():
    engine = FakeEngine()
    rules = [AlertRule(pair="XBTUSD", below=60000.0)]
    data = DashboardData(engine, default_pair="XBTUSD", alert_rules=rules)
    alerts = data.alerts()
    assert any("crossed below" in a["text"] for a in alerts)
