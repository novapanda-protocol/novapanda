from troodon.v1.judge_registry import field_match_judge, regex_judge
from troodon.v1.llm_consensus import consensus_judge_fn, parse_consensus_judges
from troodon.v1.judge_registry import resolve_judge_fn


def test_consensus_unanimous_all_pass():
    fn = consensus_judge_fn([regex_judge, field_match_judge], strategy="unanimous")
    rule = {
        "llm_rubric": {
            "pattern": r"ok",
            "field_equals": {"status": "done"},
        }
    }
    out = fn({"status": "done", "note": "ok"}, rule)
    assert out["passed"] is True
    assert out["gateway"] == "consensus"


def test_consensus_majority_two_of_three():
    always_pass = lambda d, r: {"passed": True, "reason": "ok", "checks": []}
    fn = consensus_judge_fn([always_pass, always_pass, regex_judge], strategy="majority")
    rule = {"llm_rubric": {"pattern": r"missing"}}
    out = fn({"note": "x"}, rule)
    assert out["passed"] is True


def test_consensus_unanimous_one_fails():
    fn = consensus_judge_fn([regex_judge, field_match_judge], strategy="unanimous")
    rule = {
        "llm_rubric": {
            "pattern": r"missing",
            "field_equals": {"status": "done"},
        }
    }
    out = fn({"status": "done"}, rule)
    assert out["passed"] is False


def test_parse_consensus_from_env_shape():
    judges, strategy = parse_consensus_judges(
        "consensus:unanimous:regex,field_match",
        resolve_judge_fn,
    )
    assert strategy == "unanimous"
    assert len(judges) == 2


def test_verifier_factory_consensus():
    from troodon.verifier import make_verifier

    v = make_verifier("llm", llm_judge="consensus:unanimous:regex,field_match")
    out = v.verify(
        {"status": "done", "note": "ok"},
        {
            "llm_rubric": {
                "pattern": "ok",
                "field_equals": {"status": "done"},
            }
        },
    )
    assert out["passed"] is True
