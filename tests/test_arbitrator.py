import pytest
from fastapi.testclient import TestClient

from troodon import state_machine as sm
from troodon.exchange import ExchangeEngine
from troodon.identity import Identity
from troodon.node import create_app
from troodon.settlement import MockSettlement
from troodon.sdk import TroodonClient
from tests.helpers import dual_contract_engine


def _to_verified(engine, client, provider, idem="arb-1"):
    from troodon.registry import load_default_registries

    _, rules = load_default_registries()
    rule = rules.get("R-extract-schema-v1")
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R-extract-schema-v1",
        price={"amount": 100, "currency": "USD"}, idempotency_key=idem,
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"invoice_no": "A-1"})
    engine.verify(ex.exchange_id, rule=rule)
    return ex


def test_arbitrator_only_can_resolve():
    arb = Identity.generate()
    app = create_app(seed=True, auth=True, arbitrator_id=arb.agent_id)
    tc = TestClient(app)
    engine = app.state.engine
    client_id, provider_id = Identity.generate(), Identity.generate()
    ex = _to_verified(engine, client_id, provider_id)
    engine.dispute(ex.exchange_id, by=client_id.agent_id, reason="x")

    client = TroodonClient("http://testserver", client_id, http=tc)
    with pytest.raises(Exception):
        client._post(f"/exchanges/{ex.exchange_id}/resolve", {"outcome": "settle"})

    arb_client = TroodonClient("http://testserver", arb, http=tc)
    r = arb_client._post(f"/exchanges/{ex.exchange_id}/resolve", {"outcome": "settle"})
    assert r["state"] == sm.SETTLED


def test_arbitrator_blocks_unauthenticated_resolve():
    arb = Identity.generate()
    app = create_app(seed=True, auth=False, arbitrator_id=arb.agent_id)
    tc = TestClient(app)
    engine = app.state.engine
    client, provider = Identity.generate(), Identity.generate()
    ex = _to_verified(engine, client, provider)
    engine.dispute(ex.exchange_id, by=client.agent_id, reason="x")
    r = tc.post(f"/exchanges/{ex.exchange_id}/resolve", json={"outcome": "settle"})
    assert r.status_code == 403


def test_resolve_without_arbitrator_allows_parties():
    app = create_app(seed=True, auth=False, arbitrator_id=None)
    tc = TestClient(app)
    engine = app.state.engine
    client, provider = Identity.generate(), Identity.generate()
    ex = _to_verified(engine, client, provider)
    engine.dispute(ex.exchange_id, by=client.agent_id, reason="x")
    r = tc.post(f"/exchanges/{ex.exchange_id}/resolve", json={"outcome": "reject"})
    assert r.status_code == 200
    assert r.json()["state"] == "REJECTED"
