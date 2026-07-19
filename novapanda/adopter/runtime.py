"""AdopterRuntime：接入方门面 —— Draft / Outbox / Vault / Intent / Peer / Query。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ..hashing import result_hash_of_json
from ..sdk import NovaPandaClient
from .anchor import AnchorReceipt, LocalAnchorLedger
from .anchor_rails import BulletinBoardRail, ChainAnchorStub, MultiRailAnchor
from .draft import DraftStore
from .export_pdf import write_arbitration_pdf
from .export_pkg import build_arbitration_package, package_summary_text
from .intent import IntentMap, IntentMatch
from .outbox import Outbox
from .peer import PeerBackup
from .query import VaultQuery
from .stations import StationDirectory, StationDiscovery, StationRecord
from .types import DraftRecord, OutboxItem, OutboxOp, VaultEntry
from .vault import VdcVault


class AdopterRuntime:
    """每个 Agent 进程一份；root 下隔离 drafts/outbox/vault。"""

    def __init__(
        self,
        client: NovaPandaClient,
        root: Path | str,
        *,
        enable_bulletin: bool = True,
        enable_chain_stub: bool = False,
        shared_bulletin: Optional[Path] = None,
    ) -> None:
        self.client = client
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.drafts = DraftStore(self.root)
        self.outbox = Outbox(self.root)
        self.vault = VdcVault(self.root)
        self.intents = IntentMap()
        self.peers = PeerBackup(self.vault)
        self.query = VaultQuery(self.vault)
        self.anchors = LocalAnchorLedger(self.root)
        rails: list = []
        bulletin_path = shared_bulletin or (self.root / "anchors" / "bulletin.jsonl")
        if enable_bulletin:
            rails.append(BulletinBoardRail(bulletin_path))
        if enable_chain_stub:
            rails.append(ChainAnchorStub())
        self.multi_anchor = MultiRailAnchor(local=self.anchors, rails=rails)
        self.stations = StationDiscovery(StationDirectory(self.root), client)
        from .cabin import CabinConsole

        self.cabin = CabinConsole(self)

    @property
    def agent_id(self) -> str:
        return self.client.agent_id

    # ----- 草稿 -----

    def open_draft(
        self,
        *,
        peer_id: str,
        resource_type: str,
        rule_id: str,
        intent_summary: str = "",
        meta: Optional[dict[str, Any]] = None,
    ) -> DraftRecord:
        return self.drafts.create(
            agent_id=self.agent_id,
            peer_id=peer_id,
            resource_type=resource_type,
            rule_id=rule_id,
            intent_summary=intent_summary,
            meta=meta,
        )

    def prepare_deliverable(self, draft_id: str, deliverable: dict[str, Any]) -> DraftRecord:
        return self.drafts.set_deliverable(draft_id, deliverable)

    def deliver_from_draft(self, draft_id: str, *, evidence_level: str = "dual_signed") -> dict:
        rec = self.drafts.get(draft_id)
        if not rec.exchange_id:
            raise ValueError("草稿未绑定 exchange_id")
        if not rec.deliverable:
            raise ValueError("草稿无交付物")
        result = self.client.deliver(
            rec.exchange_id, rec.deliverable, evidence_level=evidence_level,
        )
        self.drafts.mark_committed(draft_id)
        return result

    # ----- 网络感知写操作 -----

    def confirm(self, exchange_id: str, *, force_queue: bool = False) -> Any:
        if force_queue or not self.outbox.network_up:
            return self.outbox.enqueue(OutboxOp.CONFIRM, exchange_id)
        result = self.client.confirm(exchange_id)
        self._ingest_exchange(exchange_id, role="client", deliverable=None)
        return result

    def dispute(self, exchange_id: str, reason: str, *, force_queue: bool = False) -> Any:
        if force_queue or not self.outbox.network_up:
            return self.outbox.enqueue(
                OutboxOp.DISPUTE, exchange_id, {"reason": reason},
            )
        return self.client.dispute(exchange_id, reason=reason)

    def verify(self, exchange_id: str, *, force_queue: bool = False) -> Any:
        if force_queue or not self.outbox.network_up:
            return self.outbox.enqueue(OutboxOp.VERIFY, exchange_id)
        return self.client.verify(exchange_id)

    def flush_outbox(self) -> list[dict[str, Any]]:
        def _handler(item: OutboxItem) -> Any:
            if item.op == OutboxOp.CONFIRM.value:
                result = self.client.confirm(item.exchange_id)
                self._ingest_exchange(item.exchange_id, role="client", deliverable=None)
                return result
            if item.op == OutboxOp.DISPUTE.value:
                return self.client.dispute(
                    item.exchange_id, reason=str(item.payload.get("reason") or "queued_dispute"),
                )
            if item.op == OutboxOp.VERIFY.value:
                return self.client.verify(item.exchange_id)
            if item.op == OutboxOp.DELIVER.value:
                return self.client.deliver(
                    item.exchange_id,
                    item.payload["deliverable"],
                    evidence_level=str(item.payload.get("evidence_level") or "dual_signed"),
                )
            if item.op == OutboxOp.CONTRACT.value:
                return self.client.contract(item.exchange_id)
            if item.op == OutboxOp.ESCROW.value:
                return self.client.escrow(
                    item.exchange_id,
                    amount=int(item.payload["amount"]),
                    currency=str(item.payload["currency"]),
                )
            raise ValueError(f"未知 outbox op: {item.op}")

        return self.outbox.flush(_handler)

    # ----- Intent -----

    def apply_intent(self, exchange_id: str, text: str) -> dict[str, Any]:
        match = self.intents.require(text)
        return self._dispatch_intent(exchange_id, match)

    def _dispatch_intent(self, exchange_id: str, match: IntentMatch) -> dict[str, Any]:
        if match.action == "confirm":
            return {"action": "confirm", "result": self.confirm(exchange_id)}
        if match.action == "dispute":
            return {"action": "dispute", "result": self.dispute(exchange_id, match.reason)}
        if match.action == "verify":
            return {"action": "verify", "result": self.verify(exchange_id)}
        if match.action == "export":
            entry = self.vault.get_by_exchange(exchange_id)
            if entry is None:
                raise KeyError(f"Vault 中无 exchange {exchange_id}")
            pkg = build_arbitration_package(entry)
            return {
                "action": "export",
                "package": pkg,
                "summary_text": package_summary_text(pkg),
            }
        if match.action == "status":
            return {"action": "status", "result": self.client.get_exchange(exchange_id)}
        raise ValueError(f"未实现 action: {match.action}")

    # ----- Vault / Peer -----

    def remember_settled(
        self,
        exchange_id: str,
        *,
        role: str,
        deliverable: Optional[dict[str, Any]] = None,
        peer_id: Optional[str] = None,
    ) -> VaultEntry:
        return self._ingest_exchange(
            exchange_id, role=role, deliverable=deliverable, peer_id=peer_id,
        )

    def _ingest_exchange(
        self,
        exchange_id: str,
        *,
        role: str,
        deliverable: Optional[dict[str, Any]],
        peer_id: Optional[str] = None,
    ) -> VaultEntry:
        ex = self.client.get_exchange(exchange_id)
        doc = ex.get("vdc")
        if not doc:
            raise RuntimeError("Exchange 尚无 VDC")
        if peer_id is None:
            peer_id = ex["provider"] if role == "client" else ex["client"]
        # 节点 export 在鉴权为当事方时可能附带 deliverable；否则仅存 VDC
        if deliverable is None:
            try:
                exported = self.client.export_exchange(exchange_id)
                d = exported.get("deliverable")
                if isinstance(d, dict):
                    deliverable = d
            except Exception:  # noqa: BLE001
                pass
        return self.vault.put(
            vdc=doc,
            exchange_id=exchange_id,
            peer_id=peer_id,
            role=role,
            deliverable=deliverable,
            source="local",
        )

    def mutual_backup_export(
        self,
        exchange_id: str,
        *,
        include_deliverable: bool = True,
    ) -> dict[str, Any]:
        entry = self.vault.get_by_exchange(exchange_id)
        if entry is None:
            entry = self.remember_settled(exchange_id, role="client")
        return self.peers.export_for_peer(entry, include_deliverable=include_deliverable)

    def mutual_backup_import(
        self,
        package: dict[str, Any],
        *,
        peer_id: str,
        role: str,
    ) -> VaultEntry:
        return self.peers.import_from_peer(package, peer_id=peer_id, role=role)

    def export_arbitration(self, exchange_id: str) -> dict[str, Any]:
        entry = self.vault.get_by_exchange(exchange_id)
        if entry is None:
            raise KeyError(f"Vault 中无 exchange {exchange_id}")
        return build_arbitration_package(entry)

    def export_arbitration_pdf(self, exchange_id: str, path: Path | str) -> Path:
        pkg = self.export_arbitration(exchange_id)
        return write_arbitration_pdf(path, pkg)

    def anchor_exchange(
        self,
        exchange_id: str,
        *,
        meta: Optional[dict[str, Any]] = None,
        multi: bool = False,
    ) -> AnchorReceipt | dict[str, Any]:
        entry = self.vault.get_by_exchange(exchange_id)
        if entry is None:
            raise KeyError(f"Vault 中无 exchange {exchange_id}")
        if multi:
            return self.multi_anchor.anchor(
                vdc=entry.vdc, exchange_id=exchange_id, meta=meta,
            )
        return self.anchors.anchor(
            vdc=entry.vdc, exchange_id=exchange_id, meta=meta,
        )

    def register_station(self, station: StationRecord) -> StationRecord:
        return self.stations.register_local(station)

    def discover_stations(
        self,
        *,
        max_amount: int = 10_000,
        prefer_marketplace: bool = True,
    ) -> dict[str, Any]:
        return self.stations.discover(
            max_amount=max_amount, prefer_marketplace=prefer_marketplace,
        )

    def deliverable_hash(self, deliverable: dict[str, Any]) -> str:
        return result_hash_of_json(deliverable)

    def build_manifest(
        self,
        *,
        capabilities: list[dict[str, Any]],
        exchange_endpoint: str = "http://localhost/exchanges",
        profiles: Optional[list[str]] = None,
        declare_lite: bool = False,
        lite_tier: str = "edge",
    ) -> dict[str, Any]:
        """自签 Agent Manifest；``declare_lite`` 时声明 Outbox 离线队列。"""
        from ..manifest import build_agent_manifest

        profs = list(profiles or ["NP-MIN"])
        lite = None
        if declare_lite or "NP-LITE" in profs:
            if "NP-LITE" not in profs:
                profs.append("NP-LITE")
            lite = {
                "tier": lite_tier,
                "canonical": "novapanda-c1",
                "offline_queue": True,
            }
        return build_agent_manifest(
            self.client.identity,
            capabilities=capabilities,
            exchange_endpoint=exchange_endpoint,
            profiles=profs,
            lite=lite,
        )

    def check_lite_alignment(self, *, profiles: Optional[list[str]] = None) -> dict[str, Any]:
        """对照 NP-LITE-03：分区时 flush 必须拒绝。"""
        from ..manifest_validate import check_lite_outbox_alignment

        was_up = self.outbox.network_up
        try:
            self.outbox.partition()
            blocked = False
            try:
                self.outbox.flush(lambda _i: None)
            except RuntimeError:
                blocked = True
        finally:
            if was_up:
                self.outbox.restore()
            else:
                self.outbox.partition()
        return check_lite_outbox_alignment(
            profiles=profiles or ["NP-MIN", "NP-LITE"],
            offline_queue_implemented=True,
            flush_blocked_when_offline=blocked,
        )
