from novapanda.v1.llm_verifier import LLMJudgeVerifier


def test_llm_stub_passes_with_keywords():
    v = LLMJudgeVerifier()
    rule = {
        "schema": {"type": "object", "properties": {"note": {"type": "string"}}},
        "llm_rubric": {"required_keywords": ["quality", "complete"]},
    }
    deliverable = {"note": "quality work complete"}
    result = v.verify(deliverable, rule)
    assert result["passed"] is True
    assert "llm_audit" in result
    assert result["verifier_id"] == "verifier:llm-judge/v1-stub"


def test_llm_stub_fails_missing_keyword():
    v = LLMJudgeVerifier()
    rule = {"llm_rubric": {"required_keywords": ["missing-word"]}}
    result = v.verify({"x": 1}, rule)
    assert result["passed"] is False
