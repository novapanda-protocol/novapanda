"""Exchange 引擎（v0 内存版）：编排状态机 + 验收 + 结算 + VDC 双签。

这是「身体/可运营」层：人人可自建、可被替代。它只负责编排，
真理（VDC、签名、信誉）都是可被任何第三方脱离本节点独立复验的。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from . import state_machine as sm
from . import vdc as V
from .hashing import result_hash_of_json
from .identity import Identity
from .blobs import inline_ref, is_stored_ref
from .settlement import SettlementAdapter
from .store import InMemoryStore
from .terms import terms_hash_from_exchange, verify_contract_ack
from .verifier import AcceptAllVerifier, Verifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def _iso_from_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ExchangeError(Exception):
    pass


class NotFoundError(ExchangeError):
    pass


@dataclass
class Exchange:
    exchange_id: str
    client: str
    provider: str
    resource_type: str
    quantity: int
    rule_id: str
    price: dict
    state: str
    idempotency_key: str
    created_at: str
    updated_at: str
    version: int = 0
    nonce: str = field(default_factory=V.new_nonce)
    timeouts: dict = field(default_factory=dict)
    deadline_ts: Optional[float] = None
    deadline_at: Optional[str] = None
    escrow_handle: Optional[str] = None
    deliverable: Any = None
    deliverable_ref: Optional[str] = None
    result_hash: Optional[str] = None
    vdc: Optional[dict] = None
    verify_result: Optional[dict] = None
    settlement_receipt: Optional[dict] = None
    settlement_intent: Optional[dict] = None
    settlement_terms: Optional[dict] = None
    settlement_binding: Optional[dict] = None
    dispute_info: Optional[dict] = None
    terms_hash: Optional[str] = None
    contract_acks: dict = field(default_factory=dict)
    trace_context: Optional[dict] = None


class ExchangeEngine:
    def __init__(
        self,
        settlement: SettlementAdapter,
        verifier: Optional[Verifier] = None,
        reputation=None,
        store=None,
        blob_store=None,
        rail_registry=None,
    ) -> None:
        self._store = store if store is not None else InMemoryStore()
        self._blobs = blob_store
        self._settlement = settlement
        self._rail_registry = rail_registry
        self._verifier: Verifier = verifier or AcceptAllVerifier()
        self._reputation = reputation

    def _adapter_for(self, ex: Exchange) -> SettlementAdapter:
        binding = ex.settlement_binding or {}
        rail_id = binding.get("rail")
        if self._rail_registry is not None and rail_id:
            return self._rail_registry.adapter_for_rail_id(str(rail_id))
        return self._settlement

    def _finalize_binding(self, ex: Exchange) -> None:
        if self._rail_registry is None:
            ex.settlement_binding = {
                "rail": getattr(self._settlement, "rail", "mock"),
                "chosen_at": "contract",
            }
            return
        from .rail_registry import SettlementBindingError, finalize_settlement_binding

        st = ex.settlement_terms or {}
        ex.settlement_binding = finalize_settlement_binding(
            settlement_terms=st,
            price=ex.price,
            node_rails=self._rail_registry.manifest_rails(),
            client_rails=st.get("client_rails"),
            provider_rails=st.get("provider_rails"),
        )

    def _assert_receipt_rail(self, ex: Exchange, receipt: dict) -> None:
        binding = ex.settlement_binding or {}
        expected = binding.get("rail")
        if not expected:
            return
        actual = receipt.get("rail")
        if actual and actual != expected:
            raise ExchangeError(
                f"settlement receipt rail 与 binding 不一致: {actual!r} != {expected!r}"
            )

    @staticmethod
    def _idem_key(client: str, idempotency_key: str) -> str:
        return f"{client}\x00{idempotency_key}"

    def get(self, exchange_id: str) -> Exchange:
        ex = self._store.get(exchange_id)
        if ex is None:
            raise NotFoundError(f"未知 exchange: {exchange_id}")
        return ex

    def find_vdc(self, vdc_id: str) -> Optional[dict]:
        if hasattr(self._store, "vdc_get"):
            vdc = self._store.vdc_get(vdc_id)
            if vdc is not None:
                return vdc
        for ex in self._store.values():
            if ex.vdc and ex.vdc.get("vdc_id") == vdc_id:
                return ex.vdc
        return None

    def get_deliverable(self, exchange_id: str) -> Any:
        ex = self.get(exchange_id)
        return self._load_deliverable(ex)

    def verify_deliverable_candidate(self, exchange_id: str, deliverable: Any) -> dict:
        """公开 hash 验证：无需读取存储的 blob，只需比对 candidate 与 result_hash。"""
        ex = self.get(exchange_id)
        if ex.result_hash is None:
            raise ExchangeError("交换尚无 result_hash")
        candidate = result_hash_of_json(deliverable)
        return {
            "matches": candidate == ex.result_hash,
            "result_hash": ex.result_hash,
            "candidate_hash": candidate,
        }

    def _store_deliverable(self, ex: Exchange, deliverable: Any) -> None:
        if self._blobs is not None:
            ex.deliverable_ref = self._blobs.put(ex.exchange_id, deliverable)
            ex.deliverable = None
        else:
            ex.deliverable = deliverable
            ex.deliverable_ref = inline_ref(ex.exchange_id)

    def _load_deliverable(self, ex: Exchange) -> Any:
        if ex.deliverable is not None:
            return ex.deliverable
        ref = ex.deliverable_ref
        if ref and is_stored_ref(ref) and self._blobs is not None:
            return self._blobs.get(ref)
        return ex.deliverable

    def _transition(self, ex: Exchange, dst: str) -> None:
        sm.assert_transition(ex.state, dst)
        ex.state = dst
        ex.version += 1
        ex.updated_at = _now_iso()

    def _set_deadline(self, ex: Exchange, phase: Optional[str]) -> None:
        """设置「当前所等待的下一动作」的截止时间。phase=None 表示清除（终态或交付后）。"""
        secs = ex.timeouts.get(phase) if phase else None
        if secs is None:
            ex.deadline_ts = None
            ex.deadline_at = None
        else:
            ex.deadline_ts = _now_ts() + secs
            ex.deadline_at = _iso_from_ts(ex.deadline_ts)

    def propose(
        self,
        *,
        client: str,
        provider: str,
        resource_type: str,
        quantity: int,
        rule_id: str,
        price: dict,
        idempotency_key: str,
        timeouts: Optional[dict] = None,
        settlement_terms: Optional[dict] = None,
        trace_context: Optional[dict] = None,
    ) -> Exchange:
        idem_key = self._idem_key(client, idempotency_key)
        existing = self._store.idem_get(idem_key)
        if existing is not None:
            return self.get(existing)

        now = _now_iso()
        ex = Exchange(
            exchange_id="ex-" + uuid.uuid4().hex,
            client=client,
            provider=provider,
            resource_type=resource_type,
            quantity=quantity,
            rule_id=rule_id,
            price=price,
            state=sm.PROPOSED,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
            timeouts=timeouts or {},
            settlement_terms=settlement_terms,
            trace_context=trace_context,
        )
        ex.terms_hash = terms_hash_from_exchange(ex)
        self._set_deadline(ex, "contract")
        self._store.add(ex)
        self._store.idem_set(idem_key, ex.exchange_id)
        return ex

    def contract(self, exchange_id: str, *, party: str, signature: str) -> Exchange:
        """条款双签：client 与 provider 各 ack 一次；双方齐后才 CONTRACTED。"""
        ex = self.get(exchange_id)
        if ex.state == sm.CONTRACTED:
            return ex
        if ex.state != sm.PROPOSED:
            sm.assert_transition(ex.state, sm.CONTRACTED)
        if party not in (ex.client, ex.provider):
            raise ExchangeError("contract 方必须是交换相关方")
        if party in ex.contract_acks:
            return ex
        if not ex.terms_hash:
            ex.terms_hash = terms_hash_from_exchange(ex)
        if not verify_contract_ack(party, signature, terms_hash=ex.terms_hash,
                                    exchange_id=ex.exchange_id):
            raise ExchangeError("contract 签名无效")
        ex.contract_acks[party] = {"signature": signature, "at": _now_iso()}
        if ex.client in ex.contract_acks and ex.provider in ex.contract_acks:
            if ex.settlement_binding is None:
                self._finalize_binding(ex)
            self._transition(ex, sm.CONTRACTED)
            self._set_deadline(ex, "escrow")
        else:
            ex.version += 1
            ex.updated_at = _now_iso()
        self._store.save(ex)
        return ex

    def escrow(self, exchange_id: str, *, amount: int, currency: str) -> Exchange:
        ex = self.get(exchange_id)
        if (amount, currency) != (ex.price["amount"], ex.price["currency"]):
            raise ExchangeError("escrow 金额/币种与条款不符")
        adapter = self._adapter_for(ex)
        handle = adapter.escrow(exchange_id, amount, currency)
        ex.escrow_handle = handle
        self._transition(ex, sm.ESCROWED)
        self._set_deadline(ex, "deliver")
        self._store.save(ex)
        return ex

    def deliver(
        self,
        exchange_id: str,
        provider_identity: Identity,
        deliverable: Any,
        *,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
        evidence_level: str = "dual_signed",
    ) -> Exchange:
        ex = self.get(exchange_id)
        if provider_identity.agent_id != ex.provider:
            raise ExchangeError("deliver 身份与 provider 不符")

        rh = result_hash_of_json(deliverable)
        doc = V.build_vdc(
            client=ex.client,
            provider=ex.provider,
            resource_type=ex.resource_type,
            quantity=ex.quantity,
            result_hash=rh,
            rule_id=ex.rule_id,
            evidence_level=evidence_level,
            started_at=started_at or _now_iso(),
            finished_at=finished_at or _now_iso(),
            idempotency_key=ex.idempotency_key,
            nonce=ex.nonce,
            state=sm.DELIVERED,
        )
        V.provider_sign(doc, provider_identity)

        self._store_deliverable(ex, deliverable)
        ex.result_hash = rh
        ex.vdc = doc
        self._transition(ex, sm.DELIVERED)
        self._set_deadline(ex, "verify")
        self._store.save(ex)
        return ex

    def ingest_delivery(self, exchange_id: str, *, vdc: dict, deliverable: Any) -> Exchange:
        """HTTP 路径：接收 provider 在本地构造并签名的 VDC，节点只做校验。

        私钥不出本地——节点从不持有 provider 私钥，仅验签 + 校验条款一致性。
        """
        ex = self.get(exchange_id)
        sm.assert_transition(ex.state, sm.DELIVERED)
        if vdc.get("state") != sm.DELIVERED:
            raise ExchangeError("VDC.state 必须为 DELIVERED")

        expected = {
            "client": ex.client,
            "provider": ex.provider,
            "resource_type": ex.resource_type,
            "quantity": ex.quantity,
            "rule_id": ex.rule_id,
            "nonce": ex.nonce,
            "idempotency_key": ex.idempotency_key,
        }
        actual = {
            "client": vdc["parties"]["client"],
            "provider": vdc["parties"]["provider"],
            "resource_type": vdc["resource_type"],
            "quantity": vdc["quantity"],
            "rule_id": vdc["rule_id"],
            "nonce": vdc.get("nonce"),
            "idempotency_key": vdc.get("idempotency_key"),
        }
        if actual != expected:
            raise ExchangeError("VDC 字段与 Exchange 条款不一致")

        rh = result_hash_of_json(deliverable)
        if vdc.get("result_hash") != rh:
            raise ExchangeError("result_hash 与 deliverable 不符")
        if not V.verify_provider(vdc):
            raise ExchangeError("provider_sig 验签失败")

        self._store_deliverable(ex, deliverable)
        ex.result_hash = rh
        ex.vdc = vdc
        self._transition(ex, sm.DELIVERED)
        self._set_deadline(ex, "verify")
        self._store.save(ex)
        return ex

    def ingest_confirmation(self, exchange_id: str, *, vdc: dict) -> Exchange:
        """HTTP 路径：接收 client 在本地补签的双签 VDC，节点只做校验后结算。"""
        ex = self.get(exchange_id)
        sm.assert_transition(ex.state, sm.SETTLED)
        if ex.vdc is None or vdc.get("vdc_id") != ex.vdc.get("vdc_id"):
            raise ExchangeError("vdc_id 与本地交付记录不一致")
        if not V.verify_provider(vdc):
            raise ExchangeError("provider_sig 验签失败")
        if not V.verify_client(vdc):
            raise ExchangeError("client_sig 验签失败")

        vdc["state"] = sm.SETTLED
        ex.vdc = vdc
        self._settle_with_capture(ex, "settle")
        self._transition(ex, sm.SETTLED)
        self._set_deadline(ex, None)
        self._store.save(ex)
        if self._reputation:
            self._reputation.record_settlement(ex)
        return ex

    def _enrich_verify_result(self, result: dict, ex: Exchange,
                              rule: Optional[dict]) -> dict:
        """补充 replay_inputs_ref：第三方凭此定位 deliverable + rule 独立复跑验收。"""
        rid = (rule or {}).get("rule_id") or ex.rule_id
        out = dict(result)
        out["replay_inputs_ref"] = {
            "kind": "inline",
            "exchange_id": ex.exchange_id,
            "rule_id": rid,
            "deliverable_ref": ex.deliverable_ref or inline_ref(ex.exchange_id),
        }
        if rule and "schema" in rule:
            out["replay_inputs_ref"]["schema_inline"] = rule["schema"]
        return out

    def verify(self, exchange_id: str, *, rule: Optional[dict] = None) -> Exchange:
        ex = self.get(exchange_id)
        # 先确保状态合法（VERIFIED/REJECTED 均只能从 DELIVERED 进入），再做任何副作用
        sm.assert_transition(ex.state, sm.VERIFIED)
        deliverable = self._load_deliverable(ex)
        result = self._verifier.verify(deliverable, rule)
        result = self._enrich_verify_result(result, ex, rule)
        ex.verify_result = result
        if result.get("passed"):
            self._transition(ex, sm.VERIFIED)
            self._set_deadline(ex, "confirm")
            self._store.save(ex)
        else:
            self._refund_if_held(ex)
            self._transition(ex, sm.REJECTED)
            self._set_deadline(ex, None)
            self._store.save(ex)
            if self._reputation:
                self._reputation.record_outcome(
                    ex, agent_id=ex.provider, role="provider", outcome="rejected"
                )
        return ex

    def confirm(self, exchange_id: str, client_identity: Identity) -> Exchange:
        ex = self.get(exchange_id)
        if client_identity.agent_id != ex.client:
            raise ExchangeError("confirm 身份与 client 不符")
        if ex.vdc is None:
            raise ExchangeError("缺少 VDC，无法 confirm")

        V.client_sign(ex.vdc, client_identity)
        ex.vdc["state"] = sm.SETTLED
        self._settle_with_capture(ex, "settle")
        self._transition(ex, sm.SETTLED)
        self._set_deadline(ex, None)
        self._store.save(ex)
        if self._reputation:
            self._reputation.record_settlement(ex)
        return ex

    def dispute(self, exchange_id: str, *, by: str, reason: str) -> Exchange:
        """从 VERIFIED 进入 DISPUTED：任一方对验收结果存疑时开启争议。"""
        ex = self.get(exchange_id)
        sm.assert_transition(ex.state, sm.DISPUTED)
        if by not in (ex.client, ex.provider):
            raise ExchangeError("发起争议者必须是交换相关方")
        ex.dispute_info = {"by": by, "reason": reason, "opened_at": _now_iso(),
                           "resolution": None}
        self._transition(ex, sm.DISPUTED)
        self._store.save(ex)
        return ex

    def resolve(self, exchange_id: str, *, outcome: str,
                resolver: Optional[str] = None, note: Optional[str] = None) -> Exchange:
        """仲裁裁决：outcome='settle'（结算给 provider）或 'reject'（退款给 client）。

        v0 由仲裁权威裁决，非客户同意——故 settle 分支产出的 VDC 仅 provider 单签，
        结算依据是争议裁决而非双签。
        """
        if outcome not in ("settle", "reject"):
            raise ExchangeError("outcome 必须为 settle 或 reject")
        ex = self.get(exchange_id)
        target = sm.SETTLED if outcome == "settle" else sm.REJECTED
        sm.assert_transition(ex.state, target)
        if outcome == "settle":
            self._settle_with_capture(ex, "settle")
            self._transition(ex, sm.SETTLED)
        else:
            self._refund_if_held(ex)
            self._transition(ex, sm.REJECTED)
        ex.dispute_info = {**(ex.dispute_info or {}), "resolution": outcome,
                           "resolver": resolver, "note": note, "resolved_at": _now_iso()}
        self._set_deadline(ex, None)
        self._store.save(ex)
        if self._reputation:
            if outcome == "settle":
                self._reputation.record_settlement(ex)
            else:
                self._reputation.record_outcome(
                    ex, agent_id=ex.provider, role="provider", outcome="rejected"
                )
        return ex

    def cancel(self, exchange_id: str) -> Exchange:
        ex = self.get(exchange_id)
        sm.assert_transition(ex.state, sm.CANCELLED)  # 先校验，避免"退款后才发现非法"
        self._refund_if_held(ex)
        self._transition(ex, sm.CANCELLED)
        self._set_deadline(ex, None)
        self._store.save(ex)
        return ex

    def expire(self, exchange_id: str) -> Exchange:
        ex = self.get(exchange_id)
        sm.assert_transition(ex.state, sm.EXPIRED_REFUNDED)  # 同上，先校验后退款
        self._refund_if_held(ex)
        self._transition(ex, sm.EXPIRED_REFUNDED)
        self._set_deadline(ex, None)
        self._store.save(ex)
        return ex

    def _capture_intent(self, ex: Exchange, intent: dict) -> None:
        """capture-before-execute：在调用外部结算之前，先把意图落盘。

        若进程在外部调用与最终落盘之间崩溃，持久化记录会留下 pending 意图，
        recover() 可据此幂等地重放结算，避免"钱动了但状态没落盘"的不一致。
        """
        ex.settlement_intent = intent
        ex.version += 1
        ex.updated_at = _now_iso()
        self._store.save(ex)

    def _settle_with_capture(self, ex: Exchange, action: str) -> None:
        if not ex.escrow_handle or ex.settlement_receipt is not None:
            return
        handle = ex.escrow_handle
        self._capture_intent(ex, {"action": action, "handle": handle, "status": "pending"})
        adapter = self._adapter_for(ex)
        fn = adapter.settle if action == "settle" else adapter.refund
        receipt = fn(handle)  # 幂等
        self._assert_receipt_rail(ex, receipt)
        ex.settlement_receipt = receipt
        ex.settlement_intent = {"action": action, "handle": handle, "status": "done"}

    def _refund_if_held(self, ex: Exchange) -> None:
        self._settle_with_capture(ex, "refund")

    def recover(self) -> list[Exchange]:
        """崩溃恢复：重放所有 pending 结算意图（幂等），并补齐未完成的终态。

        适配器失败时 MUST NOT 假推进 SETTLED；intent 保持 pending 并记 last_error。
        """
        from .settlement import SettlementError

        recovered: list[Exchange] = []
        for ex in self._store.values():
            intent = ex.settlement_intent
            if not intent or intent.get("status") != "pending":
                continue
            action, handle = intent["action"], intent["handle"]
            adapter = self._adapter_for(ex)
            fn = adapter.settle if action == "settle" else adapter.refund
            try:
                receipt = fn(handle)
                self._assert_receipt_rail(ex, receipt)
                ex.settlement_receipt = receipt
            except SettlementError as exc:
                ex.settlement_intent = {
                    **intent,
                    "status": "pending",
                    "last_error": str(exc),
                }
                ex.version += 1
                ex.updated_at = _now_iso()
                self._store.save(ex)
                continue
            ex.settlement_intent = {**intent, "status": "done"}
            target = sm.SETTLED if action == "settle" else sm.EXPIRED_REFUNDED
            if ex.state not in sm.TERMINAL_STATES and sm.can_transition(ex.state, target):
                self._transition(ex, target)
                self._set_deadline(ex, None)
            else:
                ex.version += 1
                ex.updated_at = _now_iso()
            self._store.save(ex)
            recovered.append(ex)
        return recovered

    def sweep(self, *, now_ts: Optional[float] = None) -> list[Exchange]:
        """超时清扫：交付前阶段 / DELIVERED(verify) / VERIFIED(confirm) -> EXPIRED_REFUNDED。"""
        now = now_ts if now_ts is not None else _now_ts()
        expired: list[Exchange] = []
        for ex in list(self._store.values()):
            if ex.state in sm.TERMINAL_STATES:
                continue
            if ex.deadline_ts is None or now < ex.deadline_ts:
                continue
            if sm.can_transition(ex.state, sm.EXPIRED_REFUNDED):
                self.expire(ex.exchange_id)
                expired.append(ex)
        return expired

    def validate_witness_v2(self, attestation: dict) -> dict:
        """v2 占位：校验见证声明 schema + 签名，不写入 VDC。"""
        from .v2.witness import validate_witness_attestation

        errors = validate_witness_attestation(attestation)
        return {"valid": len(errors) == 0, "errors": errors}

    def validate_stake_v2(self, stake: dict) -> dict:
        from .v2.witness import validate_stake_lock

        errors = validate_stake_lock(stake)
        return {"valid": len(errors) == 0, "errors": errors}

    def attach_witness_v2(
        self,
        exchange_id: str,
        attestation: dict,
        *,
        require_stake: bool = False,
    ) -> Exchange:
        """v2：将见证挂到 VDC（可选要求 witness 已 lock stake）。"""
        from .v2.stake import find_locked_stake
        from .v2.witness import (
            WITNESS_V2_ENABLED,
            WitnessV2NotEnabledError,
            attach_witness_to_vdc,
            validate_witness_attestation,
        )

        if not WITNESS_V2_ENABLED:
            raise WitnessV2NotEnabledError("witness v2 未启用")
        errors = validate_witness_attestation(attestation)
        if errors:
            raise ExchangeError("; ".join(errors))
        ex = self.get(exchange_id)
        if ex.vdc is None:
            raise ExchangeError("交换尚无 VDC")
        witness_id = attestation.get("witness_id")
        if require_stake and witness_id:
            stake = find_locked_stake(agent_id=witness_id, exchange_id=exchange_id)
            if stake is None:
                raise ExchangeError("witness 须先 lock stake 才能 attach")
        ex.vdc = attach_witness_to_vdc(ex.vdc, attestation)
        self._store.save(ex)
        return ex

    def slash_stake_v2(self, stake: dict, *, reason: str, slashed_by: str) -> dict:
        from .v2.witness import WitnessV2NotEnabledError, WITNESS_V2_ENABLED, slash_stake

        if not WITNESS_V2_ENABLED:
            raise WitnessV2NotEnabledError("stake v2 未启用")
        return slash_stake(stake, reason=reason, slashed_by=slashed_by)

    def lock_stake_v2(
        self,
        *,
        agent_id: str,
        amount: int,
        currency: str,
        purpose: str,
        exchange_id: Optional[str] = None,
        vdc_id: Optional[str] = None,
    ) -> dict:
        from .v2.stake import lock_stake

        return lock_stake(
            agent_id=agent_id,
            amount=amount,
            currency=currency,
            purpose=purpose,
            exchange_id=exchange_id,
            vdc_id=vdc_id,
        )

    def export_exchange(self, exchange_id: str, *, include_deliverable: bool = False) -> dict:
        """可携带导出包：供联邦/自托管迁移；deliverable 仅 include_deliverable 时含正文。"""
        ex = self.get(exchange_id)
        payload = {
            "export_version": "0.1",
            "exported_at": _now_iso(),
            "exchange_id": ex.exchange_id,
            "state": ex.state,
            "client": ex.client,
            "provider": ex.provider,
            "resource_type": ex.resource_type,
            "quantity": ex.quantity,
            "rule_id": ex.rule_id,
            "price": ex.price,
            "result_hash": ex.result_hash,
            "deliverable_ref": ex.deliverable_ref,
            "vdc": ex.vdc,
            "verify_result": ex.verify_result,
            "settlement_receipt": ex.settlement_receipt,
            "settlement_terms": ex.settlement_terms,
            "settlement_binding": ex.settlement_binding,
            "terms_hash": ex.terms_hash,
        }
        if include_deliverable:
            try:
                payload["deliverable"] = self._load_deliverable(ex)
            except (KeyError, NotFoundError):
                payload["deliverable"] = None
        return payload
