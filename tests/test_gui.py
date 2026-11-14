from bagbot.gui.server import DashboardData


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


class FakeEngine:
    dry_run = True
    client = FakeClient()

    def open_orders(self):
        return {"DRYRUN-000001": {"pair": "XBTUSD", "type": "buy", "ordertype": "market",
                                  "vol": "0.01", "price": None, "status": "open"}}

    def balance(self):
        raise AssertionError("dry-run dashboard must not hit the exchange")


def _data():
    return DashboardData(FakeEngine(), default_pair="XBTUSD", started_at=0.0)


def test_status_reports_dry_run_and_uptime():
    s = _data().status()
    assert s["dry_run"] is True
    assert s["mode"] == "dry-run"
    assert s["uptime_seconds"] > 0


def test_portfolio_dry_run_has_no_balances():
    pf = _data().portfolio()
    assert pf["balances"] == {}
    assert pf["open_orders"] == 1
    assert "dry-run" in pf["note"]


def test_market_uses_ticker():
    m = _data().market(None)
    assert m["last"] == 50000.0
    assert m["pair"] == "XXBTZUSD"


def test_alerts_flag_dry_run():
    alerts = _data().alerts()
    assert any(a["level"] == "info" for a in alerts)


def test_live_alert_is_warning():
    engine = FakeEngine()
    engine.dry_run = False
    alerts = DashboardData(engine).alerts()
    assert any(a["level"] == "warning" for a in alerts)
