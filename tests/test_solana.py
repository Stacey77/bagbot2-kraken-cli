import httpx
import pytest

from bagbot.solana import SolanaAdapter, SolanaError


def _adapter(handler):
    return SolanaAdapter(http_client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_get_balance_parses_lamports():
    def handler(request: httpx.Request) -> httpx.Response:
        import json
        body = json.loads(request.read())
        assert body["method"] == "getBalance"
        assert body["params"] == ["addr123"]
        return httpx.Response(200, json={
            "jsonrpc": "2.0", "id": body["id"],
            "result": {"context": {"slot": 1}, "value": 2_500_000_000},
        })

    adapter = _adapter(handler)
    assert adapter.get_balance("addr123") == 2_500_000_000
    assert adapter.get_balance_sol("addr123") == 2.5


def test_rpc_error_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "jsonrpc": "2.0", "id": 1,
            "error": {"code": -32602, "message": "Invalid param"},
        })

    with pytest.raises(SolanaError, match="Invalid param"):
        _adapter(handler).get_balance("bad")


def test_connect_returns_version():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "jsonrpc": "2.0", "id": 1,
            "result": {"solana-core": "1.18.0", "feature-set": 123},
        })

    assert _adapter(handler).connect()["solana-core"] == "1.18.0"


def test_transfer_rejects_nonpositive_lamports():
    adapter = _adapter(lambda r: httpx.Response(200, json={"result": None}))
    with pytest.raises(ValueError):
        adapter.transfer("dest", 0)
