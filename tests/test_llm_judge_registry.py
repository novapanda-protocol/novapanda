import pytest

from novapanda.v1.judge_registry import field_match_judge, regex_judge, resolve_judge_fn
from novapanda.verifier import make_verifier
from novapanda.exchange import ExchangeEngine
from novapanda.identity import Identity
from novapanda.registry import load_default_registries
from novapanda.settlement import MockSettlement
from tests.helpers import dual_contract_engine

_, RULES = load_default_registries()
LLM_RULE = RULES.get("R-llm-summary-v1")


def test_resolve_unknown_judge_raises():
    with pytest.raises(ValueError, match="未知 LLM judge"):
        resolve_judge_fn("not-a-judge")


def test_regex_judge_pass_and_fail():
    rule = {"llm_rubric": {"field": "summary", "pattern": "^PASS:"}}
    assert regex_judge({"summary": "PASS: ok"}, rule)["passed"] is True
    assert regex_judge({"summary": "FAIL: no"}, rule)["passed"] is False


def test_field_match_judge():
    rule = {"llm_rubric": {"field_equals": {"status": "done", "score": "A"}}}
    assert field_match_judge({"status": "done", "score": "A"}, rule)["passed"] is True
    assert field_match_judge({"status": "done", "score": "B"}, rule)["passed"] is False


def test_llm_regex_through_engine():
    engine = ExchangeEngine(
        MockSettlement(), verifier=make_verifier("llm", llm_judge="regex"),
    )
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="service.task.generic", quantity=1,
        rule_id="R-llm-summary-v1",
        price={"amount": 50, "currency": "USD"}, idempotency_key="ljr-1",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=50, currency="USD")
    engine.deliver(ex.exchange_id, provider, {"summary": "PASS: demo"})
    engine.verify(ex.exchange_id, rule=LLM_RULE)
    assert ex.state == "VERIFIED"
    assert ex.verify_result["llm_audit"]["schema_preflight"] == "passed"


def test_llm_schema_preflight_blocks_before_regex():
    engine = ExchangeEngine(
        MockSettlement(), verifier=make_verifier("llm", llm_judge="regex"),
    )
    client, provider = Identity.generate(), Identity.generate()
    ex = engine.propose(
        client=client.agent_id, provider=provider.agent_id,
        resource_type="service.task.generic", quantity=1,
        rule_id="R-llm-summary-v1",
        price={"amount": 50, "currency": "USD"}, idempotency_key="ljr-schema",
    )
    dual_contract_engine(engine, ex.exchange_id, client, provider)
    engine.escrow(ex.exchange_id, amount=50, currency="USD")
    # summary 通过 regex 但缺 schema 字段
    engine.deliver(ex.exchange_id, provider, {"note": "PASS: hidden"})
    engine.verify(ex.exchange_id, rule=LLM_RULE)
    assert ex.state == "REJECTED"
    assert ex.verify_result["llm_audit"]["stage"] == "schema_preflight"
