from fastapi.testclient import TestClient

from troodon.identity import Identity
from troodon.node import create_app
from troodon.reputation import ReputationLog
from tests.helpers import dual_contract_engine

GOOD = {"invoice_no": "F-1", "total": "100.00", "currency": "USD"}


def test_reputation_export_and_validate():
    node = Identity.generate()
    log = ReputationLog(node)
    app = create_app(seed=True, auth=False, reputation_store=log._store)
    tc = TestClient(app)
    engine = app.state.engine
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="fed-rep",
    )
    eid = ex.exchange_id
    dual_contract_engine(engine, eid, client, provider)
    engine.escrow(eid, amount=100, currency="USD")
    engine.deliver(eid, provider, GOOD)
    rule = app.state.rules.get("R-extract-invoice-v1")
    engine.verify(eid, rule=rule)
    engine.confirm(eid, client)

    bundle = tc.get("/reputation/export").json()
    assert bundle["entry_count"] >= 2

    r = tc.post("/v2/reputation/validate", json={"bundle": bundle})
    assert r.status_code == 200
    assert r.json()["valid"] is True


def test_reputation_import_returns_501_by_default():
    node = Identity.generate()
    log = ReputationLog(node)
    app = create_app(seed=True, auth=False, reputation_store=log._store)
    tc = TestClient(app)
    engine = app.state.engine
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="fed-imp",
    )
    eid = ex.exchange_id
    dual_contract_engine(engine, eid, client, provider)
    engine.escrow(eid, amount=100, currency="USD")
    engine.deliver(eid, provider, GOOD)
    rule = app.state.rules.get("R-extract-invoice-v1")
    engine.verify(eid, rule=rule)
    engine.confirm(eid, client)

    bundle = app.state.reputation.export_bundle()
    r = tc.post("/v2/reputation/import", json={"bundle": bundle})
    assert r.status_code == 501
    assert r.json()["code"] == "E_NOT_IMPLEMENTED"


def test_cross_node_reputation_validate_in_plugfest_style():
    provider_app = create_app(seed=True, auth=False)
    client_app = create_app(seed=True, auth=False)
    provider_tc = TestClient(provider_app)
    client_tc = TestClient(client_app)

    engine = provider_app.state.engine
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="fed-cross",
    )
    eid = ex.exchange_id
    dual_contract_engine(engine, eid, client, provider)
    engine.escrow(eid, amount=100, currency="USD")
    engine.deliver(eid, provider, GOOD)
    rule = provider_app.state.rules.get("R-extract-invoice-v1")
    engine.verify(eid, rule=rule)
    engine.confirm(eid, client)

    bundle = provider_tc.get("/reputation/export").json()
    validated = client_tc.post("/v2/reputation/validate", json={"bundle": bundle}).json()
    assert validated["valid"] is True
