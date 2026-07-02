"""LLM 多裁判共识：组合多个 judge_fn，产出单一 passed/audit。"""

from __future__ import annotations

from typing import Callable, Optional

JudgeFn = Callable[[object, dict], dict]


def consensus_judge_fn(
    judges: list[JudgeFn],
    *,
    strategy: str = "unanimous",
) -> JudgeFn:
    """strategy: unanimous | majority — 全部/多数 passed 则通过。"""
    if not judges:
        raise ValueError("consensus 至少需要一个 judge")

    def _fn(deliverable: object, rule: dict) -> dict:
        results = [j(deliverable, rule) for j in judges]
        passes = [bool(r.get("passed")) for r in results]
        if strategy == "majority":
            passed = sum(passes) > len(passes) / 2
        else:
            passed = all(passes)
        reasons = [str(r.get("reason", "")) for r in results]
        checks = []
        for i, r in enumerate(results):
            checks.append({"judge": i, "passed": r.get("passed"), "reason": r.get("reason")})
            checks.extend(r.get("checks") or [])
        audit_extras = {
            "consensus_strategy": strategy,
            "consensus_judges": len(judges),
            "consensus_votes": passes,
        }
        first_audit = next((r.get("_audit_extras") for r in results if r.get("_audit_extras")), None)
        if isinstance(first_audit, dict):
            audit_extras["primary_audit"] = first_audit
        return {
            "passed": passed,
            "reason": "consensus ok" if passed else f"consensus failed: {reasons}",
            "checks": checks,
            "_audit_extras": audit_extras,
            "gateway": "consensus",
        }

    return _fn


def parse_consensus_judges(spec: str, resolver) -> tuple[list[JudgeFn], str]:
    """spec 形如 'consensus:unanimous:regex,field_match' 或 'majority:regex'。"""
    raw = spec.strip()
    if raw.lower().startswith("consensus:"):
        raw = raw.split(":", 1)[1]
    strategy = "unanimous"
    names = raw
    if ":" in raw:
        strategy, names = raw.split(":", 1)
    strategy = strategy.strip().lower()
    if strategy not in ("unanimous", "majority"):
        raise ValueError(f"未知 consensus strategy: {strategy}")
    judges: list[JudgeFn] = []
    for name in names.split(","):
        name = name.strip().lower()
        if not name:
            continue
        fn = resolver(name)
        if fn is None:
            raise ValueError(f"未知 judge: {name}")
        judges.append(fn)
    if not judges:
        raise ValueError("consensus 未解析到任何 judge")
    return judges, strategy
