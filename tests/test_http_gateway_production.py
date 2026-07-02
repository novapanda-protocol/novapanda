import httpx

from novapanda.http_gateway_base import HttpGatewayClient
from novapanda.settlement import SettlementError


def test_gateway_retries_on_500():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if request.url.path == "/authorize":
            if calls["n"] < 2:
                return httpx.Response(503, json={"error": "busy"})
            return httpx.Response(200, json={"ref": "ref-1"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, base_url="http://testserver")
    gw = HttpGatewayClient("http://testserver", http=http, max_retries=2, rail_name="test")
    ref = gw.authorize("ex-1", 100, "USD")
    assert ref == "ref-1"
    assert calls["n"] == 2


def test_gateway_sends_api_key_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"ref": "r1"})

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, base_url="http://testserver")
    HttpGatewayClient(
        "http://testserver",
        http=http,
        api_key="secret-key",
        max_retries=0,
        rail_name="test",
    ).authorize("ex-1", 1, "USD")
    assert seen["auth"] == "Bearer secret-key"
