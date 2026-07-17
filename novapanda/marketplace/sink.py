"""终态观察者：ExchangeTerminalSnapshot → Volume / Risk / Score 缓存失效。

默认 **不重复写** ReputationLog（ExchangeEngine 已在 confirm/reject 时写入）。
若节点未挂 reputation，可设 ``write_reputation=True`` 由本 Sink 补记。

永不调用 ``state_machine.assert_transition``。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from novapanda import state_machine as sm

from .protocols import RiskSignalStore, ScoreEngine
from .types import ExchangeTerminalSnapshot, OutcomeName
from .volume import VolumeIndex


def snapshot_from_exchange(ex: Any) -> ExchangeTerminalSnapshot:
    """从 Exchange 投影只读快照（解耦用）。"""
    price = ex.price or {}
    vdc_id = None
    if getattr(ex, "vdc", None):
        vdc_id = ex.vdc.get("vdc_id")
    return ExchangeTerminalSnapshot(
        exchange_id=ex.exchange_id,
        state=ex.state,
        client=ex.client,
        provider=ex.provider,
        resource_type=ex.resource_type,
        quantity=int(ex.quantity),
        vdc_id=vdc_id,
        price_amount=int(price.get("amount") or 0),
        price_currency=str(price.get("currency") or "USD"),
        outcome_hint=_outcome_from_state(ex.state),
    )


def _outcome_from_state(state: str) -> Optional[OutcomeName]:
    if state == sm.SETTLED:
        return "settled"
    if state == sm.REJECTED:
        return "rejected"
    if state == sm.EXPIRED_REFUNDED:
        return "expired"
    if state == sm.CANCELLED:
        return "cancelled"
    return None


@dataclass
class MarketplaceTerminalSink:
    """市场侧终态旁路：金额索引 + 风控观察 + 声誉分缓存失效。"""

    volume: VolumeIndex
    risk: Optional[RiskSignalStore] = None
    score_engine: Optional[ScoreEngine] = None
    reputation_log: Any = None
    write_reputation: bool = False
    sybil: Any = None  # Optional[SybilGraphDetector]
    _seen_exchange_ids: set[str] = field(default_factory=set)

    def on_terminal(self, snap: ExchangeTerminalSnapshot) -> None:
        # 幂等：同一 exchange 终态只处理一次（confirm/resolve/expire 重放安全）
        if snap.exchange_id in self._seen_exchange_ids:
            return
        self._seen_exchange_ids.add(snap.exchange_id)

        self.volume.record(snap.exchange_id, snap.price_amount, snap.price_currency)

        if self.risk is not None:
            self.risk.observe_terminal(snap)

        if self.sybil is not None:
            self.sybil.observe(snap)
            self.sybil.detect_and_mark()

        if self.write_reputation and self.reputation_log is not None:
            self._write_log(snap)

        if self.score_engine is not None:
            self.score_engine.invalidate(snap.client)
            self.score_engine.invalidate(snap.provider)

    def on_exchange(self, ex: Any) -> None:
        self.on_terminal(snapshot_from_exchange(ex))

    def _write_log(self, snap: ExchangeTerminalSnapshot) -> None:
        outcome = snap.outcome_hint
        if outcome == "settled":
            self.reputation_log.append(
                agent_id=snap.provider,
                counterparty=snap.client,
                exchange_id=snap.exchange_id,
                vdc_id=snap.vdc_id,
                role="provider",
                outcome="settled",
                resource_type=snap.resource_type,
                quantity=snap.quantity,
            )
            self.reputation_log.append(
                agent_id=snap.client,
                counterparty=snap.provider,
                exchange_id=snap.exchange_id,
                vdc_id=snap.vdc_id,
                role="client",
                outcome="settled",
                resource_type=snap.resource_type,
                quantity=snap.quantity,
            )
        elif outcome == "rejected":
            self.reputation_log.append(
                agent_id=snap.provider,
                counterparty=snap.client,
                exchange_id=snap.exchange_id,
                vdc_id=snap.vdc_id,
                role="provider",
                outcome="rejected",
                resource_type=snap.resource_type,
                quantity=snap.quantity,
            )
