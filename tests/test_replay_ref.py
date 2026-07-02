from novapanda.exchange import ExchangeEngine
from novapanda.identity import Identity
from novapanda.registry import load_default_registries
from novapanda.settlement import MockSettlement
from novapanda.verifier import SchemaVerifier
from tests.helpers import dual_contract_engine

GOOD = {"invoice_no": "A-001", "total": "100.00", "currency": "USD"}


def test_verify_result_has_replay_inputs_ref():
    _, rules = load_default_registries()
    rule = rules.get("R-extract-invoice-v1")
    engine = ExchangeEngine(MockSettlement(), verifier=SchemaVerifier())
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1,
        rule_id="R-extract-invoice-v1",
        price={"amount": 100, "currency": "USD"}, idempotency_key="replay-ref",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=100, currency="USD")
    engine.deliver(ex.exchange_id, provider, GOOD)
    ex = engine.verify(ex.exchange_id, rule=rule)

    ref = ex.verify_result["replay_inputs_ref"]
    assert ref["kind"] == "inline"
    assert ref["exchange_id"] == ex.exchange_id
    assert ref["rule_id"] == "R-extract-invoice-v1"
    assert ref["deliverable_ref"] == f"inline:{ex.exchange_id}"
    assert "schema_inline" in ref


def test_deliverable_ref_set_on_delivery():
    engine = ExchangeEngine(MockSettlement())
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="data.extraction.structured", quantity=1, rule_id="R1",
        price={"amount": 1, "currency": "USD"}, idempotency_key="dref",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=1, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"invoice_no": "x"})
    assert ex.deliverable_ref == f"inline:{ex.exchange_id}"
