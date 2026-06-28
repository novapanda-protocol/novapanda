"""Agent Manifest：能力发现与自签名 manifest（`/.well-known/troodon.json`）。

Agent 在本地持有私钥并自签 manifest；对端拉取后验签即可发现能力与交换端点，
无需预建关系。
"""

from __future__ import annotations

from typing import Optional

from .canonical import canonical_bytes
from .identity import Identity, verify
from .v1.did import agent_id_to_did, did_to_agent_id


def build_agent_manifest(
    identity: Identity,
    *,
    capabilities: list[dict],
    exchange_endpoint: str,
    transport: Optional[list[str]] = None,
    version: str = "0.0.1",
    include_did: bool = True,
) -> dict:
    body = {
        "protocol": "troodon",
        "version": version,
        "agent_id": identity.agent_id,
        "pubkey": identity.pubkey_b64url,
        "capabilities": capabilities,
        "endpoints": {
            "exchange": exchange_endpoint,
            "transport": transport or ["http"],
        },
    }
    if include_did:
        body["did"] = agent_id_to_did(identity.agent_id)
    body["sig"] = identity.sign(canonical_bytes({k: v for k, v in body.items()}))
    return body


def manifest_signing_bytes(manifest: dict) -> bytes:
    unsigned = {k: v for k, v in manifest.items() if k != "sig"}
    return canonical_bytes(unsigned)


def verify_agent_manifest(manifest: dict) -> bool:
    sig = manifest.get("sig")
    if not sig:
        return False
    agent_id = manifest.get("agent_id")
    if not agent_id:
        return False
    if not verify(agent_id, sig, manifest_signing_bytes(manifest)):
        return False
    did = manifest.get("did")
    if did:
        try:
            if did_to_agent_id(did) != agent_id:
                return False
        except ValueError:
            return False
    return True


def manifest_agent_id(manifest: dict) -> str:
    """从 manifest 解析权威 agent_id（优先 did）。"""
    did = manifest.get("did")
    if did:
        return did_to_agent_id(did)
    aid = manifest.get("agent_id")
    if not aid:
        raise ValueError("manifest 缺少 agent_id")
    return aid
