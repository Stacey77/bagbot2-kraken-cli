import json

from bagbot.kraken.ws import parse_ticker_message, subscribe_message


def test_subscribe_message_format():
    frame = json.loads(subscribe_message("ticker", ["XBT/USD"]))
    assert frame == {"method": "subscribe", "params": {"channel": "ticker", "symbol": ["XBT/USD"]}}


def test_parse_ticker_snapshot():
    msg = json.dumps({
        "channel": "ticker",
        "type": "snapshot",
        "data": [{"symbol": "XBT/USD", "last": 50050.5, "bid": 50000.0,
                  "ask": 50100.0, "volume": 250.5}],
    })
    t = parse_ticker_message(msg)
    assert t is not None
    assert t.pair == "XBT/USD"
    assert t.last == 50050.5
    assert t.volume_24h == 250.5


def test_parse_ignores_heartbeat_and_status():
    assert parse_ticker_message('{"channel":"heartbeat"}') is None
    assert parse_ticker_message({"channel": "status", "data": [{}]}) is None
    assert parse_ticker_message({"channel": "ticker", "data": []}) is None
