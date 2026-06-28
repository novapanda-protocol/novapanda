"""A2A（Agent-to-Agent）接入面：把协议操作暴露为 A2A 技能。

产出一张 AgentCard（能力清单），并把收到的技能调用分发到统一操作注册表。
与具体 A2A 运行时解耦：任何 A2A 服务端都可挂载本 card 与 handler。
"""

from __future__ import annotations

from typing import Any, Optional

from .base import OPERATIONS, Client, dispatch


def agent_card(*, name: str = "troodon-agent", url: Optional[str] = None) -> dict:
    return {
        "name": name,
        "description": "Troodon-compatible 价值交割 Agent",
        "url": url,
        "capabilities": {"streaming": False, "pushNotifications": False},
        "skills": [
            {
                "id": op.name,
                "name": op.name,
                "description": op.description,
                "inputSchema": op.input_schema,
            }
            for op in OPERATIONS
        ],
    }


class A2ABinding:
    def __init__(self, client: Client, *, name: str = "troodon-agent") -> None:
        self.client = client
        self.name = name

    def card(self) -> dict:
        return agent_card(name=self.name)

    def handle(self, skill_id: str, params: dict | None = None) -> Any:
        return dispatch(self.client, skill_id, params)
