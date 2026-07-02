from fastapi.testclient import TestClient

from novapanda import vdc as V
from novapanda.exchange import ExchangeEngine
from novapanda.identity import Identity
from novapanda.llm_fake import create_llm_fake_app
from novapanda.registry import load_default_registries
from novapanda.settlement import MockSettlement
from novapanda.v1.llm_openai_compat import OpenAICompatLLMGateway, build_judge_prompt, parse_judge_content
from novapanda.verifier import make_verifier
from tests.helpers import dual_contract_engine

_, RULES = load_default_registries()
LLM_RULE = RULES.get("R-llm-summary-v1")


def test_make_verifier_openai_requires_gateway_url():
    import pytest

    with pytest.raises(ValueError, match="NOVAPANDA_LLM_GATEWAY_URL"):
        make_verifier("llm", llm_judge="openai")


def test_openai_compat_fake_chat_completions():
    fake = create_llm_fake_app(mode="regex")
    tc = TestClient(fake)
    gw = OpenAICompatLLMGateway("http://testserver", http=tc)
    result = gw.judge({"summary": "PASS: openai path"}, LLM_RULE)
    assert result["passed"] is True
    assert result.get("gateway") == "openai-compat"


def test_openai_judge_prompt_and_parse():
    prompt = build_judge_prompt({"summary": "x"}, LLM_RULE)
    assert "rule_id=" in prompt
    assert "deliverable=" in prompt
    parsed = parse_judge_content('{"passed": true, "reason": "ok", "checks": []}')
    assert parsed["passed"] is True


def test_openai_llm_verifier_full_exchange():
    fake = create_llm_fake_app(mode="regex")
    gw_tc = TestClient(fake)
    verifier = make_verifier(
        "llm",
        llm_judge="openai",
        llm_gateway_url="http://testserver",
        llm_gateway_http=gw_tc,
    )
    engine = ExchangeEngine(MockSettlement(), verifier=verifier)
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id,
        provider=provider.agent_id,
        resource_type="service.task.generic",
        quantity=1,
        rule_id="R-llm-summary-v1",
        price={"amount": 50, "currency": "USD"},
        idempotency_key="llm-openai-1",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=50, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"summary": "PASS: via openai compat"})
    engine.verify(ex.exchange_id, rule=LLM_RULE)
    assert ex.state == "VERIFIED"
    settled = engine.confirm(ex.exchange_id, client)
    assert settled.state == "SETTLED"
    assert V.is_valid_settled(settled.vdc)
