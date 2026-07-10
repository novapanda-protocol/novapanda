"""S1 沙箱 HTTP 轨 — fiat-s1-sandbox + 伙伴网关（fake 或真 URL）。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from novapanda.config import NodeConfig
from novapanda.exchange import ExchangeEngine
from novapanda.fiat_fake import create_fiat_fake_app
from novapanda.fiat_gateway import HttpFiatGateway
from novapanda.identity import Identity
from novapanda.rail_registry import build_rail_registry
from novapanda.settlement import S1HttpSandboxSettlement
from tests.helpers import dual_contract_engine


def test_s1_http_sandbox_settlement_class():
    fake = TestClient(create_fiat_fake_app())
    gw = HttpFiatGateway("http://testserver", http=fake)
    s = S1HttpSandboxSettlement(gw, partner="test-psp")
    h = s.escrow("ex-s1h", 42, "USD")
    receipt = s.settle(h)
    assert receipt["rail"] == "fiat-s1-sandbox"
    assert receipt["environment"] == "sandbox"
    assert receipt["licensed"] is False
    assert receipt["partner"] == "test-psp"
    rail = s.manifest_rail()
    assert rail["transport"] == "http"
    assert "api_base" not in rail


def test_s1_http_sandbox_full_exchange_via_registry():
    fake = TestClient(create_fiat_fake_app())
    gw = HttpFiatGateway("http://testserver", http=fake)
    cfg = NodeConfig(
        settlement="sandbox",
        settlement_rails=["sandbox", "mock"],
        default_rail="sandbox",
        fiat_gateway_url="http://fake.example",
    )
    reg = build_rail_registry(cfg)
    adapter = reg.get("sandbox")
    assert isinstance(adapter, S1HttpSandboxSettlement)
    # 注入测试用 http client（绕过真实 URL）
    adapter.gateway = gw  # type: ignore[attr-defined]

    engine = ExchangeEngine(reg.active_adapter, rail_registry=reg)
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id,
        provider=provider.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"},
        idempotency_key="s1-http",
        settlement_terms={"preferred_rails": ["fiat-s1-sandbox"], "currency": "USD"},
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    bound = engine.get(ex.exchange_id)
    assert bound.settlement_binding["rail"] == "fiat-s1-sandbox"
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"invoice_no": "S1", "total": "100.00", "currency": "USD"})
    engine.verify(ex.exchange_id)
    settled = engine.confirm(ex.exchange_id, client)
    assert settled.state == "SETTLED"
    assert settled.settlement_receipt["rail"] == "fiat-s1-sandbox"
    assert settled.settlement_receipt["environment"] == "sandbox"
