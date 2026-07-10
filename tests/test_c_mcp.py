"""C-MCP conformance vectors — MCP binding ≡ SDK semantics."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from novapanda import vdc as V
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.reverify import reverify
from novapanda.sdk import NovaPandaClient
from novapanda.surfaces import MCPBinding
from tests.helpers import dual_contract_sdk

RULE_ID = "R-extract-invoice-v1"
RESOURCE = "data.extraction.structured"
PRICE = {"amount": 100, "currency": "USD"}
GOOD = {"invoice_no": "A-001", "total": "100.00", "currency": "USD"}


@pytest.fixture
def clients():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    client = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    provider = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    return client, provider, tc


def _sdk_settled(client: NovaPandaClient, provider: NovaPandaClient, idem: str) -> dict:
    ex = client.propose(
        provider=provider.agent_id,
        resource_type=RESOURCE,
        quantity=1,
        rule_id=RULE_ID,
        price=PRICE,
        idempotency_key=idem,
    )
    eid = ex["exchange_id"]
    dual_contract_sdk(client, provider, eid)
    client.escrow(eid, amount=100, currency="USD")
    provider.deliver(eid, deliverable=GOOD)
    client.verify(eid)
    return client.confirm(eid)


def _mcp_settled(client: NovaPandaClient, provider: NovaPandaClient, idem: str) -> dict:
    cb, pb = MCPBinding(client), MCPBinding(provider)
    ex = cb.call_tool(
        "novapanda.propose",
        {
            "provider": provider.agent_id,
            "resource_type": RESOURCE,
            "quantity": 1,
            "rule_id": RULE_ID,
            "price": PRICE,
            "idempotency_key": idem,
        },
    )
    eid = ex["exchange_id"]
    cb.call_tool("novapanda.contract", {"exchange_id": eid})
    pb.call_tool("novapanda.contract", {"exchange_id": eid})
    cb.call_tool("novapanda.escrow", {"exchange_id": eid, "amount": 100, "currency": "USD"})
    pb.call_tool("novapanda.deliver", {"exchange_id": eid, "deliverable": GOOD})
    cb.call_tool("novapanda.verify", {"exchange_id": eid})
    return cb.call_tool("novapanda.confirm", {"exchange_id": eid})


def test_c_mcp_01_full_lifecycle_equivalent_to_sdk(clients):
    """C-MCP-01: MCP path ≡ SDK path (state, vdc_id, result_hash)."""
    client, provider, _ = clients
    sdk = _sdk_settled(client, provider, "c-mcp-sdk")
    mcp = _mcp_settled(client, provider, "c-mcp-mcp")

    assert sdk["state"] == mcp["state"] == "SETTLED"
    assert sdk["vdc"]["vdc_id"] != mcp["vdc"]["vdc_id"]  # distinct exchanges
    assert sdk["vdc"]["result_hash"] == mcp["vdc"]["result_hash"]
    assert V.is_valid_settled(sdk["vdc"]) is True
    assert V.is_valid_settled(mcp["vdc"]) is True
    assert all(v is not False for v in reverify(mcp["vdc"], GOOD).values())


def test_c_mcp_02_forbidden_tools_absent():
    """C-MCP-02: admin / force-settle tools must not exist on readonly binding."""
    from novapanda.bindings.mcp_tools import FORBIDDEN_TOOLS, list_tools

    names = {t["name"] for t in list_tools()}
    for forbidden in FORBIDDEN_TOOLS:
        assert forbidden not in names


def test_c_mcp_03_readonly_manifest_matches_http(clients):
    """C-MCP-03: np_manifest ≡ GET /.well-known/novapanda.json."""
    from novapanda.bindings.mcp_tools import dispatch_readonly

    _, _, tc = clients
    via_mcp = dispatch_readonly("np_manifest", base_url="http://testserver", http=tc)
    via_http = tc.get("/.well-known/novapanda.json").json()
    assert via_mcp.get("protocol") == via_http.get("protocol") == "novapanda"
    assert via_mcp.get("agent_id") == via_http.get("agent_id")


def test_c_mcp_04_operator_bearer_cannot_propose_without_agent_auth():
    """C-MCP-04: Operator session ≠ Agent signature on write paths."""
    from novapanda.bindings.mcp_tools import MCP_TOOL_CATALOG, dispatch_readonly

    app = create_app(seed=True, auth=True)
    tc = TestClient(app)
    client = Identity.generate()
    provider = Identity.generate()

    reg = tc.post(
        "/operator/register",
        json={
            "email": "mcp-op@example.com",
            "display_name": "Op",
            "password": "secret-pass",
            "accept_terms": True,
        },
    )
    otp = reg.json()["otp_dev"]
    tc.post("/operator/verify", json={"email": "mcp-op@example.com", "otp": otp})
    login = tc.post(
        "/operator/login",
        json={"email": "mcp-op@example.com", "password": "secret-pass"},
    )
    token = login.json()["session_token"]

    propose_body = {
        "client": client.agent_id,
        "provider": provider.agent_id,
        "resource_type": RESOURCE,
        "quantity": 1,
        "rule_id": RULE_ID,
        "price": PRICE,
        "idempotency_key": "c-mcp-04",
    }
    denied = tc.post(
        "/exchanges",
        json=propose_body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert denied.status_code == 401
    assert denied.json()["code"] == "E_AUTH_MISSING"

    by_name = {t["name"]: t for t in MCP_TOOL_CATALOG}
    assert by_name["np_propose"]["auth"] == "agent"
    assert by_name["np_confirm"]["auth"] == "agent"
    with pytest.raises(ValueError, match="write-only"):
        dispatch_readonly("np_propose", base_url="http://testserver", http=tc)


def test_c_mcp_05_get_exchange_honest(clients):
    """C-MCP-05: np_get_exchange ≡ GET /exchanges/{id}; no fake settlement."""
    from novapanda.bindings.mcp_tools import dispatch_readonly

    client, provider, tc = clients
    ex = client.propose(
        provider=provider.agent_id,
        resource_type=RESOURCE,
        quantity=1,
        rule_id=RULE_ID,
        price=PRICE,
        idempotency_key="c-mcp-05-proposed",
    )
    eid = ex["exchange_id"]
    via_http = tc.get(f"/exchanges/{eid}").json()
    via_mcp = dispatch_readonly(
        "np_get_exchange",
        base_url="http://testserver",
        http=tc,
        params={"exchange_id": eid},
    )
    assert via_mcp == via_http
    assert via_mcp.get("settlement_receipt") is None
    assert via_mcp.get("vdc") is None

    settled = _sdk_settled(client, provider, "c-mcp-05-settled")
    eid2 = settled["exchange_id"]
    via_http2 = tc.get(f"/exchanges/{eid2}").json()
    via_mcp2 = dispatch_readonly(
        "np_get_exchange",
        base_url="http://testserver",
        http=tc,
        params={"exchange_id": eid2},
    )
    assert via_mcp2 == via_http2
    assert via_mcp2["state"] == "SETTLED"
    assert via_mcp2.get("settlement_receipt") is not None
