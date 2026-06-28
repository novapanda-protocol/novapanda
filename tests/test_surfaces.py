"""一致性证明：同一笔交割经任意接入面，产出的 VDC 完全等价、可独立复验。"""

import pytest
from fastapi.testclient import TestClient

from troodon import vdc as V
from troodon.identity import Identity
from troodon.node import create_app
from troodon.reverify import reverify
from troodon.sdk import TroodonClient
from tests.helpers import dual_contract_sdk
from troodon.surfaces import (
    A2ABinding,
    ExchangeSkill,
    MCPBinding,
    OPERATIONS_BY_NAME,
    ProviderAdapter,
    agent_card,
    mcp_tool_descriptors,
)

RULE_ID = "R-extract-invoice-v1"
RESOURCE = "data.extraction.structured"
PRICE = {"amount": 100, "currency": "USD"}
GOOD = {"invoice_no": "A-001", "total": "100.00", "currency": "USD"}


@pytest.fixture
def clients():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    client = TroodonClient("http://testserver", Identity.generate(), http=tc)
    provider = TroodonClient("http://testserver", Identity.generate(), http=tc)
    return client, provider


def _assert_settled_vdc(settled: dict):
    assert settled["state"] == "SETTLED"
    assert V.is_valid_settled(settled["vdc"]) is True
    assert all(v is not False for v in reverify(settled["vdc"], GOOD).values())


def test_surface_descriptor_parity():
    """MCP 工具 / A2A 技能 必须与统一操作集一一对应（不多不少）。"""
    ops = set(OPERATIONS_BY_NAME.keys())
    mcp_names = {d["name"].split("troodon.", 1)[-1] for d in mcp_tool_descriptors()}
    a2a_names = {s["id"] for s in agent_card()["skills"]}
    assert mcp_names == ops
    assert a2a_names == ops


def test_mcp_surface_full_lifecycle(clients):
    client, provider = clients
    cb, pb = MCPBinding(client), MCPBinding(provider)
    ex = cb.call_tool("troodon.propose", {
        "provider": provider.agent_id, "resource_type": RESOURCE, "quantity": 1,
        "rule_id": RULE_ID, "price": PRICE, "idempotency_key": "mcp-1",
    })
    eid = ex["exchange_id"]
    cb.call_tool("troodon.contract", {"exchange_id": eid})
    pb.call_tool("troodon.contract", {"exchange_id": eid})
    cb.call_tool("troodon.escrow", {"exchange_id": eid, "amount": 100, "currency": "USD"})
    pb.call_tool("troodon.deliver", {"exchange_id": eid, "deliverable": GOOD})
    cb.call_tool("troodon.verify", {"exchange_id": eid})
    settled = cb.call_tool("troodon.confirm", {"exchange_id": eid})
    _assert_settled_vdc(settled)


def test_a2a_surface_full_lifecycle(clients):
    client, provider = clients
    cb, pb = A2ABinding(client), A2ABinding(provider)
    ex = cb.handle("propose", {
        "provider": provider.agent_id, "resource_type": RESOURCE, "quantity": 1,
        "rule_id": RULE_ID, "price": PRICE, "idempotency_key": "a2a-1",
    })
    eid = ex["exchange_id"]
    cb.handle("contract", {"exchange_id": eid})
    pb.handle("contract", {"exchange_id": eid})
    cb.handle("escrow", {"exchange_id": eid, "amount": 100, "currency": "USD"})
    pb.handle("deliver", {"exchange_id": eid, "deliverable": GOOD})
    cb.handle("verify", {"exchange_id": eid})
    settled = cb.handle("confirm", {"exchange_id": eid})
    _assert_settled_vdc(settled)


def test_skill_surface_full_lifecycle(clients):
    client, provider = clients
    cs, ps = ExchangeSkill(client), ExchangeSkill(provider)
    ex = cs.run("propose", provider=provider.agent_id, resource_type=RESOURCE,
                quantity=1, rule_id=RULE_ID, price=PRICE, idempotency_key="skill-1")
    eid = ex["exchange_id"]
    cs.run("contract", exchange_id=eid)
    ps.run("contract", exchange_id=eid)
    cs.run("escrow", exchange_id=eid, amount=100, currency="USD")
    ps.run("deliver", exchange_id=eid, deliverable=GOOD)
    cs.run("verify", exchange_id=eid)
    settled = cs.run("confirm", exchange_id=eid)
    _assert_settled_vdc(settled)


def test_adapter_surface_provider_plugs_in_with_one_function(clients):
    """适配器：provider 只提供一个 work_fn 即可接入并交付。"""
    client, provider = clients
    # 外部系统：行业 Agent / OpenClaw / 爱马仕 …只需实现这一个函数
    calls = []

    def work_fn(request: dict):
        calls.append(request)
        assert request["resource_type"] == RESOURCE
        return GOOD

    adapter = ProviderAdapter(provider, work_fn)

    ex = client.propose(provider=provider.agent_id, resource_type=RESOURCE, quantity=1,
                        rule_id=RULE_ID, price=PRICE, idempotency_key="adapter-1")
    eid = ex["exchange_id"]
    dual_contract_sdk(client, provider, eid)
    client.escrow(eid, amount=100, currency="USD")
    adapter.fulfill(eid)            # 适配器拉取需求->产出->本地签名交付
    client.verify(eid)
    settled = client.confirm(eid)

    _assert_settled_vdc(settled)
    assert len(calls) == 1  # work_fn 被精确驱动一次


def test_all_surfaces_produce_equivalent_vdc_shape(clients):
    """跨接入面产出的 VDC 结构一致（同 rule/resource 下字段集合相同）。"""
    client, provider = clients

    def run_via_skill(idem):
        cs, ps = ExchangeSkill(client), ExchangeSkill(provider)
        ex = cs.run("propose", provider=provider.agent_id, resource_type=RESOURCE,
                    quantity=1, rule_id=RULE_ID, price=PRICE, idempotency_key=idem)
        eid = ex["exchange_id"]
        cs.run("contract", exchange_id=eid)
        ps.run("contract", exchange_id=eid)
        cs.run("escrow", exchange_id=eid, amount=100, currency="USD")
        ps.run("deliver", exchange_id=eid, deliverable=GOOD)
        cs.run("verify", exchange_id=eid)
        return cs.run("confirm", exchange_id=eid)["vdc"]

    def run_via_mcp(idem):
        cb, pb = MCPBinding(client), MCPBinding(provider)
        ex = cb.call_tool("troodon.propose", {
            "provider": provider.agent_id, "resource_type": RESOURCE, "quantity": 1,
            "rule_id": RULE_ID, "price": PRICE, "idempotency_key": idem})
        eid = ex["exchange_id"]
        cb.call_tool("troodon.contract", {"exchange_id": eid})
        pb.call_tool("troodon.contract", {"exchange_id": eid})
        cb.call_tool("troodon.escrow", {"exchange_id": eid, "amount": 100, "currency": "USD"})
        pb.call_tool("troodon.deliver", {"exchange_id": eid, "deliverable": GOOD})
        cb.call_tool("troodon.verify", {"exchange_id": eid})
        return cb.call_tool("troodon.confirm", {"exchange_id": eid})["vdc"]

    v1 = run_via_skill("eq-skill")
    v2 = run_via_mcp("eq-mcp")
    assert set(v1.keys()) == set(v2.keys())
    assert v1["resource_type"] == v2["resource_type"]
    assert set(v1["signatures"].keys()) == set(v2["signatures"].keys())
    assert "provider_sig" in v1["signatures"] and "client_sig" in v1["signatures"]
