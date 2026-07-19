"""多轨锚定（M4）：本地账本 + 公告板 + 链上轨占位。

全部为身体旁路；**不得**替代 SETTLED + 双签 VDC。
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Protocol

from ..canonical import canonical_bytes
from ..hashing import sha256_hex
from .anchor import AnchorReceipt, LocalAnchorLedger
from .paths import ensure_dir


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class AnchorRail(Protocol):
    def rail_id(self) -> str: ...
    def publish(
        self,
        *,
        vdc_fingerprint: str,
        vdc_id: str,
        exchange_id: str,
        meta: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]: ...
    def lookup(self, vdc_fingerprint: str) -> list[dict[str, Any]]: ...


@dataclass
class BulletinBoardRail:
    """共享公告板文件（多 Agent 可读的廉价公示面，非公链）。"""

    path: Path
    rail_name: str = "bulletin_file"

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        ensure_dir(self.path.parent)
        if not self.path.is_file():
            self.path.write_text("", encoding="utf-8")

    def rail_id(self) -> str:
        return self.rail_name

    def publish(
        self,
        *,
        vdc_fingerprint: str,
        vdc_id: str,
        exchange_id: str,
        meta: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        row = {
            "bulletin_id": "bul-" + uuid.uuid4().hex[:12],
            "vdc_id": vdc_id,
            "exchange_id": exchange_id,
            "vdc_fingerprint": vdc_fingerprint,
            "published_at": _now(),
            "rail": self.rail_name,
            "meta": dict(meta or {}),
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return row

    def lookup(self, vdc_fingerprint: str) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        hits: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("vdc_fingerprint") == vdc_fingerprint:
                hits.append(row)
        return hits


@dataclass
class ChainAnchorStub:
    """公链锚定占位：只生成伪 tx 回执，不广播。

    真链接入时替换 ``submit`` 实现；语义仍是旁路公示。
    """

    chain_id: str = "stub-evm-1"
    submitted: list[dict[str, Any]] = field(default_factory=list)

    def rail_id(self) -> str:
        return f"chain_stub:{self.chain_id}"

    def publish(
        self,
        *,
        vdc_fingerprint: str,
        vdc_id: str,
        exchange_id: str,
        meta: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        # 伪 tx：fingerprint 前缀作回执，明确 stub
        digest = sha256_hex(
            f"{self.chain_id}:{vdc_fingerprint}:{exchange_id}".encode()
        )
        row = {
            "tx_stub": f"0x{digest[:32]}",
            "chain_id": self.chain_id,
            "vdc_id": vdc_id,
            "exchange_id": exchange_id,
            "vdc_fingerprint": vdc_fingerprint,
            "published_at": _now(),
            "rail": self.rail_id(),
            "live": False,
            "note": "stub only — not broadcast",
            "meta": dict(meta or {}),
        }
        self.submitted.append(row)
        return row

    def lookup(self, vdc_fingerprint: str) -> list[dict[str, Any]]:
        return [r for r in self.submitted if r.get("vdc_fingerprint") == vdc_fingerprint]


@dataclass
class MultiRailAnchor:
    """先写本地账本，再扇出到公告板 / 链 stub。"""

    local: LocalAnchorLedger
    rails: list[Any] = field(default_factory=list)

    @staticmethod
    def fingerprint_vdc(vdc: dict[str, Any]) -> str:
        return "sha256:" + sha256_hex(canonical_bytes(vdc))

    def anchor(
        self,
        *,
        vdc: dict[str, Any],
        exchange_id: str,
        meta: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        local_receipt = self.local.anchor(vdc=vdc, exchange_id=exchange_id, meta=meta)
        fp = local_receipt.vdc_fingerprint
        fanout: list[dict[str, Any]] = []
        for rail in self.rails:
            fanout.append(
                rail.publish(
                    vdc_fingerprint=fp,
                    vdc_id=local_receipt.vdc_id,
                    exchange_id=exchange_id,
                    meta=meta,
                )
            )
        return {
            "local": local_receipt.to_dict(),
            "fanout": fanout,
            "note": "旁路多轨锚定；交割终局仍是 SETTLED + 双签 VDC",
        }

    def verify(self, vdc: dict[str, Any]) -> dict[str, Any]:
        fp = self.fingerprint_vdc(vdc)
        local = self.local.verify_local(vdc)
        rails = {rail.rail_id(): rail.lookup(fp) for rail in self.rails}
        return {
            "fingerprint": fp,
            "local": local,
            "rails": rails,
            "anchored_any": bool(local.get("anchored")) or any(rails.values()),
        }
