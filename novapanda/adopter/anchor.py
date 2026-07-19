"""廉价本地哈希锚定（身体旁路）。

记录 VDC fingerprint 的 append-only 账本，**不是** SETTLED 真源，也不是公链终局。
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..canonical import canonical_bytes
from ..hashing import sha256_hex
from .paths import ensure_dir


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class AnchorReceipt:
    anchor_id: str
    vdc_id: str
    exchange_id: str
    vdc_fingerprint: str
    anchored_at: str
    rail: str  # local_jsonl | bulletin_file
    note: str = "旁路锚定；交割终局仍是 SETTLED + 双签 VDC"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LocalAnchorLedger:
    """JSONL 锚定账本，落在 Adopter root/anchors/ledger.jsonl。"""

    def __init__(self, root: Path | str) -> None:
        self.root = ensure_dir(Path(root) / "anchors")
        self.ledger_path = self.root / "ledger.jsonl"

    @staticmethod
    def fingerprint_vdc(vdc: dict[str, Any]) -> str:
        return "sha256:" + sha256_hex(canonical_bytes(vdc))

    def anchor(
        self,
        *,
        vdc: dict[str, Any],
        exchange_id: str,
        meta: Optional[dict[str, Any]] = None,
    ) -> AnchorReceipt:
        vdc_id = str(vdc.get("vdc_id") or "")
        if not vdc_id:
            raise ValueError("VDC 缺少 vdc_id")
        fp = self.fingerprint_vdc(vdc)
        receipt = AnchorReceipt(
            anchor_id="anc-" + uuid.uuid4().hex[:12],
            vdc_id=vdc_id,
            exchange_id=exchange_id,
            vdc_fingerprint=fp,
            anchored_at=_now(),
            rail="local_jsonl",
        )
        row = receipt.to_dict()
        if meta:
            row["meta"] = dict(meta)
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        # 单条回执文件便于分享
        (self.root / f"{receipt.anchor_id}.json").write_text(
            json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        return receipt

    def list_all(self) -> list[dict[str, Any]]:
        if not self.ledger_path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.ledger_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
        return rows

    def find_by_fingerprint(self, fingerprint: str) -> list[dict[str, Any]]:
        return [r for r in self.list_all() if r.get("vdc_fingerprint") == fingerprint]

    def verify_local(self, vdc: dict[str, Any]) -> dict[str, Any]:
        fp = self.fingerprint_vdc(vdc)
        hits = self.find_by_fingerprint(fp)
        return {
            "fingerprint": fp,
            "anchored": bool(hits),
            "hits": hits,
            "note": "本地账本命中 ≠ 链上终局；SETTLED 仍靠双签 VDC",
        }
