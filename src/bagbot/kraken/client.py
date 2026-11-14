"""Thin Kraken REST API client (public + signed private endpoints).

The client is intentionally dependency-light (httpx only) and exposes the
request-signing logic as a pure module-level function so it can be tested
without any network access.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import urllib.parse

import httpx

from .models import OrderResult, Ticker


class KrakenError(Exception):
    """Raised when the Kraken API reports an error or credentials are missing."""


def sign_request(urlpath: str, data: dict, api_secret: str) -> str:
    """Compute the Kraken API-Sign header value for a private request.

    Pure function of (urlpath, data, api_secret); ``data`` must include a
    ``nonce`` entry. See https://docs.kraken.com/api/docs/guides/spot-rest-auth
    """
    postdata = urllib.parse.urlencode(data)
    encoded = (str(data["nonce"]) + postdata).encode()
    message = urlpath.encode() + hashlib.sha256(encoded).digest()
    mac = hmac.new(base64.b64decode(api_secret), message, hashlib.sha512)
    return base64.b64encode(mac.digest()).decode()


class KrakenClient:
    """Minimal Kraken spot REST client.

    ``http_client`` may be injected (e.g. ``httpx.Client(transport=
    httpx.MockTransport(...))``) for offline tests.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        base_url: str = "https://api.kraken.com",
        timeout: float = 30.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self._http = http_client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._http.close()

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _nonce() -> str:
        return str(int(time.time() * 1000))

    @staticmethod
    def _handle(resp: httpx.Response) -> dict:
        resp.raise_for_status()
        payload = resp.json()
        errors = payload.get("error") or []
        if errors:
            raise KrakenError("; ".join(str(e) for e in errors))
        return payload.get("result", {})

    def _public(self, method: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}/0/public/{method}"
        return self._handle(self._http.get(url, params=params or {}))

    def _private(self, method: str, params: dict | None = None) -> dict:
        if not self.api_key or not self.api_secret:
            raise KrakenError(
                "Kraken API key and secret are required for private endpoints "
                "(set KRAKEN_API_KEY / KRAKEN_API_SECRET)."
            )
        urlpath = f"/0/private/{method}"
        data = {"nonce": self._nonce(), **(params or {})}
        headers = {
            "API-Key": self.api_key,
            "API-Sign": sign_request(urlpath, data, self.api_secret),
        }
        return self._handle(self._http.post(f"{self.base_url}{urlpath}", data=data, headers=headers))

    # ------------------------------------------------------------------
    # Public market data
    # ------------------------------------------------------------------
    def server_time(self) -> dict:
        return self._public("Time")

    def ticker(self, pair: str) -> Ticker:
        result = self._public("Ticker", {"pair": pair})
        if not result:
            raise KrakenError(f"No ticker data returned for pair {pair!r}")
        key, info = next(iter(result.items()))
        return Ticker(
            pair=key,
            last=float(info["c"][0]),
            bid=float(info["b"][0]),
            ask=float(info["a"][0]),
            volume_24h=float(info["v"][1]),
            raw=info,
        )

    def ohlc(self, pair: str, interval: int = 60) -> dict:
        return self._public("OHLC", {"pair": pair, "interval": interval})

    def order_book(self, pair: str, depth: int = 10) -> dict:
        return self._public("Depth", {"pair": pair, "count": depth})

    # ------------------------------------------------------------------
    # Private account / trading
    # ------------------------------------------------------------------
    def balance(self) -> dict:
        return self._private("Balance")

    def open_orders(self) -> dict:
        return self._private("OpenOrders")

    def add_order(
        self,
        pair: str,
        side: str,
        order_type: str,
        volume: float,
        price: float | None = None,
    ) -> OrderResult:
        params: dict = {
            "pair": pair,
            "type": side,
            "ordertype": order_type,
            "volume": str(volume),
        }
        if order_type == "limit":
            if price is None:
                raise KrakenError("Limit orders require a price.")
            params["price"] = str(price)
        result = self._private("AddOrder", params)
        txids = result.get("txid") or []
        descr = (result.get("descr") or {}).get("order", "")
        return OrderResult(txid=txids[0] if txids else "", description=descr)

    def cancel_order(self, txid: str) -> bool:
        result = self._private("CancelOrder", {"txid": txid})
        return int(result.get("count", 0)) > 0
