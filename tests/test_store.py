from fastapi.testclient import TestClient

import pytest

from novapanda import state_machine as sm
from novapanda import vdc as V
from novapanda.exchange import ExchangeEngine
from novapanda.identity import Identity
from novapanda.node import create_app
from novapanda.sdk import NovaPandaClient
from novapanda.settlement import MockSettlement
from novapanda.store import ConcurrencyError, SQLiteStore
from tests.helpers import dual_contract_engine, dual_contract_sdk


def _propose(engine, client, provider, idem="t1"):
    return engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 100, "currency": "USD"}, idempotency_key=idem,
    )


def test_sqlite_full_lifecycle():
    store = SQLiteStore(":memory:")
    settlement = MockSettlement()
    engine = ExchangeEngine(settlement, store=store)
    client, provider = Identity.generate(), Identity.generate()

    ex = _propose(engine, client, provider)
    eid = ex.exchange_id
    dual_contract_engine(engine, eid, client, provider)
    engine.escrow(eid, amount=100, currency="USD")
    engine.deliver(eid, provider, {"invoice_no": "A-1"})
    engine.verify(eid)
    settled = engine.confirm(eid, client)

    assert settled.state == sm.SETTLED
    assert V.is_valid_settled(settled.vdc) is True


def test_sqlite_durable_across_engine_instances(tmp_path):
    db = str(tmp_path / "novapanda.db")
    settlement = MockSettlement()
    client, provider = Identity.generate(), Identity.generate()

    # 实例 1：写到磁盘
    engine1 = ExchangeEngine(settlement, store=SQLiteStore(db))
    ex = _propose(engine1, client, provider, idem="dur-1")
    eid = ex.exchange_id
    dual_contract_engine(engine1, eid, client, provider)
    engine1.escrow(eid, amount=100, currency="USD")

    # 实例 2：全新引擎 + 全新连接，从磁盘读回，状态延续
    engine2 = ExchangeEngine(settlement, store=SQLiteStore(db))
    reread = engine2.get(eid)
    assert reread.state == sm.ESCROWED
    assert reread.escrow_handle is not None

    # 幂等键也持久化：同 client+key 重复 propose 返回同一交换
    again = _propose(engine2, client, provider, idem="dur-1")
    assert again.exchange_id == eid

    # 继续推进直到结算
    engine2.deliver(eid, provider, {"invoice_no": "A-1"})
    engine2.verify(eid)
    settled = engine2.confirm(eid, client)
    assert settled.state == sm.SETTLED


def test_optimistic_lock_conflict(tmp_path):
    db = str(tmp_path / "lock.db")
    store = SQLiteStore(db)
    settlement = MockSettlement()
    engine = ExchangeEngine(settlement, store=store)
    client, provider = Identity.generate(), Identity.generate()
    ex = _propose(engine, client, provider, idem="lock-1")

    # 两个并发读取，拿到同一 version
    a = store.get(ex.exchange_id)
    b = store.get(ex.exchange_id)
    assert a.version == b.version == 0

    # a 先提交（0 -> 1）成功
    a.state = sm.CONTRACTED
    a.version += 1
    store.save(a)

    # b 基于陈旧 version 提交 -> 冲突
    b.state = sm.CANCELLED
    b.version += 1
    with pytest.raises(ConcurrencyError):
        store.save(b)


def test_node_with_sqlite_store():
    app = create_app(seed=True, store=SQLiteStore(":memory:"))
    tc = TestClient(app)
    client = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    provider = NovaPandaClient("http://testserver", Identity.generate(), http=tc)
    good = {"invoice_no": "A-001", "total": "100.00", "currency": "USD"}

    ex = client.propose(provider=provider.agent_id, resource_type="data.extraction.structured",
                        quantity=1, rule_id="R-extract-invoice-v1",
                        price={"amount": 100, "currency": "USD"}, idempotency_key="sql-api")
    eid = ex["exchange_id"]
    dual_contract_sdk(client, provider, eid)
    client.escrow(eid, amount=100, currency="USD")
    provider.deliver(eid, good)
    client.verify(eid)
    settled = client.confirm(eid)
    assert settled["state"] == "SETTLED"
    assert V.is_valid_settled(settled["vdc"]) is True
