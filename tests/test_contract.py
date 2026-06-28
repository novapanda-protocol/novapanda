import pytest

from troodon import state_machine as sm
from troodon.exchange import ExchangeEngine, ExchangeError
from troodon.identity import Identity
from troodon.settlement import MockSettlement
from troodon.terms import sign_contract_ack, terms_hash_from_exchange, verify_contract_ack
from tests.helpers import ack_contract, dual_contract_engine


def test_terms_hash_stable():
    client, provider = Identity.generate(), Identity.generate()
    engine = ExchangeEngine(MockSettlement())
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="th-1",
    )
    assert ex.terms_hash == terms_hash_from_exchange(ex)


def test_single_ack_stays_proposed():
    client, provider = Identity.generate(), Identity.generate()
    engine = ExchangeEngine(MockSettlement())
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="ack-1",
    )
    ack_contract(engine, ex.exchange_id, client)
    live = engine.get(ex.exchange_id)
    assert live.state == sm.PROPOSED
    assert set(live.contract_acks.keys()) == {client.agent_id}


def test_dual_ack_transitions_to_contracted():
    client, provider = Identity.generate(), Identity.generate()
    engine = ExchangeEngine(MockSettlement())
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="ack-2",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    live = engine.get(ex.exchange_id)
    assert live.state == sm.CONTRACTED
    assert client.agent_id in live.contract_acks
    assert provider.agent_id in live.contract_acks


def test_bad_contract_signature_rejected():
    client, provider = Identity.generate(), Identity.generate()
    engine = ExchangeEngine(MockSettlement())
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="bad-sig",
    )
    with pytest.raises(ExchangeError, match="签名无效"):
        engine.contract(ex.exchange_id, party=client.agent_id, signature="AAAA")


def test_contract_ack_bytes_match_verify():
    client, provider = Identity.generate(), Identity.generate()
    engine = ExchangeEngine(MockSettlement())
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="v-1",
    )
    sig = sign_contract_ack(client, ex)
    assert verify_contract_ack(client.agent_id, sig, terms_hash=ex.terms_hash,
                               exchange_id=ex.exchange_id)
