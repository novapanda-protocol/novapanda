"""动态声誉 ScoreEngine：基础成功率 × 金额衰减权重 − Sybil/wash 惩罚。

公式（实现权威）：

1. **单笔权重（金额衰减）**

   ``w(A) = ln(1 + A / A_dust) / ln(1 + A_ref / A_dust)``

   - ``A``：名义金额（来自 VolumeIndex；缺失时退化为 ``quantity``）
   - ``A_dust``：尘埃阈值，小额刷单权重接近 0
   - ``A_ref``：参考大单，使 ``w(A_ref) = 1``；更大单次权重 >1 但对数缓增

2. **基础声誉分**

   ``base = Σ w_i · y_i / Σ w_i``

   - ``y_i = 1`` if outcome=settled；``0`` if rejected
   - expired/cancelled 不进分母（与现有 weighted_score 一致：只计 settled/rejected）

3. **有效分**

   ``effective = clamp01(base · (1 - risk_penalty))``

   ``risk_penalty`` 来自 ``RiskSignalStore.penalty``（女巫/刷单）。

本模块只读派生，不写 Exchange、不改 ``state_machine``。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

from .protocols import RiskSignalStore, ScoreEngine
from .types import ReputationView
from .volume import InMemoryVolumeIndex, VolumeIndex

SCORE_VERSION = "0.1-marketplace"


@dataclass
class ScorePolicy:
    """金额衰减与冷启动策略。"""

    dust_amount: int = 10
    reference_amount: int = 1000
    # 无 VolumeIndex 时用 quantity * quantity_unit_notional 近似
    quantity_unit_notional: int = 1
    cold_start_score: Optional[float] = None  # None → score 保持 None


@dataclass
class DynamicScoreEngine:
    """生产默认实现：对接 ReputationLog.entries + VolumeIndex + RiskSignalStore。"""

    reputation_log: Any  # duck: .entries(agent_id=...) -> list[dict]
    volume: VolumeIndex = field(default_factory=InMemoryVolumeIndex)
    risk: Optional[RiskSignalStore] = None
    policy: ScorePolicy = field(default_factory=ScorePolicy)
    _cache: dict[str, ReputationView] = field(default_factory=dict)

    def view(self, agent_id: str) -> ReputationView:
        cached = self._cache.get(agent_id)
        if cached is not None:
            return cached
        view = self._compute(agent_id)
        self._cache[agent_id] = view
        return view

    def views(self, agent_ids: list[str]) -> dict[str, ReputationView]:
        return {aid: self.view(aid) for aid in agent_ids}

    def invalidate(self, agent_id: str) -> None:
        self._cache.pop(agent_id, None)

    def invalidate_all(self) -> None:
        self._cache.clear()

    # ----- 核心计算 -----

    def amount_weight(self, amount: int) -> float:
        """金额衰减权重：尘埃单 → 0 附近；参考单 → 1；更大单对数缓增。"""
        dust = max(1, self.policy.dust_amount)
        ref = max(dust + 1, self.policy.reference_amount)
        a = max(0, amount)
        numer = math.log1p(a / dust)
        denom = math.log1p(ref / dust)
        if denom <= 0:
            return 0.0
        return numer / denom

    def _compute(self, agent_id: str) -> ReputationView:
        entries = list(self.reputation_log.entries(agent_id=agent_id))
        settled_n = rejected_n = 0
        weighted_success = 0.0
        weighted_total = 0.0
        volume_score_acc = 0.0
        volume_w_acc = 0.0

        for entry in entries:
            outcome = entry.get("outcome")
            if outcome not in ("settled", "rejected"):
                continue
            amount = self._notional_for(entry)
            w = self.amount_weight(amount)
            if outcome == "settled":
                settled_n += 1
                weighted_success += w
                volume_score_acc += w
            else:
                rejected_n += 1
            weighted_total += w
            volume_w_acc += w

        entry_count = len(entries)
        if weighted_total <= 0:
            base: Optional[float] = self.policy.cold_start_score
            volume_score = 0.0
        else:
            base = round(weighted_success / weighted_total, 4)
            volume_score = round(volume_score_acc / volume_w_acc, 4) if volume_w_acc else 0.0

        risk_penalty = 0.0
        if self.risk is not None:
            risk_penalty = float(self.risk.penalty(agent_id))
            # 无历史时可选打上冷启动信号惩罚（不强制写 store，仅在 view 层体现）
            if entry_count == 0 and risk_penalty <= 0:
                risk_penalty = 0.0

        if base is None:
            effective = None
        else:
            effective = round(max(0.0, min(1.0, base * (1.0 - risk_penalty))), 4)

        return ReputationView(
            agent_id=agent_id,
            score=base,
            entry_count=entry_count,
            settled_count=settled_n,
            rejected_count=rejected_n,
            volume_score=volume_score,
            risk_penalty=risk_penalty,
            effective_score=effective,
            score_version=SCORE_VERSION,
        )

    def _notional_for(self, entry: dict) -> int:
        eid = entry.get("exchange_id") or ""
        amt = self.volume.notional(eid) if eid else None
        if amt is not None:
            return int(amt)
        qty = int(entry.get("quantity") or 0)
        return max(0, qty * self.policy.quantity_unit_notional)


# 结构性确认：实现满足 Protocol
def _check_score_engine(engine: DynamicScoreEngine) -> ScoreEngine:
    return engine
