"""EVM 结算轨语义孪生（与 ``bindings/evm/VDCSettlement.sol`` 对齐）。

链上合约是 NP-SETTLE 的一种 rail，不进入 CORE 状态机（ADR-0002）。
本模块供无 Foundry 的 CI 验证状态转换与超时退款逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


class OnChainStatus(IntEnum):
    NONE = 0
    FUNDED = 1
    FULFILLED = 2
    SETTLED = 3
    DISPUTED = 4
    REFUNDED = 5


@dataclass
class OnChainVDC:
    exchange_id: str
    client: str
    provider: str
    amount: int
    deliver_deadline_ts: Optional[float]
    verify_deadline_ts: Optional[float]
    result_hash: str = ""
    credential_id: str = ""
    verifier: str = ""
    status: OnChainStatus = OnChainStatus.FUNDED
    dispute_reason: str = ""


@dataclass
class EvmSettlementRail:
    """内存实现：镜像 Solidity 核心状态机。"""

    arbitrator: str = "arbitrator:default"
    trusted_verifiers: set[str] = field(default_factory=set)
    records: dict[str, OnChainVDC] = field(default_factory=dict)

    def create_vdc(
        self,
        *,
        exchange_id: str,
        client: str,
        provider: str,
        amount: int,
        deliver_deadline_ts: Optional[float] = None,
        verify_deadline_ts: Optional[float] = None,
    ) -> OnChainVDC:
        if exchange_id in self.records:
            raise ValueError("VDC already exists")
        if amount <= 0:
            raise ValueError("amount must be > 0")
        rec = OnChainVDC(
            exchange_id=exchange_id,
            client=client,
            provider=provider,
            amount=amount,
            deliver_deadline_ts=deliver_deadline_ts,
            verify_deadline_ts=verify_deadline_ts,
        )
        self.records[exchange_id] = rec
        return rec

    def fulfill_vdc_with_proof(
        self,
        *,
        exchange_id: str,
        result_hash: str,
        credential_id: str,
        verifier: str,
    ) -> OnChainVDC:
        rec = self._get(exchange_id)
        if rec.status != OnChainStatus.FUNDED:
            raise ValueError("not FUNDED")
        if self.trusted_verifiers and verifier not in self.trusted_verifiers:
            raise ValueError("untrusted verifier")
        if not result_hash or not credential_id:
            raise ValueError("missing proof")
        rec.result_hash = result_hash
        rec.credential_id = credential_id
        rec.verifier = verifier
        rec.status = OnChainStatus.FULFILLED
        return rec

    def settle_payment(self, *, exchange_id: str, credential_id: str = "") -> OnChainVDC:
        rec = self._get(exchange_id)
        if rec.status not in (OnChainStatus.FULFILLED, OnChainStatus.DISPUTED):
            raise ValueError("not settleable")
        if credential_id and rec.credential_id and credential_id != rec.credential_id:
            raise ValueError("credential mismatch")
        rec.status = OnChainStatus.SETTLED
        return rec

    def initiate_dispute(self, *, exchange_id: str, by: str, reason: str) -> OnChainVDC:
        rec = self._get(exchange_id)
        if rec.status != OnChainStatus.FULFILLED:
            raise ValueError("dispute only from FULFILLED")
        if by not in (rec.client, rec.provider, self.arbitrator):
            raise ValueError("unauthorized")
        rec.status = OnChainStatus.DISPUTED
        rec.dispute_reason = reason
        return rec

    def resolve_dispute(self, *, exchange_id: str, pay_provider: bool, by: str) -> OnChainVDC:
        rec = self._get(exchange_id)
        if rec.status != OnChainStatus.DISPUTED:
            raise ValueError("not DISPUTED")
        if by != self.arbitrator:
            raise ValueError("only arbitrator")
        rec.status = OnChainStatus.SETTLED if pay_provider else OnChainStatus.REFUNDED
        return rec

    def refund_if_timed_out(self, *, exchange_id: str, now_ts: float) -> OnChainVDC:
        """任何人可调用：交付超时（仍 FUNDED）或验证超时（仍 FUNDED 且已过 verify 截止）。

        注：FULFILLED 后默认不再因 deliver 超时退款（与 CORE：DELIVERED 后由 verify/confirm 截止处理）。
        若仍为 FUNDED 且超过 deliver 或 verify deadline → REFUNDED。
        """
        rec = self._get(exchange_id)
        if rec.status != OnChainStatus.FUNDED:
            return rec
        overdue = False
        if rec.deliver_deadline_ts is not None and now_ts > rec.deliver_deadline_ts:
            overdue = True
        if rec.verify_deadline_ts is not None and now_ts > rec.verify_deadline_ts:
            overdue = True
        if not overdue:
            raise ValueError("not timed out")
        rec.status = OnChainStatus.REFUNDED
        return rec

    def _get(self, exchange_id: str) -> OnChainVDC:
        rec = self.records.get(exchange_id)
        if rec is None:
            raise KeyError(exchange_id)
        return rec
