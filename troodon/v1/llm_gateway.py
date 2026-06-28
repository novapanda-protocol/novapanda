"""LLM 裁判 HTTP 网关客户端（占位：对接外部 LLM 编排服务）。

约定 REST API（参考实现 / fake server 共用）：
  POST {base}/judge
    body: {deliverable, rule_id, resource_type, rubric, schema?}
    -> {passed, reason, checks?}
"""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx


class LLMGatewayError(Exception):
    pass


class HttpLLMGateway:
    def __init__(self, base_url: str, *, http: Optional[httpx.Client] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = http or httpx.Client(base_url=self.base_url, timeout=60.0)
        self.last_audit: dict = {}

    def judge(self, deliverable: Any, rule: dict) -> dict:
        request_body = {
            "deliverable": deliverable,
            "rule_id": rule.get("rule_id"),
            "resource_type": rule.get("resource_type"),
            "rubric": rule.get("llm_rubric"),
            "rule_schema": rule.get("schema"),
        }
        self.last_audit = {
            "gateway_url": self.base_url,
            "gateway_request": request_body,
            "prompt_snapshot": json.dumps(request_body, ensure_ascii=False, sort_keys=True),
            "model_version": "http-judge/v1",
        }
        r = self._http.post("/judge", json=request_body)
        if r.status_code >= 400:
            raise LLMGatewayError(f"LLM gateway /judge 失败: {r.status_code} {r.text}")
        data = r.json()
        if "passed" not in data:
            raise LLMGatewayError("LLM gateway 响应缺少 passed")
        data["_audit_extras"] = dict(self.last_audit)
        return data


def make_http_judge_fn(gateway: HttpLLMGateway):
    """包装为 LLMJudgeVerifier 可用的 judge_fn（预检仍在节点侧）。"""

    def _fn(deliverable: Any, rule: dict) -> dict:
        return gateway.judge(deliverable, rule)

    return _fn
