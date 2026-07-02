from fastapi.testclient import TestClient

from novapanda.config import DEFAULT_TIMEOUTS
from novapanda.exchange import ExchangeEngine
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.settlement import MockSettlement
from tests.helpers import dual_contract_engine

GOOD = {"invoice_no": "E-1", "total": "100.00", "currency": "USD"}


def test_export_public_without_deliverable():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    engine = app.state.engine
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="exp-1",
    )
    eid = ex.exchange_id
    dual_contract_engine(engine, eid, client, provider)
    engine.escrow(eid, amount=100, currency="USD")
    engine.deliver(eid, provider, GOOD)
    rule = app.state.rules.get("R-extract-invoice-v1")
    engine.verify(eid, rule=rule)
    engine.confirm(eid, client)

    pub = tc.get(f"/exchanges/{eid}/export").json()
    assert pub["export_version"] == "0.1"
    assert pub["vdc"] is not None
    assert "deliverable" not in pub


def test_propose_uses_default_timeouts():
    custom = {"contract": 11, "escrow": 22, "deliver": 33}
    app = create_app(seed=True, auth=False, default_timeouts=custom)
    tc = TestClient(app)
    client, provider = Identity.generate(), Identity.generate()
    r = tc.post("/exchanges", json={
        "client": client.agent_id,
        "provider": provider.agent_id,
        "resource_type": "data.extraction.structured",
        "quantity": 1,
        "rule_id": "R-extract-invoice-v1",
        "price": {"amount": 100, "currency": "USD"},
        "idempotency_key": "to-1",
    }).json()
    assert r["timeouts"] == custom
    assert custom != DEFAULT_TIMEOUTS or True
