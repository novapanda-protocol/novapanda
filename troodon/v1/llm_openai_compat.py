"""OpenAI-compatible LLM 网关适配（/v1/chat/completions → judge 结果）。

生产可指向 OpenAI / Azure / 自建编排；测试用 llm_fake 的 compat 端点。
"""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx

from .llm_gateway import LLMGatewayError


def build_judge_prompt(deliverable: Any, rule: dict) -> str:
    rubric = rule.get("llm_rubric") or {}
    return (
        "You are a deterministic delivery judge. "
        "Reply with JSON only: {\"passed\": bool, \"reason\": str, \"checks\": []}.\n"
        f"rule_id={rule.get('rule_id')!r}\n"
        f"rubric={json.dumps(rubric, ensure_ascii=False)}\n"
        f"deliverable={json.dumps(deliverable, ensure_ascii=False)}"
    )


def parse_judge_content(content: str) -> dict:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMGatewayError(f"LLM 响应非 JSON: {exc}") from exc
    if "passed" not in data:
        raise LLMGatewayError("LLM 响应缺少 passed")
    return data


class OpenAICompatLLMGateway:
    """POST /v1/chat/completions，解析 message.content 为 judge 结果。"""

    def __init__(
        self,
        base_url: str,
        *,
        model: str = "troodon-judge-stub",
        api_key: Optional[str] = None,
        http: Optional[httpx.Client] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = http or httpx.Client(
            base_url=self.base_url, timeout=60.0, headers=headers,
        )
        self.last_audit: dict = {}

    def judge(self, deliverable: Any, rule: dict) -> dict:
        prompt = build_judge_prompt(deliverable, rule)
        request_body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
        self.last_audit = {
            "gateway_url": self.base_url,
            "prompt_snapshot": prompt,
            "model_version": self.model,
            "gateway_request": {
                "model": self.model,
                "message_count": len(request_body["messages"]),
            },
        }
        r = self._http.post("/v1/chat/completions", json=request_body)
        if r.status_code >= 400:
            raise LLMGatewayError(f"OpenAI compat 失败: {r.status_code} {r.text}")
        body = r.json()
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMGatewayError(f"OpenAI compat 响应格式异常: {body}") from exc
        out = parse_judge_content(content)
        out.setdefault("gateway", "openai-compat")
        out["_audit_extras"] = dict(self.last_audit)
        return out


def make_openai_judge_fn(gateway: OpenAICompatLLMGateway):
    def _fn(deliverable: Any, rule: dict) -> dict:
        return gateway.judge(deliverable, rule)

    return _fn
