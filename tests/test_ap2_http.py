from fastapi.testclient import TestClient

from troodon import vdc as V
from troodon.exchange import ExchangeEngine
from troodon.identity import Identity
from troodon.settlement import AP2Settlement
from troodon.ap2_fake import create_ap2_fake_app
from troodon.ap2_gateway import HttpAP2Gateway
from tests.helpers import dual_contract_engine


def test_ap2_http_gateway_full_exchange():
    fake = create_ap2_fake_app()
    gw_tc = TestClient(fake)
    gateway = HttpAP2Gateway("http://testserver", http=gw_tc)
    settlement = AP2Settlement(gateway)
    engine = ExchangeEngine(settlement)
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="ap2-http",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"invoice_no": "A-1"})
    engine.verify(ex.exchange_id)
    settled = engine.confirm(ex.exchange_id, client)
    assert settled.state == "SETTLED"
    assert settled.settlement_receipt["rail"] == "ap2"
    assert V.is_valid_settled(settled.vdc) is True
