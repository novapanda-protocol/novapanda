"""VDC（可验证交割凭证）的构造、签名与复验。

签名范围（重要）：
- `state` 是生命周期标记，由交换/节点驱动，会随 DELIVERED→SETTLED 变化，
  因此**不进签名**——否则状态一变 provider_sig 就失效。
- `provider_sig` = Ed25519 over canonical(VDC 去掉 signatures、state)  —— B 对交付事实的声明。
- `client_sig`   = Ed25519 over canonical(VDC 去掉 state、signatures.client_sig) —— A 认可 B 的声明（含 provider_sig）。

任何第三方只需 VDC + 双方 agent_id 即可复验，无需信任任何节点。
"""

from __future__ import annotations

import copy
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .canonical import canonical_bytes
from .identity import Identity, verify as _verify_sig

VDC_VERSION = "0.1"
EVIDENCE_LEVELS = ("self_reported", "dual_signed", "metered", "third_party_witnessed")
PROVIDER_PAYLOAD_ENCODINGS = ("json", "cbor")
_VOLATILE_FIELDS = ("state",)  # 不进签名的生命周期字段


def new_id() -> str:
    # v0 用 uuid4；后续可替换为 ULID（保持字段语义不变）。
    return uuid.uuid4().hex


def new_nonce() -> str:
    return secrets.token_hex(16)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_vdc(
    *,
    client: str,
    provider: str,
    resource_type: str,
    quantity: int,
    result_hash: str,
    rule_id: str,
    evidence_level: str,
    started_at: str,
    finished_at: str,
    idempotency_key: str,
    nonce: Optional[str] = None,
    state: str = "DELIVERED",
    prev_hash: str = "GENESIS",
    metering: Optional[dict] = None,
) -> dict:
    if evidence_level not in EVIDENCE_LEVELS:
        raise ValueError(f"未知 evidence_level: {evidence_level}")
    evidence: dict[str, Any] = {
        "level": evidence_level,
        "started_at": started_at,
        "finished_at": finished_at,
    }
    if metering is not None:
        evidence["metering"] = metering
    return {
        "vdc_version": VDC_VERSION,
        "vdc_id": new_id(),
        "parties": {"client": client, "provider": provider},
        "resource_type": resource_type,
        "quantity": quantity,
        "result_hash": result_hash,
        "rule_id": rule_id,
        "evidence": evidence,
        "state": state,
        "idempotency_key": idempotency_key,
        "nonce": nonce or new_nonce(),
        "prev_hash": prev_hash,
        "created_at": now_iso(),
        "signatures": {},
    }


def _strip_volatile(v: dict) -> dict:
    for field in _VOLATILE_FIELDS:
        v.pop(field, None)
    return v


def provider_signing_payload(vdc: dict) -> dict:
    """可签名 VDC 载荷（去 signatures + state）。"""
    v = copy.deepcopy(vdc)
    v.pop("signatures", None)
    return _strip_volatile(v)


def provider_signing_bytes(vdc: dict) -> bytes:
    return canonical_bytes(provider_signing_payload(vdc))


def provider_signing_cbor_bytes(vdc: dict) -> bytes:
    """VDC provider 签名域 CBOR canonical（v2 双轨）。"""
    from .v1.cbor_codec import canonical_cbor_bytes

    return canonical_cbor_bytes(provider_signing_payload(vdc))


def provider_payload_encoding(vdc: dict) -> str:
    enc = vdc.get("signatures", {}).get("provider_payload_encoding", "json")
    return enc if enc in PROVIDER_PAYLOAD_ENCODINGS else "json"


def provider_payload_bytes(vdc: dict, *, encoding: Optional[str] = None) -> bytes:
    enc = encoding or provider_payload_encoding(vdc)
    if enc == "cbor":
        return provider_signing_cbor_bytes(vdc)
    if enc == "json":
        return provider_signing_bytes(vdc)
    raise ValueError(f"未知 provider_payload_encoding: {enc}")


def client_signing_bytes(vdc: dict) -> bytes:
    v = copy.deepcopy(vdc)
    _strip_volatile(v)
    sigs = dict(v.get("signatures", {}))
    sigs.pop("client_sig", None)
    v["signatures"] = sigs
    return canonical_bytes(v)


def provider_sign(vdc: dict, identity: Identity, *, encoding: str = "json") -> dict:
    if encoding not in PROVIDER_PAYLOAD_ENCODINGS:
        raise ValueError(f"未知 encoding: {encoding}")
    if vdc["parties"]["provider"] != identity.agent_id:
        raise ValueError("provider 身份与 VDC 不匹配")
    sigs = vdc.setdefault("signatures", {})
    sigs["provider_payload_encoding"] = encoding
    sigs["provider_sig"] = identity.sign(provider_payload_bytes(vdc, encoding=encoding))
    return vdc


def client_sign(vdc: dict, identity: Identity) -> dict:
    if vdc["parties"]["client"] != identity.agent_id:
        raise ValueError("client 身份与 VDC 不匹配")
    if "provider_sig" not in vdc.get("signatures", {}):
        raise ValueError("缺少 provider_sig，client 不能先于 provider 签名")
    vdc["signatures"]["client_sig"] = identity.sign(client_signing_bytes(vdc))
    return vdc


def verify_provider(vdc: dict) -> bool:
    sig = vdc.get("signatures", {}).get("provider_sig")
    if not sig:
        return False
    return _verify_sig(
        vdc["parties"]["provider"],
        sig,
        provider_payload_bytes(vdc),
    )


def verify_client(vdc: dict) -> bool:
    sig = vdc.get("signatures", {}).get("client_sig")
    if not sig:
        return False
    return _verify_sig(vdc["parties"]["client"], sig, client_signing_bytes(vdc))


def is_valid_settled(vdc: dict) -> bool:
    """终态有效交割：状态为 SETTLED 且双签均验签通过。"""
    return (
        vdc.get("state") == "SETTLED"
        and verify_provider(vdc)
        and verify_client(vdc)
    )
