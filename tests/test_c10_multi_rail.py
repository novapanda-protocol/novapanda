"""C10-MR — Multi-rail registry (P1) + settlement_binding (P2)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from novapanda.config import NodeConfig
from novapanda.exchange import ExchangeEngine
from novapanda.identity import Identity
from novapanda.node import create_app_from_config
from novapanda.rail_registry import (
    SettlementBindingError,
    build_rail_registry,
    negotiate_rail,
)
from novapanda.settlement import MockSettlement
from novapanda.terms import sign_contract_ack
from tests.helpers import dual_contract_engine


# --- P1 ---


def test_c10_mr_multi_rail_registry_from_config():
    cfg = NodeConfig(
        settlement="mock",
        settlement_rails=["mock", "sandbox", "x402"],
        default_rail="sandbox",
    )
    reg = build_rail_registry(cfg)
    assert reg.list_keys() == ["mock", "sandbox", "x402"]
    assert reg.active_rail_id == "fiat-s1-sandbox"
    rails = reg.manifest_rails()
    assert len(rails) == 3
    ids = {r["id"] for r in rails}
    assert ids == {"mock", "fiat-s1-sandbox", "x402"}


def test_c10_mr_negotiate_prefers_intersection_and_preferred():
    node_rails = [
        {"id": "mock", "currencies": ["USD"], "amount_class": ["micro", "standard", "macro"]},
        {"id": "x402", "currencies": ["USDC"], "amount_class": ["micro", "standard"]},
        {"id": "fiat-s1-sandbox", "currencies": ["USD"], "amount_class": ["standard", "macro"]},
    ]
    terms = {
        "currency": "USDC",
        "amount_class": "micro",
        "preferred_rails": ["x402", "mock"],
    }
    assert negotiate_rail(
        terms=terms,
        node_rails=node_rails,
        client_rails=["x402", "mock"],
        provider_rails=["x402", "fiat-s1-sandbox"],
    ) == "x402"


def test_c10_mr_node_endpoints_multi_rail(monkeypatch):
    monkeypatch.setenv("NOVAPANDA_AUTH", "0")
    monkeypatch.setenv("NOVAPANDA_RAILS", "mock,x402,sandbox")
    monkeypatch.setenv("NOVAPANDA_DEFAULT_RAIL", "mock")
    app = create_app_from_config()
    tc = TestClient(app)
    rails = tc.get("/node/settlement/rails").json()
    assert rails["default_rail"] == "mock"
    assert len(rails["rails"]) == 3


def test_c10_mr_single_rail_backward_compat(monkeypatch):
    monkeypatch.delenv("NOVAPANDA_RAILS", raising=False)
    monkeypatch.setenv("NOVAPANDA_SETTLEMENT", "mock")
    reg = build_rail_registry(NodeConfig.from_env())
    assert reg.list_keys() == ["mock"]


def test_c10_mr_single_x402_still_requires_url(monkeypatch):
    monkeypatch.delenv("NOVAPANDA_RAILS", raising=False)
    monkeypatch.delenv("NOVAPANDA_X402_URL", raising=False)
    monkeypatch.setenv("NOVAPANDA_SETTLEMENT", "x402")
    monkeypatch.setenv("NOVAPANDA_SETTLEMENT_ENV", "sandbox")
    import pytest

    with pytest.raises(ValueError, match="NOVAPANDA_X402_URL"):
        build_rail_registry(NodeConfig.from_env())


# --- P2 ---


def _registry():
    return build_rail_registry(
        NodeConfig(
            settlement="mock",
            settlement_rails=["mock", "x402", "sandbox"],
            default_rail="mock",
        )
    )


def test_c10_mr_p2_binding_at_contract_prefers_x402():
    reg = _registry()
    engine = ExchangeEngine(reg.active_adapter, rail_registry=reg)
    client = Identity.generate()
    provider = Identity.generate()
    ex = engine.propose(
        client=client.agent_id,
        provider=provider.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 50, "currency": "USDC"},
        idempotency_key="p2-x402",
        settlement_terms={
            "currency": "USDC",
            "amount_class": "micro",
            "preferred_rails": ["x402", "mock"],
            "client_rails": ["x402", "mock"],
            "provider_rails": ["x402", "sandbox"],
        },
    )
    engine.contract(ex.exchange_id, party=client.agent_id, signature=sign_contract_ack(client, ex))
    bound = engine.contract(
        ex.exchange_id, party=provider.agent_id, signature=sign_contract_ack(provider, ex),
    )
    assert bound.state == "CONTRACTED"
    assert bound.settlement_binding["rail"] == "x402"


def test_c10_mr_p2_escrow_uses_bound_rail():
    reg = _registry()
    engine = ExchangeEngine(reg.active_adapter, rail_registry=reg)
    client = Identity.generate()
    provider = Identity.generate()
    ex = engine.propose(
        client=client.agent_id,
        provider=provider.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 10, "currency": "USD"},
        idempotency_key="p2-escrow",
        settlement_terms={"preferred_rails": ["mock"], "currency": "USD"},
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=10, currency="USD")
    assert engine.get(ex.exchange_id).settlement_binding["rail"] == "mock"
    assert engine.get(ex.exchange_id).escrow_handle is not None


def test_c10_mr_p2_rail_mismatch_on_contract():
    reg = _registry()
    engine = ExchangeEngine(reg.active_adapter, rail_registry=reg)
    client = Identity.generate()
    provider = Identity.generate()
    ex = engine.propose(
        client=client.agent_id,
        provider=provider.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 99, "currency": "JPY"},
        idempotency_key="p2-mismatch",
        settlement_terms={"currency": "JPY", "amount_class": "standard", "fallback": "reject"},
    )
    engine.contract(ex.exchange_id, party=client.agent_id, signature=sign_contract_ack(client, ex))
    import pytest

    with pytest.raises(SettlementBindingError):
        engine.contract(
            ex.exchange_id, party=provider.agent_id, signature=sign_contract_ack(provider, ex),
        )


def test_c10_mr_p2_http_e_rail_mismatch(monkeypatch):
    monkeypatch.setenv("NOVAPANDA_AUTH", "0")
    monkeypatch.setenv("NOVAPANDA_RAILS", "mock,x402")
    monkeypatch.setenv("NOVAPANDA_DEFAULT_RAIL", "mock")
    app = create_app_from_config()
    tc = TestClient(app)
    client = Identity.generate()
    provider = Identity.generate()
    body = {
        "client": client.agent_id,
        "provider": provider.agent_id,
        "resource_type": "data.extraction.structured",
        "quantity": 1,
        "rule_id": "R-extract-invoice-v1",
        "price": {"amount": 1, "currency": "JPY"},
        "idempotency_key": "http-mismatch",
        "settlement": {"currency": "JPY", "fallback": "reject"},
    }
    ex = tc.post("/exchanges", json=body).json()
    eid = ex["exchange_id"]
    tc.post(f"/exchanges/{eid}/contract", json={"signature": sign_contract_ack(client, ex)})
    r = tc.post(
        f"/exchanges/{eid}/contract",
        json={"signature": sign_contract_ack(provider, ex)},
    )
    assert r.status_code == 400
    payload = r.json()
    detail = payload.get("detail", payload)
    assert detail["code"] == "E_RAIL_MISMATCH"


def test_c10_mr_p2_default_binding_without_settlement_terms():
    reg = _registry()
    engine = ExchangeEngine(reg.active_adapter, rail_registry=reg)
    client = Identity.generate()
    provider = Identity.generate()
    ex = engine.propose(
        client=client.agent_id,
        provider=provider.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 5, "currency": "USD"},
        idempotency_key="p2-default",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    assert engine.get(ex.exchange_id).settlement_binding["rail"] == "mock"


def test_c10_mr_p2_single_engine_binds_mock():
    engine = ExchangeEngine(MockSettlement())
    client = Identity.generate()
    provider = Identity.generate()
    ex = engine.propose(
        client=client.agent_id,
        provider=provider.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 1, "currency": "USD"},
        idempotency_key="p2-single",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    assert engine.get(ex.exchange_id).settlement_binding["rail"] == "mock"


# --- P3: quote + micro routing ---


def test_c10_mr_p3_micro_amount_routes_x402():
    reg = build_rail_registry(
        NodeConfig(settlement="mock", settlement_rails=["mock", "x402", "sandbox"], default_rail="mock")
    )
    q = reg.quote(50, "USDC")
    assert q["amount_class"] == "micro"
    assert q["recommended_rail"] == "x402"


def test_c10_mr_p3_macro_amount_prefers_sandbox_over_x402():
    reg = build_rail_registry(
        NodeConfig(settlement="mock", settlement_rails=["mock", "x402", "sandbox"], default_rail="mock")
    )
    q = reg.quote(200_000, "USD")
    assert q["amount_class"] == "macro"
    assert q["recommended_rail"] == "fiat-s1-sandbox"


def test_c10_mr_p3_quote_endpoint(monkeypatch):
    monkeypatch.setenv("NOVAPANDA_AUTH", "0")
    monkeypatch.setenv("NOVAPANDA_RAILS", "mock,x402,sandbox")
    tc = TestClient(create_app_from_config())
    q = tc.get("/node/settlement/quote", params={"amount": 25, "currency": "USDC"}).json()
    assert q["recommended_rail"] == "x402"
    assert any(x["rail"] == "x402" and x["eligible"] for x in q["quotes"])


def test_c10_mr_p3_negotiate_preview(monkeypatch):
    monkeypatch.setenv("NOVAPANDA_AUTH", "0")
    monkeypatch.setenv("NOVAPANDA_RAILS", "mock,x402,sandbox")
    tc = TestClient(create_app_from_config())
    r = tc.post(
        "/node/settlement/negotiate",
        json={
            "amount": 50,
            "currency": "USDC",
            "settlement": {
                "preferred_rails": ["x402"],
                "client_rails": ["x402", "mock"],
                "provider_rails": ["x402"],
            },
        },
    ).json()
    assert r["binding_preview"]["rail"] == "x402"


def test_c10_mr_p3_auto_amount_class_in_binding():
    reg = build_rail_registry(
        NodeConfig(settlement="mock", settlement_rails=["mock", "x402"], default_rail="mock")
    )
    from novapanda.rail_registry import finalize_settlement_binding

    binding = finalize_settlement_binding(
        settlement_terms={"preferred_rails": ["x402", "mock"]},
        price={"amount": 30, "currency": "USDC"},
        node_rails=reg.manifest_rails(),
    )
    assert binding["amount_class"] == "micro"
    assert binding["rail"] == "x402"
