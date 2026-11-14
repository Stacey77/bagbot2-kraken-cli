import base64
import hashlib
import hmac
import urllib.parse

import httpx
import pytest

from bagbot.kraken.client import KrakenClient, KrakenError, sign_request

SECRET = base64.b64encode(b"test-secret-key-material").decode()  # envshield:allow - fake test data


def _client(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    return KrakenClient(http_client=httpx.Client(transport=transport), **kwargs)


def test_sign_request_matches_manual_hmac():
    data = {"nonce": "1616492376594", "ordertype": "limit", "pair": "XBTUSD", "type": "buy", "volume": "1.25"}
    postdata = urllib.parse.urlencode(data)
    expected_message = "/0/private/AddOrder".encode() + hashlib.sha256(
        (data["nonce"] + postdata).encode()
    ).digest()
    expected = base64.b64encode(
        hmac.new(base64.b64decode(SECRET), expected_message, hashlib.sha512).digest()
    ).decode()
    assert sign_request("/0/private/AddOrder", data, SECRET) == expected


def test_sign_request_changes_with_nonce():
    base = {"nonce": "1", "pair": "XBTUSD"}
    assert sign_request("/0/private/Balance", base, SECRET) != sign_request(
        "/0/private/Balance", {**base, "nonce": "2"}, SECRET
    )


def test_ticker_parses_kraken_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/0/public/Ticker"
        assert request.url.params["pair"] == "XBTUSD"
        return httpx.Response(200, json={
            "error": [],
            "result": {
                "XXBTZUSD": {
                    "a": ["50100.0", "1", "1.0"],
                    "b": ["50000.0", "1", "1.0"],
                    "c": ["50050.5", "0.01"],
                    "v": ["100.0", "250.5"],
                }
            },
        })

    t = _client(handler).ticker("XBTUSD")
    assert t.pair == "XXBTZUSD"
    assert t.last == 50050.5
    assert t.bid == 50000.0
    assert t.ask == 50100.0
    assert t.volume_24h == 250.5


def test_private_endpoint_requires_credentials():
    client = _client(lambda r: httpx.Response(200, json={"error": [], "result": {}}))
    with pytest.raises(KrakenError, match="API key and secret"):
        client.balance()


def test_private_request_sends_signature_headers():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = request.headers
        captured["body"] = request.read().decode()
        return httpx.Response(200, json={"error": [], "result": {"ZUSD": "100.0000"}})

    client = _client(handler, api_key="mykey", api_secret=SECRET)
    result = client.balance()
    assert result == {"ZUSD": "100.0000"}
    assert captured["headers"]["API-Key"] == "mykey"
    assert captured["headers"]["API-Sign"]
    assert "nonce=" in captured["body"]


def test_api_error_raises_kraken_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": ["EQuery:Unknown asset pair"], "result": {}})

    with pytest.raises(KrakenError, match="Unknown asset pair"):
        _client(handler).ticker("NOPE")


def test_add_order_limit_requires_price():
    client = _client(lambda r: httpx.Response(200, json={"error": [], "result": {}}),
                     api_key="k", api_secret=SECRET)
    with pytest.raises(KrakenError, match="price"):
        client.add_order("XBTUSD", "buy", "limit", 0.1)
