"""DID 占位：did:novapanda:<agent_id> 与 agent_id 双向映射。"""

from __future__ import annotations

from typing import Any, Optional

from ..identity import Identity, verify as _verify_sig
from ..canonical import canonical_bytes

DID_METHOD = "novapanda"
DID_VERSION = "0.1-placeholder"


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def agent_id_to_did(agent_id: str) -> str:
    if not agent_id.startswith("ed25519:"):
        raise ValueError("agent_id 格式无效")
    return f"did:{DID_METHOD}:{agent_id}"


def did_to_agent_id(did: str) -> str:
    prefix = f"did:{DID_METHOD}:"
    if not did.startswith(prefix):
        raise ValueError(f"非 novapanda DID: {did}")
    agent_id = did[len(prefix):]
    if not agent_id.startswith("ed25519:"):
        raise ValueError("DID 内 agent_id 格式无效")
    return agent_id


def is_novapanda_did(ref: str) -> bool:
    return ref.startswith(f"did:{DID_METHOD}:")


def normalize_party_ref(ref: str, registry=None) -> str:
    """将 agent_id 或 did:novapanda:... 规范化为 agent_id。"""
    if is_novapanda_did(ref):
        if registry is not None:
            return registry.resolve(ref)["agent_id"]
        return did_to_agent_id(ref)
    if not ref.startswith("ed25519:"):
        raise ValueError("party 须为 ed25519: agent_id 或 did:novapanda:...")
    return ref


def resolve_did_public_key(did: str, registry=None) -> Optional[str]:
    if registry is None:
        return None
    doc = registry.get(did)
    if doc is None:
        return None
    vms = doc.get("verificationMethod") or []
    if not vms:
        return None
    return vms[0].get("publicKeyBase64url")


def build_did_document(
    identity: Identity,
    *,
    services: Optional[list[dict]] = None,
) -> dict:
    doc: dict[str, Any] = {
        "did_version": DID_VERSION,
        "id": agent_id_to_did(identity.agent_id),
        "verificationMethod": [{
            "id": f"{agent_id_to_did(identity.agent_id)}#key-1",
            "type": "Ed25519VerificationKey2020",
            "controller": agent_id_to_did(identity.agent_id),
            "publicKeyMultibase": None,
            "publicKeyBase64url": identity.pubkey_b64url,
        }],
        "service": services or [],
        "published_at": _now_iso(),
        "signature": "",
    }
    payload = {k: v for k, v in doc.items() if k != "signature"}
    doc["signature"] = identity.sign(canonical_bytes(payload))
    return doc


def validate_did_document(doc: dict) -> list[str]:
    errors: list[str] = []
    if doc.get("did_version") != DID_VERSION:
        errors.append("did_version 不匹配")
    did = doc.get("id")
    if not isinstance(did, str) or not did.startswith(f"did:{DID_METHOD}:"):
        errors.append("id 无效")
    else:
        try:
            did_to_agent_id(did)
        except ValueError as exc:
            errors.append(str(exc))
    vms = doc.get("verificationMethod")
    if not isinstance(vms, list) or not vms:
        errors.append("verificationMethod 必填")
    sig = doc.get("signature", "")
    if sig and did:
        try:
            agent_id = did_to_agent_id(did)
            payload = {k: v for k, v in doc.items() if k != "signature"}
            if not _verify_sig(agent_id, sig, canonical_bytes(payload)):
                errors.append("signature 验签失败")
        except ValueError:
            pass
    return errors
