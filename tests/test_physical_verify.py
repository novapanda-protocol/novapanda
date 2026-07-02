from novapanda import state_machine as sm
from novapanda.exchange import ExchangeEngine
from novapanda.identity import Identity
from novapanda.registry import load_default_registries
from novapanda.settlement import MockSettlement
from novapanda.verifier import SchemaVerifier
from tests.helpers import dual_contract_engine

_, RULES = load_default_registries()
ENERGY_RULE = RULES.get("R-energy-dc-meter-v1")
GOOD = {
    "session_id": "sess-energy-1",
    "kwh_delivered": "10.500",
    "meter_signature": "meter-sig-demo",
}
BAD = {"session_id": "sess-energy-1", "kwh_delivered": "10.500"}

ACTUATION_RULE = RULES.get("R-actuation-task-v1")
ACTUATION_GOOD = {
    "task_id": "task-robot-1",
    "completion_proof": "proof-hash-demo",
    "duration_secs": 120,
}
ACTUATION_BAD = {"task_id": "task-robot-1", "duration_secs": 120}


def test_energy_rule_passes_through_engine():
    engine = ExchangeEngine(MockSettlement(), verifier=SchemaVerifier())
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="energy.electric.dc", quantity=1,
        rule_id="R-energy-dc-meter-v1",
        price={"amount": 1050, "currency": "USD"}, idempotency_key="pev-1",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=1050, currency="USD")
    engine.deliver(ex.exchange_id, provider, GOOD)
    engine.verify(ex.exchange_id, rule=ENERGY_RULE)
    assert ex.state == sm.VERIFIED
    assert ex.verify_result["passed"] is True


def test_energy_rule_rejects_missing_meter_signature():
    engine = ExchangeEngine(MockSettlement(), verifier=SchemaVerifier())
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="energy.electric.dc", quantity=1,
        rule_id="R-energy-dc-meter-v1",
        price={"amount": 1050, "currency": "USD"}, idempotency_key="pev-2",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=1050, currency="USD")
    engine.deliver(ex.exchange_id, provider, BAD)
    engine.verify(ex.exchange_id, rule=ENERGY_RULE)
    assert ex.state == sm.REJECTED
    assert ex.verify_result["passed"] is False


def test_actuation_rule_passes_through_engine():
    engine = ExchangeEngine(MockSettlement(), verifier=SchemaVerifier())
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="actuation.robot.task", quantity=1,
        rule_id="R-actuation-task-v1",
        price={"amount": 500, "currency": "USD"}, idempotency_key="pav-act-1",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=500, currency="USD")
    engine.deliver(ex.exchange_id, provider, ACTUATION_GOOD)
    engine.verify(ex.exchange_id, rule=ACTUATION_RULE)
    assert ex.state == sm.VERIFIED


def test_actuation_rule_rejects_missing_proof():
    engine = ExchangeEngine(MockSettlement(), verifier=SchemaVerifier())
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="actuation.robot.task", quantity=1,
        rule_id="R-actuation-task-v1",
        price={"amount": 500, "currency": "USD"}, idempotency_key="pav-act-2",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=500, currency="USD")
    engine.deliver(ex.exchange_id, provider, ACTUATION_BAD)
    engine.verify(ex.exchange_id, rule=ACTUATION_RULE)
    assert ex.state == sm.REJECTED
