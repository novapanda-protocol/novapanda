from troodon.exchange import ExchangeEngine
from troodon.identity import Identity
from troodon.reputation import ReputationLog, SQLiteReputationStore
from troodon.settlement import MockSettlement
from tests.helpers import dual_contract_engine


def _settle(engine, client, provider, idem):
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 100, "currency": "USD"}, idempotency_key=idem,
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"invoice_no": "A-1"})
    engine.verify(ex.exchange_id)
    engine.confirm(ex.exchange_id, client)


def test_reputation_persists_and_chain_verifies(tmp_path):
    db = str(tmp_path / "rep.db")
    node = Identity.generate()
    client, provider = Identity.generate(), Identity.generate()

    log1 = ReputationLog(node, store=SQLiteReputationStore(db))
    engine = ExchangeEngine(MockSettlement(), reputation=log1)
    _settle(engine, client, provider, "rp-1")
    _settle(engine, client, provider, "rp-2")
    assert len(log1.entries()) == 4
    assert log1.verify_chain() is True

    # 新进程：重开同一磁盘库，链延续且可验
    log2 = ReputationLog(node, store=SQLiteReputationStore(db))
    assert len(log2.entries()) == 4
    assert log2.verify_chain() is True
    assert len(log2.entries(agent_id=provider.agent_id)) == 2

    # 续写一条，prev_hash 接续磁盘上最后一条
    entries_before = log2.entries()
    new = log2.append(agent_id=provider.agent_id, counterparty=client.agent_id,
                      exchange_id="ex-x", vdc_id=None, role="provider",
                      outcome="settled", resource_type="r", quantity=1)
    assert new["prev_hash"] == entries_before[-1]["entry_hash"]
    assert log2.verify_chain() is True
