import pytest

from troodon import state_machine as sm
from troodon import vdc as V
from troodon.exchange import ExchangeEngine, ExchangeError
from troodon.identity import Identity
from troodon.settlement import MockSettlement
from tests.helpers import dual_contract_engine


class RejectAllVerifier:
    verifier_id = "verifier:reject-all"

    def verify(self, deliverable, rule):
        return {"passed": False, "verifier_id": self.verifier_id,
                "reason": "test reject", "verified_at": "2026-06-28T00:00:00Z"}


def _propose(engine, client, provider):
    return engine.propose(
        client=client.agent_id,
        provider=provider.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        rule_id="R-extract-schema-v1",
        price={"amount": 100, "currency": "USD"},
        idempotency_key="task-1",
    )


def test_happy_path_ends_settled_with_valid_vdc():
    client, provider = Identity.generate(), Identity.generate()
    settlement = MockSettlement()
    engine = ExchangeEngine(settlement)

    ex = _propose(engine, client, provider)
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"invoice_no": "A-001"})
    engine.verify(ex.exchange_id)
    ex = engine.confirm(ex.exchange_id, client)

    assert ex.state == sm.SETTLED
    assert V.is_valid_settled(ex.vdc) is True
    assert settlement.status(ex.escrow_handle) == "settled"


def test_reject_path_refunds_escrow():
    client, provider = Identity.generate(), Identity.generate()
    settlement = MockSettlement()
    engine = ExchangeEngine(settlement, verifier=RejectAllVerifier())

    ex = _propose(engine, client, provider)
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"invoice_no": "A-001"})
    ex = engine.verify(ex.exchange_id)

    assert ex.state == sm.REJECTED
    assert settlement.status(ex.escrow_handle) == "refunded"
    assert ex.verify_result["passed"] is False


def test_illegal_transition_deliver_before_escrow():
    client, provider = Identity.generate(), Identity.generate()
    engine = ExchangeEngine(MockSettlement())
    ex = _propose(engine, client, provider)
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    with pytest.raises(sm.StateError):
        engine.deliver(ex.exchange_id, provider, {"x": 1})


def test_cancel_refunds_when_escrowed():
    client, provider = Identity.generate(), Identity.generate()
    settlement = MockSettlement()
    engine = ExchangeEngine(settlement)
    ex = _propose(engine, client, provider)
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    ex = engine.cancel(ex.exchange_id)
    assert ex.state == sm.CANCELLED
    assert settlement.status(ex.escrow_handle) == "refunded"


def test_expire_refunds():
    client, provider = Identity.generate(), Identity.generate()
    settlement = MockSettlement()
    engine = ExchangeEngine(settlement)
    ex = _propose(engine, client, provider)
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    ex = engine.expire(ex.exchange_id)
    assert ex.state == sm.EXPIRED_REFUNDED
    assert settlement.status(ex.escrow_handle) == "refunded"


def test_idempotent_propose_returns_same_exchange():
    client, provider = Identity.generate(), Identity.generate()
    engine = ExchangeEngine(MockSettlement())
    a = _propose(engine, client, provider)
    b = _propose(engine, client, provider)
    assert a.exchange_id == b.exchange_id


def test_escrow_amount_mismatch_rejected():
    client, provider = Identity.generate(), Identity.generate()
    engine = ExchangeEngine(MockSettlement())
    ex = _propose(engine, client, provider)
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    with pytest.raises(ExchangeError):
        engine.escrow(ex.exchange_id, amount=999, currency="USD")


def test_verify_in_wrong_state_does_not_refund():
    """回归：未交付就 verify（且验收会拒）不得先退款再抛异常。"""
    client, provider = Identity.generate(), Identity.generate()
    settlement = MockSettlement()
    engine = ExchangeEngine(settlement, verifier=RejectAllVerifier())
    ex = _propose(engine, client, provider)
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    handle = ex.escrow_handle
    with pytest.raises(sm.StateError):
        engine.verify(ex.exchange_id)  # 当前 ESCROWED，非法
    assert settlement.status(handle) == "held"  # 未被错误退款
    assert ex.state == sm.ESCROWED


def test_cancel_on_settled_raises_and_keeps_settled():
    """回归：对已结算单 cancel 必须抛异常，且不得二次退款。"""
    client, provider = Identity.generate(), Identity.generate()
    settlement = MockSettlement()
    engine = ExchangeEngine(settlement)
    ex = _propose(engine, client, provider)
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"invoice_no": "A-001"})
    engine.verify(ex.exchange_id)
    engine.confirm(ex.exchange_id, client)
    with pytest.raises(sm.StateError):
        engine.cancel(ex.exchange_id)
    assert settlement.status(ex.escrow_handle) == "settled"


def test_wrong_provider_cannot_deliver():
    client, provider = Identity.generate(), Identity.generate()
    intruder = Identity.generate()
    engine = ExchangeEngine(MockSettlement())
    ex = _propose(engine, client, provider)
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    with pytest.raises(ExchangeError):
        engine.deliver(ex.exchange_id, intruder, {"x": 1})
