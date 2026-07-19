"""Vault 多维查询与简单统计（身体能力，非 CORE）。"""

from __future__ import annotations

from collections import Counter
from typing import Any, Optional

from .types import VaultEntry
from .vault import VdcVault


class VaultQuery:
    def __init__(self, vault: VdcVault) -> None:
        self.vault = vault

    def search(
        self,
        *,
        peer_id: Optional[str] = None,
        state: Optional[str] = None,
        resource_type: Optional[str] = None,
        keyword: Optional[str] = None,
        source: Optional[str] = None,
    ) -> list[VaultEntry]:
        kw = (keyword or "").strip().lower()
        out: list[VaultEntry] = []
        for e in self.vault.list_all():
            if peer_id and e.peer_id != peer_id:
                continue
            if state and e.state != state:
                continue
            if resource_type and e.resource_type != resource_type:
                continue
            if source and e.source != source:
                continue
            if kw:
                blob = f"{e.vdc_id} {e.exchange_id} {e.peer_id} {e.resource_type} {e.state}".lower()
                if e.deliverable:
                    blob += " " + str(e.deliverable).lower()
                if kw not in blob:
                    continue
            out.append(e)
        return out

    def stats(self) -> dict[str, Any]:
        entries = self.vault.list_all()
        by_state = Counter(e.state for e in entries)
        by_peer = Counter(e.peer_id for e in entries)
        by_type = Counter(e.resource_type for e in entries)
        return {
            "total": len(entries),
            "by_state": dict(by_state),
            "by_peer": dict(by_peer),
            "by_resource_type": dict(by_type),
            "settled": by_state.get("SETTLED", 0),
            "disputed": by_state.get("DISPUTED", 0),
        }
