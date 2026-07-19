"""PeerBackup：双方互存同一 VDC 字节（不改签）。"""

from __future__ import annotations

from typing import Any, Optional

from ..canonical import canonical_bytes
from ..hashing import sha256_hex
from .vault import VdcVault
from .types import VaultEntry


class PeerBackup:
    def __init__(self, vault: VdcVault) -> None:
        self.vault = vault

    @staticmethod
    def package_fingerprint(vdc: dict[str, Any]) -> str:
        return "sha256:" + sha256_hex(canonical_bytes(vdc))

    def export_for_peer(
        self,
        entry: VaultEntry,
        *,
        include_deliverable: bool = True,
    ) -> dict[str, Any]:
        pkg = {
            "package_version": "adopter-peer-1",
            "vdc_id": entry.vdc_id,
            "exchange_id": entry.exchange_id,
            "vdc": entry.vdc,
            "fingerprint": self.package_fingerprint(entry.vdc),
        }
        if include_deliverable and entry.deliverable is not None:
            pkg["deliverable"] = entry.deliverable
        return pkg

    def import_from_peer(
        self,
        package: dict[str, Any],
        *,
        peer_id: str,
        role: str,
        expect_fingerprint: Optional[str] = None,
    ) -> VaultEntry:
        vdc = package.get("vdc")
        if not isinstance(vdc, dict):
            raise ValueError("peer 包缺少 vdc")
        fp = self.package_fingerprint(vdc)
        claimed = package.get("fingerprint")
        if claimed and claimed != fp:
            raise ValueError("peer 包 fingerprint 与 VDC 字节不一致")
        if expect_fingerprint and expect_fingerprint != fp:
            raise ValueError("fingerprint 与预期不符")
        deliverable = package.get("deliverable")
        if deliverable is not None and not isinstance(deliverable, dict):
            raise ValueError("deliverable 须为 object")
        return self.vault.put(
            vdc=vdc,
            exchange_id=str(package.get("exchange_id") or vdc.get("idempotency_key") or ""),
            peer_id=peer_id,
            role=role,
            deliverable=deliverable,
            source="peer_backup",
            tags=["peer_backup"],
        )
