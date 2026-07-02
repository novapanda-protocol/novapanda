import pytest
from fastapi.testclient import TestClient

from novapanda.identity import Identity
from novapanda.node import create_app
from tests.helpers import dual_contract_engine

GOOD = {"invoice_no": "G-1", "total": "100.00", "currency": "USD"}


def _settled_provider(app, provider: Identity) -> str:
    engine = app.state.engine
    client = Identity.generate()
    ex = engine.propose(
        client=client.agent_id,
        provider=provider.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"},
        idempotency_key=f"gate-{provider.agent_id[-8:]}",
    )
    eid = ex.exchange_id
    dual_contract_engine(engine, eid, client, provider)
    engine.escrow(eid, amount=100, currency="USD")
    engine.deliver(eid, provider, GOOD)
    rule = app.state.rules.get("R-extract-invoice-v1")
    engine.verify(eid, rule=rule)
    engine.confirm(eid, client)
    return provider.agent_id


def test_reputation_gate_disabled_allows():
    from novapanda.reputation_gate import check_reputation_gate

    app = create_app(seed=True, auth=False)
    gate = check_reputation_gate(
        app.state.reputation,
        "ed25519:unknown",
        min_score=None,
    )
    assert gate["allowed"] is True


def test_reputation_gate_blocks_low_score():
    app = create_app(seed=True, auth=False, reputation_min_score=1.01)
    provider = Identity.generate()
    _settled_provider(app, provider)
    tc = TestClient(app)
    client = Identity.generate()
    r = tc.post("/exchanges", json={
        "client": client.agent_id,
        "provider": provider.agent_id,
        "resource_type": "data.extraction.structured",
        "quantity": 1,
        "rule_id": "R-extract-invoice-v1",
        "price": {"amount": 100, "currency": "USD"},
        "idempotency_key": "gate-block-propose",
    })
    assert r.status_code == 403
    assert r.json()["code"] == "E_REPUTATION_LOW"


def test_reputation_gate_allows_no_history():
    app = create_app(seed=True, auth=False, reputation_min_score=0.99)
    tc = TestClient(app)
    client = Identity.generate()
    provider = Identity.generate()
    r = tc.post("/exchanges", json={
        "client": client.agent_id,
        "provider": provider.agent_id,
        "resource_type": "data.extraction.structured",
        "quantity": 1,
        "rule_id": "R-extract-invoice-v1",
        "price": {"amount": 100, "currency": "USD"},
        "idempotency_key": "gate-new-provider",
    })
    assert r.status_code == 201


def test_reputation_gate_strict_blocks_no_history():
    app = create_app(seed=True, auth=False, reputation_min_score=0.5, reputation_gate_strict=True)
    tc = TestClient(app)
    client = Identity.generate()
    provider = Identity.generate()
    r = tc.post("/exchanges", json={
        "client": client.agent_id,
        "provider": provider.agent_id,
        "resource_type": "data.extraction.structured",
        "quantity": 1,
        "rule_id": "R-extract-invoice-v1",
        "price": {"amount": 100, "currency": "USD"},
        "idempotency_key": "gate-strict-new",
    })
    assert r.status_code == 403
    assert r.json()["code"] == "E_REPUTATION_LOW"


def test_config_rep_min_score_from_env(monkeypatch):
    from novapanda.config import NodeConfig

    monkeypatch.setenv("NOVAPANDA_REP_MIN_SCORE", "0.75")
    cfg = NodeConfig.from_env()
    assert cfg.reputation_min_score == 0.75
