"""Agent 密钥轮换 v1 占位（接口预留 + 旧钥验签）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .canonical import canonical_bytes
from .identity import Identity, verify as _verify_sig, verify_pubkey_b64url

KEY_HISTORY_VERSION = "0.1-placeholder"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_key_history(
    identity: Identity,
    *,
    previous_keys: list[dict] | None = None,
    effective_from: str | None = None,
) -> dict:
    """构造可发布的密钥历史文档（自签）。"""
    doc: dict[str, Any] = {
        "key_history_version": KEY_HISTORY_VERSION,
        "agent_id": identity.agent_id,
        "current_pubkey": identity.pubkey_b64url,
        "previous_keys": previous_keys or [],
        "effective_from": effective_from or _now_iso(),
        "published_at": _now_iso(),
        "signature": "",
    }
    payload = {k: v for k, v in doc.items() if k != "signature"}
    doc["signature"] = identity.sign(canonical_bytes(payload))
    return doc


def validate_key_history(doc: dict) -> list[str]:
    errors: list[str] = []
    required = (
        "key_history_version", "agent_id", "current_pubkey",
        "previous_keys", "effective_from", "published_at", "signature",
    )
    for k in required:
        if doc.get(k) in (None, ""):
            errors.append(f"缺少字段: {k}")
    if doc.get("key_history_version") != KEY_HISTORY_VERSION:
        errors.append("key_history_version 不匹配")
    prev = doc.get("previous_keys")
    if not isinstance(prev, list):
        errors.append("previous_keys 必须为数组")
    else:
        for i, item in enumerate(prev):
            if not isinstance(item, dict) or not item.get("pubkey"):
                errors.append(f"previous_keys[{i}] 缺少 pubkey")
    sig = doc.get("signature", "")
    if sig:
        payload = {k: v for k, v in doc.items() if k != "signature"}
        if not _verify_sig(doc.get("agent_id", ""), sig, canonical_bytes(payload)):
            errors.append("signature 验签失败")
    return errors


def verify_with_key_history(
    agent_id: str,
    signature: str,
    message: bytes,
    key_history: dict | None = None,
) -> bool:
    """验签：当前 agent_id 公钥失败时，尝试 key_history 中的 previous_keys。"""
    if _verify_sig(agent_id, signature, message):
        return True
    if key_history is None:
        return False
    if validate_key_history(key_history):
        return False
    if key_history.get("agent_id") != agent_id:
        return False
    if verify_pubkey_b64url(key_history["current_pubkey"], signature, message):
        return True
    for item in key_history.get("previous_keys") or []:
        if verify_pubkey_b64url(item["pubkey"], signature, message):
            return True
    return False
