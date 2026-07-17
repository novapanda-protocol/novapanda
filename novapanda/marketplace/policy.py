"""市场与声誉门闸统一配置（MatchRouter.min_reputation ↔ Gate）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ReputationMatchPolicy:
    """单一真相源：节点门闸与撮合最低分共用。

    - ``min_score``：propose/escrow Gate 与 MatchQuery.min_reputation 默认值
    - ``strict_no_history``：无历史时 Gate 是否拒绝（撮合侧仍可用 cold_reputation）
    """

    min_score: Optional[float] = None
    strict_no_history: bool = False
    cold_reputation: float = 0.5

    def match_min_reputation(self) -> float:
        """撮合硬过滤阈值；未配置门闸时为 0（不挡）。"""
        if self.min_score is None:
            return 0.0
        return float(self.min_score)
