"""仲裁 / 分享导出包：JSON 为真源；PDF 仅展示壳（本模块不生成 PDF）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from ..canonical import canonical_bytes
from ..hashing import sha256_hex
from ..reverify import _all_ok, reverify
from .types import VaultEntry


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_arbitration_package(
    entry: VaultEntry,
    *,
    include_deliverable: bool = True,
    run_reverify: bool = True,
) -> dict[str, Any]:
    pkg: dict[str, Any] = {
        "export_version": "adopter-arb-1",
        "exported_at": _now(),
        "exchange_id": entry.exchange_id,
        "vdc_id": entry.vdc_id,
        "vdc": entry.vdc,
        "vdc_fingerprint": "sha256:" + sha256_hex(canonical_bytes(entry.vdc)),
        "meta": {
            "role": entry.role,
            "peer_id": entry.peer_id,
            "source": entry.source,
            "stored_at": entry.stored_at,
        },
    }
    deliverable = entry.deliverable if include_deliverable else None
    if deliverable is not None:
        pkg["deliverable"] = deliverable
    if run_reverify and deliverable is not None:
        pkg["reverify"] = reverify(entry.vdc, deliverable)
    elif run_reverify:
        pkg["reverify"] = reverify(entry.vdc, None)
    return pkg


def package_summary_text(pkg: dict[str, Any]) -> str:
    """给人看的摘要（可喂给 PDF 壳）；验签仍以 JSON 为准。"""
    vdc = pkg.get("vdc") or {}
    parties = vdc.get("parties") or {}
    lines = [
        "NovaPanda Arbitration Export (informative text shell)",
        f"exported_at: {pkg.get('exported_at')}",
        f"vdc_id: {pkg.get('vdc_id')}",
        f"exchange_id: {pkg.get('exchange_id')}",
        f"state: {vdc.get('state')}",
        f"client: {parties.get('client')}",
        f"provider: {parties.get('provider')}",
        f"result_hash: {vdc.get('result_hash')}",
        f"fingerprint: {pkg.get('vdc_fingerprint')}",
    ]
    rv = pkg.get("reverify")
    if isinstance(rv, dict):
        lines.append(f"reverify_ok: {_all_ok(rv)}")
    lines.append("NOTE: Verify with JSON + novapanda.reverify; do not trust this text alone.")
    return "\n".join(lines)
