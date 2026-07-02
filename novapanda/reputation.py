"""信誉账本：append-only、哈希链、节点签名、可跨节点独立复验。

信誉是交割历史的客观沉淀，而非任何节点的主观打分。
任何人持有日志即可：1) 重算每条 entry_hash 与链接；2) 验证节点签名。
跨节点可携带、可比对——这是「信誉不被任何单一主体绑架」的基础。
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional

from .canonical import canonical_bytes
from .hashing import sha256_hex
from .identity import Identity, verify as _verify_sig

GENESIS = "GENESIS"


class InMemoryReputationStore:
    def __init__(self) -> None:
        self._entries: list[dict] = []

    def append(self, entry: dict) -> None:
        self._entries.append(entry)

    def last(self) -> Optional[dict]:
        return self._entries[-1] if self._entries else None

    def count(self) -> int:
        return len(self._entries)

    def all(self) -> list[dict]:
        return list(self._entries)


class SQLiteReputationStore:
    def __init__(self, path: str = ":memory:") -> None:
        self._cx = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._cx.execute(
            "CREATE TABLE IF NOT EXISTS reputation("
            "seq INTEGER PRIMARY KEY, agent_id TEXT NOT NULL, data TEXT NOT NULL)"
        )
        self._cx.commit()

    def append(self, entry: dict) -> None:
        with self._lock:
            self._cx.execute(
                "INSERT INTO reputation(seq, agent_id, data) VALUES(?,?,?)",
                (entry["seq"], entry["agent_id"], json.dumps(entry)),
            )
            self._cx.commit()

    def last(self) -> Optional[dict]:
        row = self._cx.execute(
            "SELECT data FROM reputation ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return json.loads(row[0]) if row else None

    def count(self) -> int:
        return self._cx.execute("SELECT COUNT(*) FROM reputation").fetchone()[0]

    def all(self) -> list[dict]:
        rows = self._cx.execute("SELECT data FROM reputation ORDER BY seq").fetchall()
        return [json.loads(r[0]) for r in rows]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _entry_hash(core: dict) -> str:
    return "sha256:" + sha256_hex(canonical_bytes(core))


class ReputationLog:
    def __init__(self, node_identity: Identity, store=None) -> None:
        self._node = node_identity
        self._store = store if store is not None else InMemoryReputationStore()

    @property
    def node_id(self) -> str:
        return self._node.agent_id

    def append(
        self,
        *,
        agent_id: str,
        counterparty: str,
        exchange_id: str,
        vdc_id: Optional[str],
        role: str,
        outcome: str,
        resource_type: str,
        quantity: int,
        timestamp: Optional[str] = None,
    ) -> dict:
        last = self._store.last()
        prev_hash = last["entry_hash"] if last else GENESIS
        core = {
            "seq": self._store.count(),
            "node_id": self.node_id,
            "agent_id": agent_id,
            "counterparty": counterparty,
            "exchange_id": exchange_id,
            "vdc_id": vdc_id,
            "role": role,
            "outcome": outcome,
            "resource_type": resource_type,
            "quantity": quantity,
            "timestamp": timestamp or _now_iso(),
            "prev_hash": prev_hash,
        }
        entry_hash = _entry_hash(core)
        signature = self._node.sign(canonical_bytes(core))
        entry = {**core, "entry_hash": entry_hash, "signature": signature}
        self._store.append(entry)
        return entry

    def record_settlement(self, exchange) -> list[dict]:
        """SETTLED：双方各记一条 outcome=settled。"""
        vdc_id = exchange.vdc.get("vdc_id") if exchange.vdc else None
        return [
            self.append(
                agent_id=exchange.provider, counterparty=exchange.client,
                exchange_id=exchange.exchange_id, vdc_id=vdc_id, role="provider",
                outcome="settled", resource_type=exchange.resource_type,
                quantity=exchange.quantity,
            ),
            self.append(
                agent_id=exchange.client, counterparty=exchange.provider,
                exchange_id=exchange.exchange_id, vdc_id=vdc_id, role="client",
                outcome="settled", resource_type=exchange.resource_type,
                quantity=exchange.quantity,
            ),
        ]

    def record_outcome(self, exchange, *, agent_id: str, role: str, outcome: str) -> dict:
        vdc_id = exchange.vdc.get("vdc_id") if exchange.vdc else None
        counterparty = exchange.client if role == "provider" else exchange.provider
        return self.append(
            agent_id=agent_id, counterparty=counterparty,
            exchange_id=exchange.exchange_id, vdc_id=vdc_id, role=role,
            outcome=outcome, resource_type=exchange.resource_type,
            quantity=exchange.quantity,
        )

    def entries(self, agent_id: Optional[str] = None, since: int = 0) -> list[dict]:
        out = self._store.all()[since:]
        if agent_id is not None:
            out = [e for e in out if e["agent_id"] == agent_id]
        return list(out)

    def verify_chain(self) -> bool:
        prev_hash = GENESIS
        for i, entry in enumerate(self._store.all()):
            if entry["seq"] != i or entry["prev_hash"] != prev_hash:
                return False
            core = {k: entry[k] for k in entry if k not in ("entry_hash", "signature")}
            if _entry_hash(core) != entry["entry_hash"]:
                return False
            if not _verify_sig(entry["node_id"], entry["signature"], canonical_bytes(core)):
                return False
            prev_hash = entry["entry_hash"]
        return True

    def export_bundle(self, agent_id: Optional[str] = None) -> dict:
        from .v2.federation import build_reputation_bundle

        return build_reputation_bundle(
            source_node_id=self.node_id,
            entries=self._store.all(),
            agent_id=agent_id,
        )

    def validate_external_bundle(self, bundle: dict) -> dict:
        from .v2.federation import validate_reputation_bundle

        errors = validate_reputation_bundle(bundle)
        return {"valid": len(errors) == 0, "errors": errors}

    def import_external_bundle(self, bundle: dict) -> list[dict]:
        from .v2.federation import import_reputation_bundle

        return import_reputation_bundle(self, bundle)

    def weighted_score(
        self,
        agent_id: str,
        *,
        weights: Optional[dict[str, float]] = None,
    ) -> dict:
        from .v2.reputation_agg import score_agent_from_ledger

        return score_agent_from_ledger(self.entries(), agent_id, weights=weights)

    def append_imported(self, external_entry: dict, *, source_node_id: str) -> dict:
        """将外链信誉条目镜像到本地链（导入节点联署）。"""
        last = self._store.last()
        prev_hash = last["entry_hash"] if last else GENESIS
        core = {
            "seq": self._store.count(),
            "node_id": self.node_id,
            "agent_id": external_entry["agent_id"],
            "counterparty": external_entry["counterparty"],
            "exchange_id": external_entry["exchange_id"],
            "vdc_id": external_entry.get("vdc_id"),
            "role": external_entry["role"],
            "outcome": external_entry["outcome"],
            "resource_type": external_entry["resource_type"],
            "quantity": external_entry["quantity"],
            "timestamp": external_entry["timestamp"],
            "prev_hash": prev_hash,
            "import_kind": "mirror",
            "external_ref": {
                "source_node_id": source_node_id,
                "source_entry_hash": external_entry["entry_hash"],
                "source_seq": external_entry["seq"],
            },
        }
        entry_hash = _entry_hash(core)
        signature = self._node.sign(canonical_bytes(core))
        entry = {**core, "entry_hash": entry_hash, "signature": signature}
        self._store.append(entry)
        return entry
