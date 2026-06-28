"""LLM 验收审计字段：prompt / 模型 / 网关快照（写入 verify_result.llm_audit）。"""

from __future__ import annotations

from typing import Any, Optional


def merge_judge_audit(base: dict, judge_out: dict) -> dict:
    """将 judge 返回的审计字段合并进 llm_audit。"""
    audit = dict(base)
    extras = judge_out.pop("_audit_extras", None) or {}
    if isinstance(extras, dict):
        audit.update(extras)
    for key in ("prompt_snapshot", "model_version", "gateway_url", "gateway_request"):
        if key in judge_out:
            audit[key] = judge_out.pop(key)
    if judge_out.get("gateway"):
        audit["gateway"] = judge_out["gateway"]
    return audit
