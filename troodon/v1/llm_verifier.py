"""LLM 裁判验收 v1 骨架（确定性 stub，记录 prompt 快照供审计）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from ..verifier import SchemaVerifier
from .llm_audit import merge_judge_audit


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _needs_schema_preflight(rule: Optional[dict]) -> bool:
    if not rule:
        return False
    if "schema" in rule:
        return True
    from ..v3.physical import is_reserved_physical_type

    rt = rule.get("resource_type")
    return bool(rt and is_reserved_physical_type(rt))


class LLMJudgeVerifier:
    """v1 骨架：先 Schema/物理预检，再 judge_fn 或 keyword stub。"""

    verifier_id = "verifier:llm-judge/v1-stub"
    model_id = "stub-deterministic/v1"

    def __init__(
        self,
        *,
        schema_fallback: bool = True,
        judge_fn=None,
        model_id: Optional[str] = None,
    ) -> None:
        self._schema = SchemaVerifier()
        self._schema_fallback = schema_fallback
        self._judge_fn = judge_fn
        if model_id:
            self.model_id = model_id

    def _audit_base(self, rule: Optional[dict]) -> dict:
        rubric = None
        if rule:
            rubric = rule.get("llm_rubric") or (rule.get("check") or {}).get("rubric")
        return {
            "model_id": self.model_id,
            "rubric": rubric or "(none)",
            "policy": "schema preflight then judge",
        }

    def _run_preflight(self, deliverable: Any, rule: Optional[dict]) -> Optional[dict]:
        if not self._schema_fallback or not _needs_schema_preflight(rule):
            return None
        return self._schema.verify(deliverable, rule)

    @staticmethod
    def _merge_schema_checks(preflight: Optional[dict], checks: list) -> list:
        if not preflight or not preflight.get("checks"):
            return checks
        schema_checks = [
            {"stage": "schema", **c} if isinstance(c, dict) else {"stage": "schema", "msg": str(c)}
            for c in preflight["checks"]
        ]
        return schema_checks + list(checks)

    def verify(self, deliverable: Any, rule: Optional[dict]) -> dict:
        audit = self._audit_base(rule)
        preflight = self._run_preflight(deliverable, rule)
        if preflight is not None and not preflight.get("passed"):
            out = dict(preflight)
            out["verifier_id"] = self.verifier_id
            out["llm_audit"] = {**audit, "stage": "schema_preflight", "source": "schema"}
            out["reason"] = f"schema preflight: {out.get('reason', 'failed')}"
            return out

        if self._judge_fn is not None:
            out = dict(self._judge_fn(deliverable, rule or {}))
            out.setdefault("verifier_id", self.verifier_id)
            out.setdefault("verified_at", _now_iso())
            out.setdefault("checks", [])
            out["checks"] = self._merge_schema_checks(preflight, out["checks"])
            merged = merge_judge_audit(
                {
                    **audit,
                    "source": "injected",
                    "schema_preflight": "passed" if preflight else "skipped",
                },
                out,
            )
            out["llm_audit"] = merged
            return out

        rubric = None
        if rule:
            rubric = rule.get("llm_rubric") or (rule.get("check") or {}).get("rubric")

        passed = True
        reason = "llm stub: no rubric"
        checks: list[dict] = []

        if rubric and isinstance(rubric, dict):
            required_keywords = rubric.get("required_keywords") or []
            text_blob = str(deliverable).lower()
            missing = [kw for kw in required_keywords if kw.lower() not in text_blob]
            passed = len(missing) == 0
            reason = "llm stub: rubric satisfied" if passed else f"missing keywords: {missing}"
            checks = [{"keyword": kw, "found": kw.lower() in text_blob} for kw in required_keywords]

        checks = self._merge_schema_checks(preflight, checks)

        return {
            "passed": passed,
            "verifier_id": self.verifier_id,
            "reason": reason,
            "checks": checks,
            "verified_at": _now_iso(),
            "llm_audit": {
                **audit,
                "policy": "deterministic keyword stub — replace with real LLM in production",
                "schema_preflight": "passed" if preflight else "skipped",
            },
        }
