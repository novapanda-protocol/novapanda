"""VdcVault：本地 VDC + 可选交付物；不依赖原节点 DB。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..hashing import result_hash_of_json
from .paths import ensure_dir, read_json, atomic_write_json
from .types import VaultEntry


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class VdcVault:
    def __init__(self, root: Path) -> None:
        self.root = ensure_dir(Path(root) / "vault")
        self._index = self.root / "index.json"
        if not self._index.is_file():
            atomic_write_json(self._index, {"ids": []})

    def _path(self, vdc_id: str) -> Path:
        safe = vdc_id.replace(":", "_").replace("/", "_")
        return self.root / f"{safe}.json"

    def _ids(self) -> list[str]:
        return list(read_json(self._index, {"ids": []}).get("ids", []))

    def _set_ids(self, ids: list[str]) -> None:
        atomic_write_json(self._index, {"ids": ids})

    def put(
        self,
        *,
        vdc: dict[str, Any],
        exchange_id: str,
        peer_id: str,
        role: str,
        deliverable: Optional[dict[str, Any]] = None,
        source: str = "local",
        tags: Optional[list[str]] = None,
    ) -> VaultEntry:
        vdc_id = str(vdc.get("vdc_id") or "")
        if not vdc_id:
            raise ValueError("VDC 缺少 vdc_id")
        rh = str(vdc.get("result_hash") or "")
        if deliverable is not None and not rh:
            rh = result_hash_of_json(deliverable)
        entry = VaultEntry(
            vdc_id=vdc_id,
            exchange_id=exchange_id,
            peer_id=peer_id,
            role=role,
            state=str(vdc.get("state") or ""),
            resource_type=str(vdc.get("resource_type") or ""),
            vdc=dict(vdc),
            deliverable=dict(deliverable) if deliverable is not None else None,
            result_hash=rh,
            stored_at=_now(),
            source=source,
            tags=list(tags or []),
        )
        atomic_write_json(self._path(vdc_id), entry.to_dict())
        ids = self._ids()
        if vdc_id not in ids:
            ids.append(vdc_id)
            self._set_ids(ids)
        return entry

    def get(self, vdc_id: str) -> VaultEntry:
        data = read_json(self._path(vdc_id))
        if data is None:
            raise KeyError(f"未知 VDC: {vdc_id}")
        return VaultEntry.from_dict(data)

    def get_by_exchange(self, exchange_id: str) -> Optional[VaultEntry]:
        for vid in self._ids():
            try:
                e = self.get(vid)
            except KeyError:
                continue
            if e.exchange_id == exchange_id:
                return e
        return None

    def list_all(self) -> list[VaultEntry]:
        out: list[VaultEntry] = []
        for vid in self._ids():
            try:
                out.append(self.get(vid))
            except KeyError:
                continue
        return out

    def contains(self, vdc_id: str) -> bool:
        return self._path(vdc_id).is_file()
