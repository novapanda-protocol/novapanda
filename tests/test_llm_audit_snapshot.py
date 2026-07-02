from fastapi.testclient import TestClient

from novapanda.exchange import ExchangeEngine
from novapanda.identity import Identity
from novapanda.llm_fake import create_llm_fake_app
from novapanda.registry import load_default_registries
from novapanda.settlement import MockSettlement
from novapanda.v1.llm_openai_compat import OpenAICompatLLMGateway
from novapanda.verifier import make_verifier
from tests.helpers import dual_contract_engine

_, RULES = load_default_registries()
LLM_RULE = RULES.get("R-llm-summary-v1")


def test_openai_audit_includes_prompt_snapshot():
    fake = create_llm_fake_app(mode="regex")
    tc = TestClient(fake)
    gw = OpenAICompatLLMGateway("http://testserver", model="test-model", http=tc)
    verifier = make_verifier(
        "llm",
        llm_judge="openai",
        llm_gateway_url="http://testserver",
        llm_gateway_http=tc,
        llm_model="test-model",
    )
    engine = ExchangeEngine(MockSettlement(), verifier=verifier)
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="service.task.generic", quantity=1,
        rule_id="R-llm-summary-v1",
        price={"amount": 50, "currency": "USD"}, idempotency_key="audit-1",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=50, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"summary": "PASS: audit"})
    engine.verify(ex.exchange_id, rule=LLM_RULE)
    audit = ex.verify_result["llm_audit"]
    assert audit["prompt_snapshot"]
    assert audit["model_version"] == "test-model"
    assert audit["gateway_url"] == "http://testserver"
    assert audit["schema_preflight"] == "passed"


def test_http_gateway_audit_snapshot():
    fake = create_llm_fake_app(mode="regex")
    tc = TestClient(fake)
    verifier = make_verifier(
        "llm", llm_judge="http", llm_gateway_url="http://testserver", llm_gateway_http=tc,
    )
    engine = ExchangeEngine(MockSettlement(), verifier=verifier)
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="service.task.generic", quantity=1,
        rule_id="R-llm-summary-v1",
        price={"amount": 50, "currency": "USD"}, idempotency_key="audit-http",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=50, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"summary": "PASS: http audit"})
    engine.verify(ex.exchange_id, rule=LLM_RULE)
    audit = ex.verify_result["llm_audit"]
    assert "deliverable" in audit["prompt_snapshot"]
    assert audit["gateway_url"] == "http://testserver"
