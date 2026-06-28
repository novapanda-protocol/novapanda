from troodon.exchange import ExchangeEngine
from troodon.identity import Identity
from troodon.reputation import ReputationLog
from troodon.settlement import MockSettlement
from tests.helpers import dual_contract_engine


def _run_settled(engine, client, provider, idem="t1"):
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1,
        rule_id="R1", price={"amount": 100, "currency": "USD"},
        idempotency_key=idem,
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"invoice_no": "A-001"})
    engine.verify(ex.exchange_id)
    return engine.confirm(ex.exchange_id, client)


def test_settlement_records_two_entries_and_chain_valid():
    node = Identity.generate()
    log = ReputationLog(node)
    client, provider = Identity.generate(), Identity.generate()
    engine = ExchangeEngine(MockSettlement(), reputation=log)

    _run_settled(engine, client, provider)

    assert len(log.entries()) == 2
    assert log.verify_chain() is True
    assert len(log.entries(agent_id=provider.agent_id)) == 1
    assert log.entries(agent_id=provider.agent_id)[0]["outcome"] == "settled"


def test_chain_links_across_multiple_exchanges():
    node = Identity.generate()
    log = ReputationLog(node)
    client, provider = Identity.generate(), Identity.generate()
    engine = ExchangeEngine(MockSettlement(), reputation=log)

    _run_settled(engine, client, provider, idem="a")
    _run_settled(engine, client, provider, idem="b")

    entries = log.entries()
    assert len(entries) == 4
    assert entries[0]["prev_hash"] == "GENESIS"
    for prev, cur in zip(entries, entries[1:]):
        assert cur["prev_hash"] == prev["entry_hash"]
    assert log.verify_chain() is True


def test_tampered_entry_breaks_chain():
    node = Identity.generate()
    log = ReputationLog(node)
    client, provider = Identity.generate(), Identity.generate()
    engine = ExchangeEngine(MockSettlement(), reputation=log)
    _run_settled(engine, client, provider)

    log._store.all()[0]  # 经由 store 篡改一条
    log._store._entries[0]["quantity"] = 9999
    assert log.verify_chain() is False
