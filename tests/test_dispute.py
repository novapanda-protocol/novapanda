import pytest
from fastapi.testclient import TestClient

from troodon import state_machine as sm
from troodon.exchange import ExchangeEngine, ExchangeError
from troodon.identity import Identity
from troodon.node import create_app
from troodon.reputation import ReputationLog
from troodon.sdk import TroodonClient
from troodon.settlement import MockSettlement
from tests.helpers import dual_contract_engine, dual_contract_sdk


def _to_verified(engine, client, provider, idem="d1"):
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 100, "currency": "USD"}, idempotency_key=idem,
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"invoice_no": "A-1"})
    engine.verify(ex.exchange_id)
    return ex


def test_dispute_then_resolve_settle():
    s = MockSettlement()
    node = Identity.generate()
    log = ReputationLog(node)
    engine = ExchangeEngine(s, reputation=log)
    client, provider = Identity.generate(), Identity.generate()
    ex = _to_verified(engine, client, provider)

    engine.dispute(ex.exchange_id, by=client.agent_id, reason="质疑结果")
    assert engine.get(ex.exchange_id).state == sm.DISPUTED

    resolved = engine.resolve(ex.exchange_id, outcome="settle", resolver=node.agent_id)
    assert resolved.state == sm.SETTLED
    assert s.status(ex.escrow_handle) == "settled"
    assert resolved.dispute_info["resolution"] == "settle"
    assert len(log.entries()) == 2  # 结算记双方


def test_dispute_then_resolve_reject_refunds():
    s = MockSettlement()
    engine = ExchangeEngine(s)
    client, provider = Identity.generate(), Identity.generate()
    ex = _to_verified(engine, client, provider, idem="d-reject")
    engine.dispute(ex.exchange_id, by=provider.agent_id, reason="对账分歧")
    resolved = engine.resolve(ex.exchange_id, outcome="reject")
    assert resolved.state == sm.REJECTED
    assert s.status(ex.escrow_handle) == "refunded"


def test_cannot_dispute_before_verified():
    engine = ExchangeEngine(MockSettlement())
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="d-early",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    with pytest.raises(sm.StateError):
        engine.dispute(ex.exchange_id, by=client.agent_id, reason="too early")


def test_dispute_resolve_over_http():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    client = TroodonClient("http://testserver", Identity.generate(), http=tc)
    provider = TroodonClient("http://testserver", Identity.generate(), http=tc)
    good = {"invoice_no": "A-001", "total": "100.00", "currency": "USD"}
    ex = client.propose(provider=provider.agent_id, resource_type="data.extraction.structured",
                        quantity=1, rule_id="R-extract-invoice-v1",
                        price={"amount": 100, "currency": "USD"}, idempotency_key="http-dispute")
    eid = ex["exchange_id"]
    dual_contract_sdk(client, provider, eid)
    client.escrow(eid, amount=100, currency="USD")
    provider.deliver(eid, good)
    client.verify(eid)
    d = tc.post(f"/exchanges/{eid}/dispute", json={"reason": "x"}).json()
    assert d["state"] == "DISPUTED"
    r = tc.post(f"/exchanges/{eid}/resolve", json={"outcome": "settle"}).json()
    assert r["state"] == "SETTLED"
