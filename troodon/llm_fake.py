"""LLM 网关 fake server：供集成测试与本地开发（内部用确定性 judge，非真 LLM）。"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from .v1.judge_registry import field_match_judge, regex_judge


class JudgeBody(BaseModel):
    deliverable: Any
    rule_id: Optional[str] = None
    resource_type: Optional[str] = None
    rubric: Optional[dict] = None
    rule_schema: Optional[dict] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionsBody(BaseModel):
    model: Optional[str] = None
    messages: list[ChatMessage]
    response_format: Optional[dict] = None


def _rule_from_judge_body(body: JudgeBody) -> dict:
    rule = {
        "rule_id": body.rule_id,
        "resource_type": body.resource_type,
        "llm_rubric": body.rubric or {},
    }
    if body.rule_schema:
        rule["schema"] = body.rule_schema
    return rule


def create_llm_fake_app(*, mode: str = "regex") -> FastAPI:
    """mode: regex | field_match — 决定 judge 使用的内置确定性 judge。"""
    judge = field_match_judge if mode == "field_match" else regex_judge
    app = FastAPI(title="Fake LLM Gateway")

    @app.post("/judge")
    def judge_endpoint(body: JudgeBody):
        result = judge(body.deliverable, _rule_from_judge_body(body))
        result.setdefault("gateway", "fake")
        return result

    @app.post("/v1/chat/completions")
    def chat_completions(body: ChatCompletionsBody):
        """OpenAI-compatible：从 prompt 解析 deliverable + rubric。"""
        if not body.messages:
            content = json.dumps({"passed": False, "reason": "no messages", "checks": []})
            return {"choices": [{"message": {"role": "assistant", "content": content}}]}
        prompt = body.messages[-1].content
        deliverable: Any = {}
        rubric: dict = {}
        rule_id = None
        for line in prompt.splitlines():
            if line.startswith("rule_id="):
                rule_id = line.split("=", 1)[1].strip().strip("'\"")
            elif line.startswith("rubric="):
                rubric = json.loads(line.split("=", 1)[1])
            elif line.startswith("deliverable="):
                deliverable = json.loads(line.split("=", 1)[1])
        rule = {"rule_id": rule_id, "llm_rubric": rubric}
        result = judge(deliverable, rule)
        content = json.dumps({
            "passed": result.get("passed"),
            "reason": result.get("reason"),
            "checks": result.get("checks", []),
        })
        return {
            "id": "chatcmpl-fake",
            "object": "chat.completion",
            "model": body.model or "troodon-judge-stub",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
        }

    return app
