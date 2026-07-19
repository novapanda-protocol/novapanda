"""座舱 / 车机轻量 UX（M4）：把驾驶员/Agent 短指令映射到 Adopter。

不持钥代签；确认仍走本地 IntentMap + Runtime。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CabinConsole:
    """车端操作台：状态 / 确认结算 / 异议 / 导出。"""

    runtime: Any  # AdopterRuntime（避免循环 import）

    def status(self, exchange_id: str) -> dict[str, Any]:
        return self.runtime.apply_intent(exchange_id, "状态")

    def confirm_settlement(self, exchange_id: str) -> dict[str, Any]:
        return self.runtime.apply_intent(exchange_id, "确认")

    def dispute_energy(self, exchange_id: str, reason: str = "电量不对") -> dict[str, Any]:
        return self.runtime.apply_intent(exchange_id, f"不对：{reason}")

    def export_pack(self, exchange_id: str) -> dict[str, Any]:
        return self.runtime.apply_intent(exchange_id, "导出")

    def handle(self, exchange_id: str, utterance: str) -> dict[str, Any]:
        """任意短指令入口。"""
        return self.runtime.apply_intent(exchange_id, utterance)
