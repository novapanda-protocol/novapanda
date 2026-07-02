"""验收器接口：把「交付是否达标」与「价格」彻底解耦。

验收是确定性的、可被任意第三方独立复算的——这样信任才不必寄托于任何单一节点。
SchemaVerifier（JSON Schema 校验）在 M3 实现；此处先定义协议与默认实现。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Protocol


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Verifier(Protocol):
    verifier_id: str

    def verify(self, deliverable: Any, rule: Optional[dict]) -> dict:
        """返回 VerifyResult: {passed, verifier_id, reason, verified_at, checks?}。"""
        ...


class AcceptAllVerifier:
    """v0 默认：恒通过。仅用于打通流程/模拟，生产应替换为确定性验收器。"""

    verifier_id = "verifier:accept-all"

    def verify(self, deliverable: Any, rule: Optional[dict]) -> dict:
        return {
            "passed": True,
            "verifier_id": self.verifier_id,
            "reason": "accept-all (v0 default)",
            "verified_at": _now_iso(),
        }


class SchemaVerifier:
    """确定性验收：用 rule.schema（JSON Schema, Draft 2020-12）校验交付物。

    决策 (passed/checks) 仅依赖 (deliverable, rule)，任何第三方可独立复算得到相同结论。
    """

    verifier_id = "verifier:json-schema/v1"

    def verify(self, deliverable: Any, rule: Optional[dict]) -> dict:
        from jsonschema import Draft202012Validator

        from .v3.physical import is_reserved_physical_type, validate_physical_deliverable

        resource_type = (rule or {}).get("resource_type")
        phys_checks: list[dict] = []
        if resource_type and is_reserved_physical_type(resource_type):
            phys_errors = validate_physical_deliverable(resource_type, deliverable)
            phys_checks = [{"field": e} for e in phys_errors]
            if phys_errors:
                return {
                    "passed": False,
                    "verifier_id": self.verifier_id,
                    "reason": "physical deliverable invalid",
                    "checks": phys_checks,
                    "verified_at": _now_iso(),
                }

        if not rule or "schema" not in rule:
            if resource_type and is_reserved_physical_type(resource_type):
                return {
                    "passed": True,
                    "verifier_id": self.verifier_id,
                    "reason": "physical deliverable valid",
                    "checks": phys_checks,
                    "verified_at": _now_iso(),
                }
            return {
                "passed": False,
                "verifier_id": self.verifier_id,
                "reason": "rule 缺少 schema",
                "checks": [],
                "verified_at": _now_iso(),
            }

        validator = Draft202012Validator(rule["schema"])
        errors = sorted(
            validator.iter_errors(deliverable),
            key=lambda e: (list(e.absolute_path), e.message),
        )
        checks = [
            {"path": "/" + "/".join(str(p) for p in e.absolute_path), "msg": e.message}
            for e in errors
        ]
        passed = not errors
        return {
            "passed": passed,
            "verifier_id": self.verifier_id,
            "reason": "schema valid" if passed else f"{len(checks)} 处校验失败",
            "checks": checks,
            "verified_at": _now_iso(),
        }


def make_verifier(
    name: str = "schema",
    *,
    llm_judge: Optional[str] = None,
    llm_gateway_url: Optional[str] = None,
    llm_gateway_http=None,
    llm_model: Optional[str] = None,
    llm_api_key: Optional[str] = None,
):
    """工厂：schema | llm | accept-all。"""
    n = (name or "schema").lower()
    if n == "llm":
        from .v1.llm_verifier import LLMJudgeVerifier
        from .v1.judge_registry import resolve_judge_fn

        if (llm_judge or "").lower() == "http":
            from .v1.llm_gateway import HttpLLMGateway, make_http_judge_fn

            if llm_gateway_http is not None:
                base = llm_gateway_url or "http://testserver"
                gw = HttpLLMGateway(base, http=llm_gateway_http)
            else:
                if not llm_gateway_url:
                    raise ValueError(
                        "NOVAPANDA_LLM_JUDGE=http 时必须设置 NOVAPANDA_LLM_GATEWAY_URL"
                    )
                gw = HttpLLMGateway(llm_gateway_url)
            return LLMJudgeVerifier(
                judge_fn=make_http_judge_fn(gw),
                model_id="http-gateway/v0",
            )
        if (llm_judge or "").lower() == "openai":
            from .v1.llm_openai_compat import OpenAICompatLLMGateway, make_openai_judge_fn

            model = llm_model or "novapanda-judge-stub"
            if llm_gateway_http is not None:
                base = llm_gateway_url or "http://testserver"
                gw = OpenAICompatLLMGateway(
                    base, model=model, api_key=llm_api_key, http=llm_gateway_http,
                )
            else:
                if not llm_gateway_url:
                    raise ValueError(
                        "NOVAPANDA_LLM_JUDGE=openai 时必须设置 NOVAPANDA_LLM_GATEWAY_URL"
                    )
                gw = OpenAICompatLLMGateway(
                    llm_gateway_url, model=model, api_key=llm_api_key,
                )
            return LLMJudgeVerifier(
                judge_fn=make_openai_judge_fn(gw),
                model_id=f"openai-compat/{model}",
            )
        if (llm_judge or "").lower().startswith("consensus:"):
            from .v1.llm_consensus import consensus_judge_fn, parse_consensus_judges

            judges, strategy = parse_consensus_judges(llm_judge, resolve_judge_fn)
            return LLMJudgeVerifier(
                judge_fn=consensus_judge_fn(judges, strategy=strategy),
                model_id=f"consensus-{strategy}/v1",
            )
        judge_fn = resolve_judge_fn(llm_judge) if llm_judge else None
        model_id = f"builtin-{llm_judge}/v1" if llm_judge else None
        return LLMJudgeVerifier(judge_fn=judge_fn, model_id=model_id)
    if n in ("accept-all", "accept_all", "acceptall"):
        return AcceptAllVerifier()
    return SchemaVerifier()
