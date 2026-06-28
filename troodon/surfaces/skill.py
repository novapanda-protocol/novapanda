"""Skill 接入面：把交割能力暴露为一个可被 Agent 直接调用的技能对象。

最薄的"函数式"接入：Agent 持有 ExchangeSkill 即可用自然的方法/动作名完成交割。
"""

from __future__ import annotations

from typing import Any

from .base import OPERATIONS_BY_NAME, Client, dispatch


class ExchangeSkill:
    def __init__(self, client: Client) -> None:
        self.client = client

    def actions(self) -> list[str]:
        return list(OPERATIONS_BY_NAME.keys())

    def run(self, action: str, **params: Any) -> Any:
        return dispatch(self.client, action, params)
