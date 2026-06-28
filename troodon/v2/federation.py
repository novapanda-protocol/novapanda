"""跨节点联邦 v2 占位（信誉携带 / 导入校验）。

v0 参考实现支持：导出 bundle、独立校验外链信誉链；导入合并默认关闭。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from ..canonical import canonical_bytes
from ..hashing import sha256_hex
from ..identity import verify as _verify_sig

BUNDLE_VERSION = "0.2-placeholder"
FEDERATION_V2_ENABLED = False


class FederationV2NotEnabledError(Exception):
    """联邦 v2 导入运行时未启用。"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _entry_hash(core: dict) -> str:
    return "sha256:" + sha256_hex(canonical_bytes(core))


def build_reputation_bundle(
    *,
    source_node_id: str,
    entries: list[dict],
    agent_id: Optional[str] = None,
) -> dict:
    """从节点信誉日志构造可携带 bundle（只读快照，不含私钥）。"""
    if agent_id is not None:
        entries = [e for e in entries if e.get("agent_id") == agent_id]
    return {
        "bundle_version": BUNDLE_VERSION,
        "source_node_id": source_node_id,
        "agent_filter": agent_id,
        "exported_at": _now_iso(),
        "entry_count": len(entries),
        "entries": list(entries),
    }


def verify_reputation_chain(entries: list[dict], *, genesis: str = "GENESIS") -> dict:
    """独立复验外链信誉链（不写入本地库）。"""
    prev_hash = genesis
    ok = True
    errors: list[str] = []
    for i, entry in enumerate(entries):
        if entry.get("seq") != i:
            ok = False
            errors.append(f"seq 不连续: 期望 {i} 得 {entry.get('seq')}")
        if entry.get("prev_hash") != prev_hash:
            ok = False
            errors.append(f"prev_hash 断链于 seq={i}")
        core = {k: v for k, v in entry.items() if k not in ("entry_hash", "signature")}
        if _entry_hash(core) != entry.get("entry_hash"):
            ok = False
            errors.append(f"entry_hash 不匹配 seq={i}")
        sig = entry.get("signature", "")
        node_id = entry.get("node_id", "")
        if not sig or not _verify_sig(node_id, sig, canonical_bytes(core)):
            ok = False
            errors.append(f"节点签名无效 seq={i}")
        prev_hash = entry.get("entry_hash", prev_hash)
    return {"valid": ok and not errors, "errors": errors, "entry_count": len(entries)}


def validate_reputation_bundle(bundle: dict) -> list[str]:
    errors: list[str] = []
    if bundle.get("bundle_version") != BUNDLE_VERSION:
        errors.append("bundle_version 不匹配")
    if not bundle.get("source_node_id"):
        errors.append("缺少 source_node_id")
    entries = bundle.get("entries")
    if not isinstance(entries, list):
        errors.append("entries 必须为数组")
        return errors
    if entries and entries[0].get("node_id") != bundle.get("source_node_id"):
        errors.append("entries[0].node_id 与 source_node_id 不一致")
    result = verify_reputation_chain(entries)
    if not result["valid"]:
        errors.extend(result["errors"])
    return errors


def import_reputation_bundle(reputation_log, bundle: dict) -> list[dict]:
    """将外链 bundle 合并进本地账本（mirror 条目 + 本地链延续）。"""
    if not FEDERATION_V2_ENABLED:
        raise FederationV2NotEnabledError("联邦信誉导入 v2 未启用")
    errors = validate_reputation_bundle(bundle)
    if errors:
        raise ValueError("; ".join(errors))
    source = bundle["source_node_id"]
    imported: list[dict] = []
    seen = {
        (e.get("external_ref") or {}).get("source_entry_hash", e["entry_hash"])
        for e in reputation_log._store.all()
        if e.get("import_kind") == "mirror"
    }
    seen.update(e["entry_hash"] for e in reputation_log._store.all() if not e.get("import_kind"))
    for entry in bundle["entries"]:
        if entry["entry_hash"] in seen:
            continue
        mirror = reputation_log.append_imported(entry, source_node_id=source)
        imported.append(mirror)
        seen.add(entry["entry_hash"])
    return imported
