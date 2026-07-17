"""风控信号：女巫集群 / 刷单等惩罚系数（纯旁路，不碰状态机）。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .types import ExchangeTerminalSnapshot, RiskKind, RiskSignal


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class RiskPolicy:
    """量化阈值（可配置；默认偏保守防小额对刷）。"""

    # 低于该名义金额的成交视为「尘埃单」，刷单权重更高
    dust_amount: int = 10
    # 同一对手方对在窗口内 settled 次数 ≥ 此值且多为尘埃单 → wash
    wash_pair_threshold: int = 5
    wash_dust_ratio: float = 0.8
    # 惩罚聚合：1 - Π(1 - severity_i)，再 clamp
    max_penalty: float = 0.95
    # 新身份：尚无历史时的基础惩罚（冷启动折扣）
    new_identity_severity: float = 0.15


@dataclass
class InMemoryRiskSignalStore:
    """内存风控：观察终态快照 → 产生信号；``penalty`` 供 ScoreEngine 扣分。"""

    policy: RiskPolicy = field(default_factory=RiskPolicy)
    _signals: dict[str, list[RiskSignal]] = field(default_factory=lambda: defaultdict(list))
    # (lo_agent, hi_agent) → list of amounts for settled pairs
    _pair_settled_amounts: dict[tuple[str, str], list[int]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def observe_terminal(self, snap: ExchangeTerminalSnapshot) -> list[RiskSignal]:
        emitted: list[RiskSignal] = []
        outcome = snap.outcome_hint or _infer_outcome(snap.state)
        if outcome != "settled":
            return emitted

        pair = _pair_key(snap.client, snap.provider)
        amounts = self._pair_settled_amounts[pair]
        amounts.append(max(0, snap.price_amount))

        if len(amounts) >= self.policy.wash_pair_threshold:
            dust_n = sum(1 for a in amounts if a <= self.policy.dust_amount)
            ratio = dust_n / len(amounts)
            if ratio >= self.policy.wash_dust_ratio:
                sev = min(1.0, 0.4 + 0.1 * (len(amounts) - self.policy.wash_pair_threshold))
                for subject in (snap.client, snap.provider):
                    sig = RiskSignal(
                        kind=RiskKind.WASH_TRADE,
                        subject_agent_id=subject,
                        severity=round(sev, 4),
                        evidence_ref=f"pair:{pair[0][:16]}|{pair[1][:16]}|n={len(amounts)}",
                        observed_at=_now_iso(),
                    )
                    self._signals[subject].append(sig)
                    emitted.append(sig)

        # 极小额高频自我闭环（client==provider 不应发生；防御）
        if snap.client == snap.provider:
            sig = RiskSignal(
                kind=RiskKind.BURST_SELF_DEAL,
                subject_agent_id=snap.client,
                severity=1.0,
                evidence_ref=snap.exchange_id,
                observed_at=_now_iso(),
            )
            self._signals[snap.client].append(sig)
            emitted.append(sig)

        return emitted

    def mark_sybil_cluster(
        self,
        agent_ids: list[str],
        *,
        severity: float,
        cluster_id: str,
    ) -> list[RiskSignal]:
        """外部图分析 / 人工研判写入女巫集群（本模块不跑图算法）。"""
        sev = max(0.0, min(1.0, severity))
        out: list[RiskSignal] = []
        for aid in agent_ids:
            sig = RiskSignal(
                kind=RiskKind.SYBIL_CLUSTER,
                subject_agent_id=aid,
                severity=sev,
                evidence_ref=f"cluster:{cluster_id}",
                observed_at=_now_iso(),
            )
            self._signals[aid].append(sig)
            out.append(sig)
        return out

    def mark_new_identity(self, agent_id: str) -> RiskSignal:
        sig = RiskSignal(
            kind=RiskKind.NEW_IDENTITY,
            subject_agent_id=agent_id,
            severity=self.policy.new_identity_severity,
            evidence_ref="cold-start",
            observed_at=_now_iso(),
        )
        self._signals[agent_id].append(sig)
        return sig

    def signals_for(self, agent_id: str) -> list[RiskSignal]:
        return list(self._signals.get(agent_id, []))

    def penalty(self, agent_id: str) -> float:
        """聚合惩罚 ∈ [0, max_penalty]。

        使用 ``1 - Π(1 - s_i)``，使多条中等信号可叠加，又不会简单线性爆表。
        同类信号取 max severity，避免同一次 wash 重复叠加。
        """
        by_kind: dict[RiskKind, float] = {}
        for sig in self.signals_for(agent_id):
            prev = by_kind.get(sig.kind, 0.0)
            by_kind[sig.kind] = max(prev, max(0.0, min(1.0, sig.severity)))
        if not by_kind:
            return 0.0
        survive = 1.0
        for s in by_kind.values():
            survive *= 1.0 - s
        return round(min(self.policy.max_penalty, 1.0 - survive), 4)


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def _infer_outcome(state: str) -> Optional[str]:
    if state == "SETTLED":
        return "settled"
    if state == "REJECTED":
        return "rejected"
    if state == "EXPIRED_REFUNDED":
        return "expired"
    if state == "CANCELLED":
        return "cancelled"
    return None
