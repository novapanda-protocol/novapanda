from troodon import state_machine as sm
from troodon.exchange import ExchangeEngine
from troodon.identity import Identity
from troodon.settlement import MockSettlement
from tests.helpers import dual_contract_engine


def test_confirm_timeout_sweeps_verified():
    settlement = MockSettlement()
    engine = ExchangeEngine(settlement)
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="cto-1",
        timeouts={"confirm": 30},
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"invoice_no": "A-1"})
    engine.verify(ex.exchange_id)
    assert ex.state == sm.VERIFIED
    assert ex.deadline_ts is not None

    expired = engine.sweep(now_ts=ex.deadline_ts + 1)
    assert [e.exchange_id for e in expired] == [ex.exchange_id]
    assert ex.state == sm.EXPIRED_REFUNDED
    assert settlement.status(ex.escrow_handle) == "refunded"


def test_no_confirm_timeout_keeps_verified():
    engine = ExchangeEngine(MockSettlement())
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="cto-2",
        timeouts={"verify": 0},
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"invoice_no": "A-1"})
    engine.verify(ex.exchange_id)
    assert ex.deadline_ts is None
    assert engine.sweep(now_ts=9_999_999_999) == []
    assert ex.state == sm.VERIFIED
