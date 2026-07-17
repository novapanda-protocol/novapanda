"""Create → Verify → Settle → Archive 编排（映射到 CORE 状态机）。

用户叙事四阶段与权威状态机对照：

| 叙事阶段 | CORE 状态 |
|----------|-----------|
| Create   | PROPOSED → CONTRACTED → ESCROWED（+ 可选链上 createVDC） |
| Verify   | DELIVERED → VERIFIED（经 Verification Gateway） |
| Settle   | VERIFIED → SETTLED（confirm + SettlementAdapter / settlePayment） |
| Archive  | 终态双签 VDC 不可变归档；DISPUTED 走仲裁后再归档 |

超时：
- deliver 超时 → ``ExchangeEngine.sweep`` → EXPIRED_REFUNDED
- 验证关口 SLA 超时 → 本编排触发 refund 意图 + 可选 ``refundIfTimedOut`` 链上释放
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from novapanda import state_machine as sm
from novapanda.exchange import Exchange, ExchangeEngine
from novapanda.hashing import result_hash_of_json
from novapanda.identity import Identity

from .credential import VerificationCredential, verify_credential
from .gateway import ProofSubmission, VerificationGateway


class LifecyclePhase(str, Enum):
    CREATE = "Create"
    VERIFY = "Verify"
    SETTLE = "Settle"
    ARCHIVE = "Archive"


def phase_of(state: str) -> LifecyclePhase:
    if state in (sm.PROPOSED, sm.CONTRACTED, sm.ESCROWED):
        return LifecyclePhase.CREATE
    if state in (sm.DELIVERED, sm.VERIFIED, sm.DISPUTED):
        return LifecyclePhase.VERIFY if state == sm.DELIVERED else (
            LifecyclePhase.SETTLE if state == sm.VERIFIED else LifecyclePhase.VERIFY
        )
    if state == sm.SETTLED:
        return LifecyclePhase.ARCHIVE
    # REJECTED / EXPIRED_REFUNDED / CANCELLED → 归档失败终态
    return LifecyclePhase.ARCHIVE


@dataclass
class AutoSettleOrchestrator:
    """生产级 Agent 网络的自动化验证+结算编排原型。"""

    engine: ExchangeEngine
    gateway: VerificationGateway
    client: Identity
    provider: Identity
    # 可选：EVM 语义孪生 / 真实合约适配器（实现 create/fulfill/settle/dispute/timeout）
    chain: Any = None
    credentials: dict[str, VerificationCredential] = field(default_factory=dict)

    def create(
        self,
        *,
        resource_type: str,
        quantity: int,
        rule_id: str,
        price: dict,
        idempotency_key: str,
        timeouts: Optional[dict] = None,
        rule: Optional[dict] = None,
    ) -> Exchange:
        """Create：条款双签 + 资金托管（链下 adapter；若有 chain 则同步 createVDC）。"""
        ex = self.engine.propose(
            client=self.client.agent_id,
            provider=self.provider.agent_id,
            resource_type=resource_type,
            quantity=quantity,
            rule_id=rule_id,
            price=price,
            idempotency_key=idempotency_key,
            timeouts=timeouts,
        )
        from novapanda.terms import sign_contract_ack

        for party in (self.client, self.provider):
            self.engine.contract(
                ex.exchange_id,
                party=party.agent_id,
                signature=sign_contract_ack(party, ex),
            )
        self.engine.escrow(
            ex.exchange_id, amount=price["amount"], currency=price["currency"]
        )
        ex = self.engine.get(ex.exchange_id)
        if self.chain is not None:
            self.chain.create_vdc(
                exchange_id=ex.exchange_id,
                client=self.client.agent_id,
                provider=self.provider.agent_id,
                amount=price["amount"],
                deliver_deadline_ts=ex.deadline_ts,
                verify_deadline_ts=_verify_deadline(ex, self.gateway),
            )
        if rule is not None:
            self._rules = getattr(self, "_rules", {})
            self._rules[ex.exchange_id] = rule
        return self.engine.get(ex.exchange_id)

    def fulfill_with_proof(self, exchange_id: str, deliverable: Any) -> tuple[Exchange, Any]:
        """Provider 交付 + 网关验收。成功则进入 VERIFIED 并可选链上 fulfill。"""
        ex = self.engine.deliver(exchange_id, self.provider, deliverable)
        rule = getattr(self, "_rules", {}).get(exchange_id)
        outcome = self.gateway.submit_proof(
            ProofSubmission(
                exchange_id=exchange_id,
                vdc_id=ex.vdc["vdc_id"],
                result_hash=ex.result_hash or result_hash_of_json(deliverable),
                rule_id=ex.rule_id,
                deliverable=deliverable,
                rule=rule,
            )
        )
        if not outcome.passed or outcome.credential is None:
            # 验收失败：走引擎 verify 同一 rule 以进入 REJECTED + refund
            self.engine.verify(exchange_id, rule=rule)
            return self.engine.get(exchange_id), outcome

        assert verify_credential(outcome.credential)
        self.credentials[exchange_id] = outcome.credential
        # 引擎 verify 使用同一 rule，与网关结论应对齐
        self.engine.verify(exchange_id, rule=rule)
        if self.chain is not None:
            self.chain.fulfill_vdc_with_proof(
                exchange_id=exchange_id,
                result_hash=ex.result_hash,
                credential_id=outcome.credential.credential_id,
                verifier=outcome.credential.verifier_agent_id,
            )
        return self.engine.get(exchange_id), outcome

    def settle(self, exchange_id: str) -> Exchange:
        """Settle：client 双签确认 + 资金释放。"""
        ex = self.engine.confirm(exchange_id, self.client)
        if self.chain is not None:
            cred = self.credentials.get(exchange_id)
            self.chain.settle_payment(
                exchange_id=exchange_id,
                credential_id=cred.credential_id if cred else "",
            )
        return ex

    def dispute(self, exchange_id: str, *, by: Identity, reason: str) -> Exchange:
        ex = self.engine.dispute(exchange_id, by=by.agent_id, reason=reason)
        if self.chain is not None:
            self.chain.initiate_dispute(exchange_id=exchange_id, by=by.agent_id, reason=reason)
        return ex

    def archive_record(self, exchange_id: str) -> dict:
        """Archive：导出可独立复验的终态包。"""
        ex = self.engine.get(exchange_id)
        cred = self.credentials.get(exchange_id)
        return {
            "phase": phase_of(ex.state).value,
            "exchange_id": exchange_id,
            "state": ex.state,
            "vdc": ex.vdc,
            "verify_result": ex.verify_result,
            "verification_credential": cred.to_dict() if cred else None,
            "settlement_handle": ex.escrow_handle,
        }

    def sweep_timeouts(self, *, now_ts: float) -> list[str]:
        """交付超时 + 验证关口超时 → 退款释放。"""
        expired_ids: list[str] = []
        for ex in self.engine.sweep(now_ts=now_ts):
            expired_ids.append(ex.exchange_id)
            if self.chain is not None:
                self.chain.refund_if_timed_out(exchange_id=ex.exchange_id, now_ts=now_ts)

        # 已进入 verifying 但网关 SLA 逾期、交换仍卡在 DELIVERED
        for exchange_id, job in list(self.gateway._jobs.items()):
            if not self.gateway.is_verify_overdue(exchange_id, now_ts=now_ts):
                continue
            try:
                ex = self.engine.get(exchange_id)
            except Exception:  # noqa: BLE001
                continue
            if ex.state != sm.DELIVERED:
                continue
            # 验证关口超时：释放托管（CORE: DELIVERED → EXPIRED_REFUNDED）
            self.engine.expire(exchange_id)
            expired_ids.append(exchange_id)
            if self.chain is not None:
                self.chain.refund_if_timed_out(exchange_id=exchange_id, now_ts=now_ts)
        return expired_ids


def _verify_deadline(ex: Exchange, gateway: VerificationGateway) -> Optional[float]:
    if gateway.verify_sla_seconds <= 0:
        return None
    if ex.deadline_ts is None:
        return None
    # 粗粒度：deliver 截止后再加验证 SLA（生产应在 DELIVERED 时重设）
    return float(ex.deadline_ts) + gateway.verify_sla_seconds
