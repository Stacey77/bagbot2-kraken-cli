"""Local web dashboard for bagbot.

Stdlib-only HTTP server (no extra dependencies) serving a dark trading
dashboard plus a small JSON API backed by the trading engine. Data-provider
functions are separated from the HTTP layer so they can be tested offline.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bagbot.kraken.client import KrakenError
from bagbot.strategy import Candle, create_strategy, run_backtest
from bagbot.trading.engine import TradingEngine

STATIC_DIR = Path(__file__).parent / "static"
ALERTS_FILE = ".bagbot.alerts.json"


@dataclass(frozen=True)
class AlertRule:
    """A price alert for a pair: trigger when last price crosses a threshold."""

    pair: str
    above: float | None = None
    below: float | None = None

    def check(self, last_price: float) -> str | None:
        if self.above is not None and last_price >= self.above:
            return f"{self.pair} price {last_price} crossed above {self.above}"
        if self.below is not None and last_price <= self.below:
            return f"{self.pair} price {last_price} crossed below {self.below}"
        return None


def load_alert_rules(path: str | Path = ALERTS_FILE) -> list[AlertRule]:
    """Load alert rules from a JSON file; returns [] when absent/invalid."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rules = []
    for item in raw if isinstance(raw, list) else []:
        try:
            rules.append(AlertRule(
                pair=str(item["pair"]),
                above=None if item.get("above") is None else float(item["above"]),
                below=None if item.get("below") is None else float(item["below"]),
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return rules


class PriceBuffer:
    """Rolling buffer of recent prices, optionally fed by a WS thread."""

    def __init__(self, maxlen: int = 240) -> None:
        self._prices: deque[float] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def add(self, price: float) -> None:
        with self._lock:
            self._prices.append(price)

    def snapshot(self) -> list[float]:
        with self._lock:
            return list(self._prices)

    def start_ws(self, pair: str) -> threading.Thread | None:
        """Start a background WS feed; returns None if it cannot start."""
        try:
            from bagbot.kraken.ws import KrakenWSClient
        except ImportError:
            return None

        def _run() -> None:
            client = KrakenWSClient()
            try:
                asyncio.run(client.stream_ticker([pair], lambda t: self.add(t.last)))
            except Exception:
                pass  # REST polling in the UI is the fallback

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return thread


@dataclass
class DashboardData:
    """Feeds the dashboard API from the trading engine."""

    engine: TradingEngine
    default_pair: str = "XBTUSD"
    started_at: float = field(default_factory=time.time)
    alert_rules: list[AlertRule] = field(default_factory=load_alert_rules)
    price_buffer: PriceBuffer = field(default_factory=PriceBuffer)

    def status(self) -> dict:
        return {
            "mode": "dry-run" if self.engine.dry_run else "live",
            "dry_run": self.engine.dry_run,
            "uptime_seconds": int(time.time() - self.started_at),
        }

    def portfolio(self) -> dict:
        if self.engine.dry_run or not self.engine.client.api_key:
            return {
                "balances": {},
                "note": "dry-run / no API credentials - paper trading only",
                "open_orders": len(self.orders()),
            }
        try:
            return {"balances": self.engine.balance(), "note": ""}
        except KrakenError as exc:
            return {"balances": {}, "note": f"error: {exc}"}

    def orders(self) -> dict:
        try:
            return self.engine.open_orders()
        except KrakenError as exc:
            return {"error": str(exc)}

    def market(self, pair: str | None = None) -> dict:
        pair = pair or self.default_pair
        try:
            t = self.engine.client.ticker(pair)
            self.price_buffer.add(t.last)
            return {"pair": t.pair, "last": t.last, "bid": t.bid, "ask": t.ask, "volume_24h": t.volume_24h}
        except KrakenError as exc:
            return {"pair": pair, "error": str(exc)}

    def prices(self) -> dict:
        return {"pair": self.default_pair, "prices": self.price_buffer.snapshot()}

    def ohlc(self, pair: str | None = None, interval: int = 60) -> dict:
        pair = pair or self.default_pair
        try:
            raw = self.engine.client.ohlc(pair, interval)
        except KrakenError as exc:
            return {"pair": pair, "error": str(exc), "candles": []}
        rows = next((v for v in raw.values() if isinstance(v, list)), [])
        candles = [Candle.from_kraken(r) for r in rows]
        return {
            "pair": pair,
            "interval": interval,
            "candles": [
                {"time": c.time, "open": c.open, "high": c.high,
                 "low": c.low, "close": c.close, "volume": c.volume}
                for c in candles
            ],
        }

    def performance(self, pair: str | None = None, strategy: str = "sma") -> dict:
        pair = pair or self.default_pair
        data = self.ohlc(pair)
        if data.get("error"):
            return {"pair": pair, "error": data["error"]}
        candles = [Candle(time=c["time"], open=c["open"], high=c["high"],
                          low=c["low"], close=c["close"], volume=c["volume"])
                   for c in data["candles"]]
        try:
            strat = create_strategy(strategy)
        except ValueError as exc:
            return {"pair": pair, "error": str(exc)}
        result = run_backtest(strat, candles)
        return {
            "pair": pair,
            "strategy": strategy,
            "candles": len(candles),
            "return_pct": round(result.return_pct, 2),
            "max_drawdown_pct": round(result.max_drawdown_pct, 2),
            "trades": len(result.trades),
            "win_rate": None if result.win_rate is None else round(result.win_rate, 3),
        }

    def place_order(self, side: str, pair: str, volume: float,
                    price: float | None = None) -> dict:
        order_type = "limit" if price is not None else "market"
        try:
            result = self.engine.place_order(pair, side, volume, order_type, price)
        except (KrakenError, ValueError) as exc:
            return {"error": str(exc)}
        return {"txid": result.txid, "description": result.description, "dry_run": result.dry_run}

    def alerts(self) -> list[dict]:
        alerts = []
        if self.engine.dry_run:
            alerts.append({"level": "info", "text": "Dry-run mode: no real orders are placed."})
        else:
            alerts.append({"level": "warning", "text": "LIVE trading enabled - real orders will be placed."})
        market = self.market()
        last = market.get("last")
        if last is not None:
            for rule in self.alert_rules:
                if rule.pair in (market.get("pair"), self.default_pair):
                    hit = rule.check(float(last))
                    if hit:
                        alerts.append({"level": "warning", "text": hit})
        return alerts


def make_handler(data: DashboardData):
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, obj, status: int = 200) -> None:
            body = json.dumps(obj).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path: Path) -> None:
            body = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _body_json(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            try:
                return json.loads(self.rfile.read(length))
            except json.JSONDecodeError:
                return {}

        def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            pair = (query.get("pair") or [None])[0]
            if parsed.path in ("/", "/index.html"):
                self._send_file(STATIC_DIR / "index.html")
            elif parsed.path == "/api/status":
                self._send_json(data.status())
            elif parsed.path == "/api/portfolio":
                self._send_json(data.portfolio())
            elif parsed.path == "/api/orders":
                self._send_json(data.orders())
            elif parsed.path == "/api/alerts":
                self._send_json(data.alerts())
            elif parsed.path == "/api/market":
                self._send_json(data.market(pair))
            elif parsed.path == "/api/prices":
                self._send_json(data.prices())
            elif parsed.path == "/api/ohlc":
                interval = int((query.get("interval") or ["60"])[0])
                self._send_json(data.ohlc(pair, interval))
            elif parsed.path == "/api/performance":
                strategy = (query.get("strategy") or ["sma"])[0]
                self._send_json(data.performance(pair, strategy))
            else:
                self._send_json({"error": "not found"}, status=404)

        def do_POST(self) -> None:  # noqa: N802 (stdlib naming)
            parsed = urlparse(self.path)
            if parsed.path == "/api/order":
                body = self._body_json()
                try:
                    result = data.place_order(
                        side=str(body["side"]),
                        pair=str(body.get("pair") or data.default_pair),
                        volume=float(body["volume"]),
                        price=None if body.get("price") in (None, "") else float(body["price"]),
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    self._send_json({"error": f"invalid order: {exc}"}, status=400)
                    return
                self._send_json(result, status=400 if result.get("error") else 200)
            else:
                self._send_json({"error": "not found"}, status=404)

        def log_message(self, *args) -> None:  # keep the console clean
            pass

    return Handler


def serve(data: DashboardData, host: str = "127.0.0.1", port: int = 8080) -> None:
    """Run the dashboard server (blocking). Starts the WS price feed if possible."""
    data.price_buffer.start_ws(data.default_pair)
    server = ThreadingHTTPServer((host, port), make_handler(data))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
