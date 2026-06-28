import json

import pytest
from fastapi.testclient import TestClient

from troodon.config import NodeConfig
from troodon.identity import Identity
from troodon.node import create_app
from tests.helpers import dual_contract_engine

GOOD = {"invoice_no": "A-1", "total": "100.00", "currency": "USD"}


def _settled_provider(app, provider: Identity) -> str:
    engine = app.state.engine
    client = Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"},
        idempotency_key=f"rw-{provider.agent_id[-8:]}",
    )
    eid = ex.exchange_id
    dual_contract_engine(engine, eid, client, provider)
    engine.escrow(eid, amount=100, currency="USD")
    engine.deliver(eid, provider, GOOD)
    rule = app.state.rules.get("R-extract-invoice-v1")
    engine.verify(eid, rule=rule)
    engine.confirm(eid, client)
    return provider.agent_id


def test_node_config_parses_rep_weights(monkeypatch):
    monkeypatch.setenv("TROODON_REP_WEIGHTS", '{"ed25519:NodeA":2.0}')
    cfg = NodeConfig.from_env()
    assert cfg.reputation_weights == {"ed25519:NodeA": 2.0}


def test_score_endpoint_uses_default_weights_from_app_state():
    app = create_app(seed=True, auth=False)
    provider = Identity.generate()
    agent_id = _settled_provider(app, provider)
    node_id = app.state.node_id
    app.state.reputation_weights = {node_id: 3.0}
    tc = TestClient(app)
    r = tc.get(f"/v2/reputation/{agent_id}/score")
    assert r.status_code == 200
    assert r.json()["weighted_settled"] >= 3.0


def test_score_endpoint_merges_query_over_defaults():
    app = create_app(seed=True, auth=False, reputation_weights={})
    provider = Identity.generate()
    agent_id = _settled_provider(app, provider)
    node_id = app.state.node_id
    tc = TestClient(app)
    r = tc.get(
        f"/v2/reputation/{agent_id}/score",
        params={"weights": json.dumps({node_id: 5.0})},
    )
    assert r.json()["weighted_settled"] >= 5.0
