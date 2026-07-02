"""见证网络 + 质押罚没 v2 占位（schema + 校验 + 引擎 stub）。

v2 目标（架构层）：第三方见证背书、质押锁定与罚没，缓解恶意验收者与女巫攻击。
v0 参考实现不执行链上/资金侧效果，仅定义结构与校验，供 plugfest/一致性测试预埋。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from ..identity import Identity, verify as _verify_sig

WITNESS_V2_VERSION = "0.2-placeholder"
STAKE_V2_VERSION = "0.2-placeholder"
WITNESS_V2_ENABLED = False

EVIDENCE_LEVELS_V2 = ("third_party_witnessed",)


class WitnessV2NotEnabledError(Exception):
    """v2 见证/质押运行时未启用。"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_witness_attestation(
    *,
    vdc_id: str,
    witness: Identity,
    claim: str,
    vdc_result_hash: str,
    stake_ref: Optional[str] = None,
) -> dict:
    """构造见证声明（未签名）。claim 为见证人对交付事实的简短断言。"""
    doc: dict[str, Any] = {
        "witness_version": WITNESS_V2_VERSION,
        "vdc_id": vdc_id,
        "witness_id": witness.agent_id,
        "vdc_result_hash": vdc_result_hash,
        "claim": claim,
        "stake_ref": stake_ref,
        "signed_at": _now_iso(),
        "signature": "",
    }
    return doc


def witness_signing_bytes(doc: dict) -> bytes:
    from ..canonical import canonical_bytes

    payload = {k: v for k, v in doc.items() if k != "signature"}
    return canonical_bytes(payload)


def witness_sign(doc: dict, witness: Identity) -> dict:
    if doc["witness_id"] != witness.agent_id:
        raise ValueError("witness 身份不匹配")
    doc["signature"] = witness.sign(witness_signing_bytes(doc))
    return doc


def validate_witness_attestation(doc: dict) -> list[str]:
    """轻量 schema 校验；返回错误列表（空=通过）。"""
    errors: list[str] = []
    required = (
        "witness_version", "vdc_id", "witness_id", "vdc_result_hash",
        "claim", "signed_at", "signature",
    )
    for k in required:
        if not doc.get(k):
            errors.append(f"缺少字段: {k}")
    if doc.get("witness_version") != WITNESS_V2_VERSION:
        errors.append("witness_version 不匹配")
    wh = doc.get("vdc_result_hash", "")
    if not (isinstance(wh, str) and wh.startswith("sha256:") and len(wh) == 71):
        errors.append("vdc_result_hash 格式无效")
    sig = doc.get("signature", "")
    if sig and not _verify_sig(doc.get("witness_id", ""), sig, witness_signing_bytes(doc)):
        errors.append("signature 验签失败")
    return errors


def build_stake_lock(
    *,
    agent_id: str,
    amount: int,
    currency: str,
    purpose: str,
    exchange_id: Optional[str] = None,
    vdc_id: Optional[str] = None,
) -> dict:
    """构造质押锁定意图（占位；不触达真实资金）。"""
    return {
        "stake_version": STAKE_V2_VERSION,
        "stake_id": f"stake-{agent_id[-8:]}-{int(datetime.now(timezone.utc).timestamp())}",
        "agent_id": agent_id,
        "amount": amount,
        "currency": currency,
        "purpose": purpose,
        "exchange_id": exchange_id,
        "vdc_id": vdc_id,
        "status": "locked",
        "locked_at": _now_iso(),
    }


def validate_stake_lock(doc: dict) -> list[str]:
    errors: list[str] = []
    required = (
        "stake_version", "stake_id", "agent_id", "amount", "currency",
        "purpose", "status", "locked_at",
    )
    for k in required:
        if doc.get(k) in (None, ""):
            errors.append(f"缺少字段: {k}")
    if doc.get("stake_version") != STAKE_V2_VERSION:
        errors.append("stake_version 不匹配")
    if doc.get("status") not in ("locked", "released", "slashed"):
        errors.append("status 无效")
    amt = doc.get("amount")
    if not isinstance(amt, int) or amt < 0:
        errors.append("amount 须为非负整数")
    return errors


def attach_witness_to_vdc(vdc: dict, attestation: dict) -> dict:
    """将见证声明挂到 VDC evidence（v2 占位；默认禁用）。"""
    if not WITNESS_V2_ENABLED:
        raise WitnessV2NotEnabledError("witness v2 未启用")
    errs = validate_witness_attestation(attestation)
    if errs:
        raise ValueError("; ".join(errs))
    if attestation["vdc_id"] != vdc.get("vdc_id"):
        raise ValueError("vdc_id 不一致")
    if attestation["vdc_result_hash"] != vdc.get("result_hash"):
        raise ValueError("result_hash 不一致")
    evidence = dict(vdc.get("evidence") or {})
    witnesses = list(evidence.get("witnesses") or [])
    witnesses.append(attestation)
    evidence["witnesses"] = witnesses
    evidence["level"] = "third_party_witnessed"
    vdc["evidence"] = evidence
    return vdc


def slash_stake(stake: dict, *, reason: str, slashed_by: str) -> dict:
    """质押罚没（不触达真实资金）。"""
    if not WITNESS_V2_ENABLED:
        raise WitnessV2NotEnabledError("stake v2 未启用")
    from .stake import slash_stake_record

    return slash_stake_record(stake, reason=reason, slashed_by=slashed_by)
