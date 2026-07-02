from fastapi.testclient import TestClient

from novapanda import vdc as V
from novapanda.exchange import ExchangeEngine
from novapanda.identity import Identity
from novapanda.llm_fake import create_llm_fake_app
from novapanda.registry import load_default_registries
from novapanda.settlement import MockSettlement
from novapanda.v1.llm_gateway import HttpLLMGateway
from novapanda.verifier import make_verifier
from tests.helpers import dual_contract_engine

_, RULES = load_default_registries()
LLM_RULE = RULES.get("R-llm-summary-v1")
STATUS_RULE = RULES.get("R-task-status-v1")


def test_make_verifier_http_requires_gateway_url():
    import pytest
    from novapanda.verifier import make_verifier

    with pytest.raises(ValueError, match="NOVAPANDA_LLM_GATEWAY_URL"):
        make_verifier("llm", llm_judge="http")
    fake = create_llm_fake_app(mode="regex")
    tc = TestClient(fake)
    gw = HttpLLMGateway("http://testserver", http=tc)
    result = gw.judge({"summary": "PASS: ok"}, LLM_RULE)
    assert result["passed"] is True
    assert result.get("gateway") == "fake"


def test_http_llm_verifier_schema_then_gateway():
    fake = create_llm_fake_app(mode="regex")
    gw_tc = TestClient(fake)
    verifier = make_verifier(
        "llm", llm_judge="http", llm_gateway_url="http://testserver", llm_gateway_http=gw_tc,
    )
    engine = ExchangeEngine(MockSettlement(), verifier=verifier)
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="service.task.generic", quantity=1,
        rule_id="R-llm-summary-v1",
        price={"amount": 50, "currency": "USD"}, idempotency_key="llm-http-1",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=50, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"summary": "PASS: via http gateway"})
    engine.verify(ex.exchange_id, rule=LLM_RULE)
    assert ex.state == "VERIFIED"
    assert ex.verify_result["llm_audit"]["schema_preflight"] == "passed"


def test_http_llm_gateway_field_match_mode():
    fake = create_llm_fake_app(mode="field_match")
    tc = TestClient(fake)
    gw = HttpLLMGateway("http://testserver", http=tc)
    good = {"status": "done", "score": "A"}
    assert gw.judge(good, STATUS_RULE)["passed"] is True
    assert gw.judge({"status": "done", "score": "B"}, STATUS_RULE)["passed"] is False


def test_http_llm_full_exchange_settled():
    fake = create_llm_fake_app(mode="regex")
    gw_tc = TestClient(fake)
    verifier = make_verifier(
        "llm", llm_judge="http", llm_gateway_url="http://testserver", llm_gateway_http=gw_tc,
    )
    engine = ExchangeEngine(MockSettlement(), verifier=verifier)
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="service.task.generic", quantity=1,
        rule_id="R-llm-summary-v1",
        price={"amount": 50, "currency": "USD"}, idempotency_key="llm-http-settle",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=50, currency="USD")
    deliverable = {"summary": "PASS: settled path"}
    engine.deliver(ex.exchange_id, provider, deliverable)
    engine.verify(ex.exchange_id, rule=LLM_RULE)
    settled = engine.confirm(ex.exchange_id, client)
    assert settled.state == "SETTLED"
    assert V.is_valid_settled(settled.vdc)
