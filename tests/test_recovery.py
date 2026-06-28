from troodon import state_machine as sm
from troodon.exchange import ExchangeEngine
from troodon.identity import Identity
from troodon.settlement import MockSettlement
from troodon.store import SQLiteStore
from tests.helpers import dual_contract_engine


def _to_verified(engine, client, provider, idem="r1"):
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


def test_settlement_is_idempotent():
    s = MockSettlement()
    h = s.escrow("ex", 100, "USD")
    r1 = s.settle(h)
    r2 = s.settle(h)  # 重放安全
    assert r1 == r2 == {"handle": h, "status": "settled", "amount": 100, "currency": "USD"}


def test_happy_confirm_records_intent_done():
    s = MockSettlement()
    engine = ExchangeEngine(s)
    client, provider = Identity.generate(), Identity.generate()
    ex = _to_verified(engine, client, provider)
    settled = engine.confirm(ex.exchange_id, client)
    assert settled.state == sm.SETTLED
    assert settled.settlement_intent == {
        "action": "settle", "handle": ex.escrow_handle, "status": "done"
    }
    assert s.status(ex.escrow_handle) == "settled"


def test_recover_completes_crashed_confirm(tmp_path):
    """模拟：capture 了 pending settle 后进程崩溃（未结算、未落终态）。recover() 应幂等补齐。"""
    db = str(tmp_path / "rec.db")
    s = MockSettlement()
    client, provider = Identity.generate(), Identity.generate()

    engine1 = ExchangeEngine(s, store=SQLiteStore(db))
    ex = _to_verified(engine1, client, provider)
    eid = ex.exchange_id

    # 注入崩溃窗口：只落盘 pending 意图，既未真正结算也未推进到 SETTLED
    live = engine1.get(eid)
    engine1._capture_intent(live, {"action": "settle", "handle": live.escrow_handle, "status": "pending"})
    assert engine1.get(eid).state == sm.VERIFIED       # 尚未结算
    assert s.status(live.escrow_handle) == "held"

    # 新引擎（共享同一结算实例 + 同一磁盘库）恢复
    engine2 = ExchangeEngine(s, store=SQLiteStore(db))
    recovered = engine2.recover()
    assert [e.exchange_id for e in recovered] == [eid]
    final = engine2.get(eid)
    assert final.state == sm.SETTLED
    assert final.settlement_intent["status"] == "done"
    assert s.status(live.escrow_handle) == "settled"


def test_recover_is_noop_when_no_pending():
    s = MockSettlement()
    engine = ExchangeEngine(s)
    client, provider = Identity.generate(), Identity.generate()
    ex = _to_verified(engine, client, provider)
    engine.confirm(ex.exchange_id, client)
    assert engine.recover() == []
