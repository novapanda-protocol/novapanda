from fastapi.testclient import TestClient

from novapanda import vdc as V
from novapanda.exchange import ExchangeEngine
from novapanda.identity import Identity
from novapanda.settlement import X402Settlement
from novapanda.x402_fake import create_x402_fake_app
from novapanda.x402_gateway import HttpX402Gateway
from tests.helpers import dual_contract_engine


def test_x402_http_gateway_full_exchange():
    fake = create_x402_fake_app()
    gw_tc = TestClient(fake)
    gateway = HttpX402Gateway("http://testserver", http=gw_tc)
    settlement = X402Settlement(gateway)
    engine = ExchangeEngine(settlement)
    client, provider = Identity.generate(), Identity.generate()

    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="x402-http",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"invoice_no": "A-1"})
    engine.verify(ex.exchange_id)
    settled = engine.confirm(ex.exchange_id, client)

    assert settled.state == "SETTLED"
    assert settled.settlement_receipt["rail"] == "x402"
    assert V.is_valid_settled(settled.vdc) is True


def test_x402_http_refund_on_cancel():
    fake = create_x402_fake_app()
    gw_tc = TestClient(fake)
    gateway = HttpX402Gateway("http://testserver", http=gw_tc)
    settlement = X402Settlement(gateway)
    engine = ExchangeEngine(settlement)
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 50, "currency": "USD"}, idempotency_key="x402-void",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=50, currency="USD")
    engine.cancel(ex.exchange_id)
    assert ex.settlement_receipt["status"] == "refunded"
