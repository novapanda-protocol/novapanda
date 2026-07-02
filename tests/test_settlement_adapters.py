from novapanda import vdc as V
from novapanda.exchange import ExchangeEngine
from novapanda.identity import Identity
from novapanda.settlement import AP2Settlement, FakeGateway, X402Settlement
from tests.helpers import dual_contract_engine


def _run(settlement):
    engine = ExchangeEngine(settlement)
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="rail-1",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"invoice_no": "A-1"})
    engine.verify(ex.exchange_id)
    return engine.confirm(ex.exchange_id, client)


def test_x402_adapter_end_to_end():
    gw = FakeGateway()
    settled = _run(X402Settlement(gw))
    assert settled.state == "SETTLED"
    assert settled.settlement_receipt["rail"] == "x402"
    assert settled.settlement_receipt["status"] == "settled"
    assert V.is_valid_settled(settled.vdc) is True
    assert gw.state(settled.escrow_handle) == "captured"


def test_ap2_adapter_refund_path():
    gw = FakeGateway()
    settlement = AP2Settlement(gw)
    engine = ExchangeEngine(settlement)
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="ap2-refund",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.cancel(ex.exchange_id)
    assert ex.settlement_receipt["rail"] == "ap2"
    assert ex.settlement_receipt["status"] == "refunded"
    assert gw.state(ex.escrow_handle) == "voided"
