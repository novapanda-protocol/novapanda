"""C-NODE-R — recover + pending settlement intent (NP-NODE)."""

from __future__ import annotations

from novapanda import state_machine as sm
from novapanda.exchange import ExchangeEngine
from novapanda.identity import Identity
from novapanda.settlement import MockSettlement, SettlementError
from novapanda.store import SQLiteStore
from tests.helpers import dual_contract_engine


class _FailingSettle(MockSettlement):
    def settle(self, handle: str) -> dict:
        raise SettlementError("adapter_down")


def _to_verified(engine, client, provider, idem="cnr-1"):
    ex = engine.propose(
        client=client.agent_id,
        provider=provider.agent_id,
        resource_type="data.extraction.structured",
        quantity=1,
        rule_id="R1",
        price={"amount": 100, "currency": "USD"},
        idempotency_key=idem,
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"invoice_no": "A-1"})
    engine.verify(ex.exchange_id)
    return ex


def test_c_node_r_01_crash_after_pending_recover_settles(tmp_path):
    db = str(tmp_path / "cnr.db")
    s = MockSettlement()
    client, provider = Identity.generate(), Identity.generate()
    engine1 = ExchangeEngine(s, store=SQLiteStore(db))
    ex = _to_verified(engine1, client, provider)
    live = engine1.get(ex.exchange_id)
    engine1._capture_intent(
        live, {"action": "settle", "handle": live.escrow_handle, "status": "pending"}
    )
    assert engine1.get(ex.exchange_id).state == sm.VERIFIED

    engine2 = ExchangeEngine(s, store=SQLiteStore(db))
    recovered = engine2.recover()
    assert [e.exchange_id for e in recovered] == [ex.exchange_id]
    final = engine2.get(ex.exchange_id)
    assert final.state == sm.SETTLED
    assert final.settlement_intent["status"] == "done"


def test_c_node_r_02_noop_when_no_pending():
    engine = ExchangeEngine(MockSettlement())
    client, provider = Identity.generate(), Identity.generate()
    ex = _to_verified(engine, client, provider, idem="cnr-2")
    engine.confirm(ex.exchange_id, client)
    assert engine.recover() == []


def test_c_node_r_03_pending_intent_visible(tmp_path):
    db = str(tmp_path / "cnr3.db")
    s = MockSettlement()
    engine = ExchangeEngine(s, store=SQLiteStore(db))
    client, provider = Identity.generate(), Identity.generate()
    ex = _to_verified(engine, client, provider, idem="cnr-3")
    live = engine.get(ex.exchange_id)
    engine._capture_intent(
        live, {"action": "settle", "handle": live.escrow_handle, "status": "pending"}
    )
    pending = [
        e
        for e in engine._store.values()
        if (e.settlement_intent or {}).get("status") == "pending"
    ]
    assert len(pending) == 1
    assert pending[0].exchange_id == ex.exchange_id


def test_c_node_r_04_recover_refuses_fake_settled_on_adapter_failure(tmp_path):
    db = str(tmp_path / "cnr4.db")
    s = _FailingSettle()
    client, provider = Identity.generate(), Identity.generate()
    engine1 = ExchangeEngine(s, store=SQLiteStore(db))
    ex = _to_verified(engine1, client, provider, idem="cnr-4")
    live = engine1.get(ex.exchange_id)
    engine1._capture_intent(
        live, {"action": "settle", "handle": live.escrow_handle, "status": "pending"}
    )

    engine2 = ExchangeEngine(s, store=SQLiteStore(db))
    recovered = engine2.recover()
    assert recovered == []
    final = engine2.get(ex.exchange_id)
    assert final.state == sm.VERIFIED
    assert final.settlement_intent["status"] == "pending"
    assert "adapter_down" in (final.settlement_intent.get("last_error") or "")
