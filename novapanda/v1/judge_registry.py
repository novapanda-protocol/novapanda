"""内置 LLM judge_fn 注册表 — 可复验、无外部 API 依赖。

通过 NOVAPANDA_LLM_JUDGE=regex|field_match 选用；也可在代码中直接注入 judge_fn。
"""

from __future__ import annotations

import re
from typing import Any, Callable, Optional

JudgeFn = Callable[[Any, dict], dict]

_REGISTRY: dict[str, JudgeFn] = {}


def register_judge(name: str, fn: JudgeFn) -> None:
    _REGISTRY[name.lower()] = fn


def resolve_judge_fn(name: Optional[str]) -> Optional[JudgeFn]:
    if not name:
        return None
    key = name.strip().lower()
    if key not in _REGISTRY:
        raise ValueError(f"未知 LLM judge: {name!r}（可用: {', '.join(sorted(_REGISTRY))}）")
    return _REGISTRY[key]


def _text_at(deliverable: Any, field: Optional[str]) -> str:
    if field and isinstance(deliverable, dict):
        val = deliverable.get(field)
        return "" if val is None else str(val)
    return str(deliverable)


def regex_judge(deliverable: Any, rule: dict) -> dict:
    """按 llm_rubric.pattern 对 field（或整份 deliverable 字符串）做正则匹配。"""
    rubric = rule.get("llm_rubric") or {}
    pattern = rubric.get("pattern")
    field = rubric.get("field")
    text = _text_at(deliverable, field)
    if not pattern:
        return {"passed": False, "reason": "rubric 缺少 pattern", "checks": []}
    matched = re.search(pattern, text, re.IGNORECASE | re.MULTILINE) is not None
    return {
        "passed": matched,
        "reason": "regex rubric satisfied" if matched else f"pattern 未匹配: {pattern!r}",
        "checks": [{"pattern": pattern, "field": field or "(whole)", "matched": matched}],
    }


def field_match_judge(deliverable: Any, rule: dict) -> dict:
    """按 llm_rubric.field_equals: {field: expected, ...} 精确匹配（字符串化后比对）。"""
    rubric = rule.get("llm_rubric") or {}
    expected_map = rubric.get("field_equals") or {}
    if not isinstance(expected_map, dict) or not expected_map:
        return {"passed": False, "reason": "rubric 缺少 field_equals", "checks": []}
    if not isinstance(deliverable, dict):
        return {"passed": False, "reason": "deliverable 须为 object", "checks": []}
    checks: list[dict] = []
    for field, expected in expected_map.items():
        actual = deliverable.get(field)
        ok = str(actual) == str(expected)
        checks.append({"field": field, "expected": expected, "actual": actual, "ok": ok})
    passed = all(c["ok"] for c in checks)
    return {
        "passed": passed,
        "reason": "field_equals satisfied" if passed else "field_equals mismatch",
        "checks": checks,
    }


register_judge("regex", regex_judge)
register_judge("field_match", field_match_judge)
