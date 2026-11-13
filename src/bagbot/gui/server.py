"""Local web dashboard for bagbot (foundation).

Stdlib-only HTTP server (no extra dependencies) serving a dark trading
dashboard plus a small JSON API backed by the trading engine. Data-provider
functions are separated from the HTTP layer so they can be tested offline.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bagbot.kraken.client import KrakenError
from bagbot.trading.engine import TradingEngine

STATIC_DIR = Path(__file__).parent / "static"


@dataclass
class DashboardData:
    """Feeds the dashboard API from the trading engine."""

    engine: TradingEngine
    default_pair: str = "XBTUSD"
    started_at: float = field(default_factory=time.time)

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
            return {"pair": t.pair, "last": t.last, "bid": t.bid, "ask": t.ask, "volume_24h": t.volume_24h}
        except KrakenError as exc:
            return {"pair": pair, "error": str(exc)}

    def alerts(self) -> list[dict]:
        alerts = []
        if self.engine.dry_run:
            alerts.append({"level": "info", "text": "Dry-run mode: no real orders are placed."})
        else:
            alerts.append({"level": "warning", "text": "LIVE trading enabled - real orders will be placed."})
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

        def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
            parsed = urlparse(self.path)
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
                pair = (parse_qs(parsed.query).get("pair") or [None])[0]
                self._send_json(data.market(pair))
            else:
                self._send_json({"error": "not found"}, status=404)

        def log_message(self, *args) -> None:  # keep the console clean
            pass

    return Handler


def serve(data: DashboardData, host: str = "127.0.0.1", port: int = 8080) -> None:
    """Run the dashboard server (blocking)."""
    server = ThreadingHTTPServer((host, port), make_handler(data))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
