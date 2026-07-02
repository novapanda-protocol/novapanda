
def test_llm_injected_judge_fn():
    from novapanda.v1.llm_verifier import LLMJudgeVerifier

    def always_pass(deliverable, rule):
        return {"passed": True, "reason": "injected ok", "checks": []}

    v = LLMJudgeVerifier(judge_fn=always_pass, model_id="custom-model/v1")
    out = v.verify({"x": 1}, {"llm_rubric": {}})
    assert out["passed"] is True
    assert out["llm_audit"]["source"] == "injected"
