from fastapi.testclient import TestClient

from troodon import state_machine as sm
from troodon.exchange import ExchangeEngine
from troodon.identity import Identity
from troodon.node import create_app
from troodon.sdk import TroodonClient
from troodon.settlement import MockSettlement
from tests.helpers import dual_contract_engine, dual_contract_sdk


def _propose(engine, client, provider, timeouts):
    return engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="t1", timeouts=timeouts,
    )


def test_sweep_expires_overdue_escrowed_and_refunds():
    settlement = MockSettlement()
    engine = ExchangeEngine(settlement)
    client, provider = Identity.generate(), Identity.generate()
    ex = _propose(engine, client, provider, {"deliver": 10})
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")

    # 用注入的未来时间触发过期（确定性，无需 sleep）
    expired = engine.sweep(now_ts=ex.deadline_ts + 1)
    assert [e.exchange_id for e in expired] == [ex.exchange_id]
    assert ex.state == sm.EXPIRED_REFUNDED
    assert settlement.status(ex.escrow_handle) == "refunded"


def test_sweep_does_not_expire_before_deadline():
    engine = ExchangeEngine(MockSettlement())
    client, provider = Identity.generate(), Identity.generate()
    ex = _propose(engine, client, provider, {"deliver": 10000})
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    assert engine.sweep(now_ts=ex.deadline_ts - 1) == []
    assert ex.state == sm.ESCROWED


def test_no_timeout_means_never_expires():
    engine = ExchangeEngine(MockSettlement())
    client, provider = Identity.generate(), Identity.generate()
    ex = _propose(engine, client, provider, None)
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    assert ex.deadline_ts is None
    assert engine.sweep(now_ts=9_999_999_999) == []
    assert ex.state == sm.ESCROWED


def test_delivered_is_not_swept():
    """交付后不再自动超时退款（公平起见）。"""
    engine = ExchangeEngine(MockSettlement())
    client, provider = Identity.generate(), Identity.generate()
    ex = _propose(engine, client, provider, {"deliver": 0})
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"invoice_no": "A-1"})
    assert ex.deadline_ts is None
    assert engine.sweep(now_ts=9_999_999_999) == []
    assert ex.state == sm.DELIVERED


def test_admin_sweep_endpoint():
    app = create_app(seed=True, auth=False)
    tc = TestClient(app)
    client = TroodonClient("http://testserver", Identity.generate(), http=tc)
    provider = TroodonClient("http://testserver", Identity.generate(), http=tc)
    ex = client.propose(
        provider=provider.agent_id, resource_type="data.extraction.structured",
        quantity=1, rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="api-timeout",
        timeouts={"deliver": 0},
    )
    eid = ex["exchange_id"]
    dual_contract_sdk(client, provider, eid)
    client.escrow(eid, amount=100, currency="USD")
    swept = tc.post("/admin/sweep").json()
    assert eid in swept["expired"]
    assert client.get_exchange(eid)["state"] == "EXPIRED_REFUNDED"
