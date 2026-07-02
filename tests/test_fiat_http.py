from fastapi.testclient import TestClient

from novapanda import vdc as V
from novapanda.exchange import ExchangeEngine
from novapanda.identity import Identity
from novapanda.settlement import FiatSettlement
from novapanda.fiat_fake import create_fiat_fake_app
from novapanda.fiat_gateway import HttpFiatGateway
from tests.helpers import dual_contract_engine


def test_fiat_http_gateway_full_exchange():
    fake = create_fiat_fake_app()
    gw_tc = TestClient(fake)
    gateway = HttpFiatGateway("http://testserver", http=gw_tc)
    settlement = FiatSettlement(gateway)
    engine = ExchangeEngine(settlement)
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="fiat-http",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"invoice_no": "A-1"})
    engine.verify(ex.exchange_id)
    settled = engine.confirm(ex.exchange_id, client)
    assert settled.state == "SETTLED"
    assert settled.settlement_receipt["rail"] == "fiat"
    assert V.is_valid_settled(settled.vdc) is True
