"""NP-CLAIM-XFER 生产登记处：VDC 锚定、assignment 验签、防双花。

与 claim_mock 分离：claim_id 前缀 claim_；可持久化到 JSON 文件。
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..canonical import canonical_bytes
from ..identity import verify


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def assignment_bytes(*, claim_id: str, to_agent_id: str, nonce: str, at: str) -> bytes:
    return canonical_bytes(
        {
            "type": "np_claim_assignment",
            "claim_version": "0.1",
            "claim_id": claim_id,
            "to_agent_id": to_agent_id,
            "nonce": nonce,
            "at": at,
        }
    )


@dataclass
class ClaimRecord:
    claim_version: str
    claim_id: str
    vdc_id: str
    rail: str
    holder_agent_id: str
    amount: int
    currency: str
    status: str  # open | reserved | spent | released | expired | frozen
    issued_at: str
    expires_at: Optional[str] = None
    lineage: list[dict] = field(default_factory=list)
    reserved_for: Optional[str] = None


class ClaimRegistry:
    """Durable claim registry for NP-CLAIM-XFER."""

    def __init__(self, path: Optional[str | Path] = None) -> None:
        self._path = Path(path) if path else None
        self._by_id: dict[str, ClaimRecord] = {}
        if self._path and self._path.is_file():
            self._load()

    @property
    def is_production(self) -> bool:
        return True

    def issue(
        self,
        *,
        vdc_id: str,
        amount: int,
        currency: str,
        holder: str,
        rail: str = "mock",
    ) -> ClaimRecord:
        if not vdc_id or not str(vdc_id).strip():
            raise ValueError("vdc_anchor_required")
        if amount < 0:
            raise ValueError("amount_negative")
        if not holder.startswith("ed25519:"):
            raise ValueError("holder_must_be_agent_id")
        rec = ClaimRecord(
            claim_version="0.1",
            claim_id="claim_" + uuid.uuid4().hex[:16],
            vdc_id=vdc_id.strip(),
            rail=rail or "mock",
            holder_agent_id=holder,
            amount=amount,
            currency=currency or "USD",
            status="open",
            issued_at=_now(),
        )
        self._by_id[rec.claim_id] = rec
        self._persist()
        return rec

    def assign(
        self,
        claim_id: str,
        to_agent_id: str,
        *,
        signature: str,
        nonce: str,
        at: str,
    ) -> ClaimRecord:
        rec = self._require(claim_id)
        if rec.status != "open":
            raise ValueError("not_open")
        if not to_agent_id.startswith("ed25519:"):
            raise ValueError("invalid_to_agent_id")
        msg = assignment_bytes(claim_id=claim_id, to_agent_id=to_agent_id, nonce=nonce, at=at)
        if not verify(rec.holder_agent_id, signature, msg):
            raise ValueError("invalid_assignment_signature")
        from_holder = rec.holder_agent_id
        rec.lineage.append(
            {
                "from": from_holder,
                "to": to_agent_id,
                "at": at,
                "nonce": nonce,
                "sig": signature,
            }
        )
        rec.holder_agent_id = to_agent_id
        self._persist()
        return rec

    def reserve(self, claim_id: str, *, for_exchange_id: str) -> ClaimRecord:
        rec = self._require(claim_id)
        if rec.status != "open":
            raise ValueError("not_open")
        rec.status = "reserved"
        rec.reserved_for = for_exchange_id
        self._persist()
        return rec

    def capture(self, claim_id: str) -> ClaimRecord:
        rec = self._require(claim_id)
        if rec.status != "reserved":
            raise ValueError("not_reserved")
        rec.status = "spent"
        self._persist()
        return rec

    def release(self, claim_id: str) -> ClaimRecord:
        rec = self._require(claim_id)
        if rec.status not in ("open", "reserved"):
            raise ValueError("cannot_release")
        rec.status = "released"
        rec.reserved_for = None
        self._persist()
        return rec

    def redeem(self, claim_id: str) -> ClaimRecord:
        """Redeem：开放态直接消耗（轨侧放款由伙伴处理，登记处只记 spent）。"""
        rec = self._require(claim_id)
        if rec.status != "open":
            raise ValueError("not_open")
        rec.status = "spent"
        self._persist()
        return rec

    def get(self, claim_id: str) -> Optional[ClaimRecord]:
        return self._by_id.get(claim_id)

    def list_for_holder(self, holder: Optional[str] = None) -> list[ClaimRecord]:
        items = list(self._by_id.values())
        if holder:
            items = [c for c in items if c.holder_agent_id == holder]
        return sorted(items, key=lambda c: c.issued_at, reverse=True)

    def clear(self) -> None:
        self._by_id.clear()
        self._persist()

    def public(self, rec: ClaimRecord) -> dict:
        return {
            "claim_version": rec.claim_version,
            "claim_id": rec.claim_id,
            "vdc_id": rec.vdc_id,
            "rail": rec.rail,
            "holder_agent_id": rec.holder_agent_id,
            "holder": rec.holder_agent_id,
            "amount": rec.amount,
            "currency": rec.currency,
            "status": rec.status,
            "issued_at": rec.issued_at,
            "expires_at": rec.expires_at,
            "lineage": list(rec.lineage),
            "reserved_for": rec.reserved_for,
            "mock": False,
            "profile": "NP-CLAIM-XFER",
        }

    def _require(self, claim_id: str) -> ClaimRecord:
        rec = self._by_id.get(claim_id)
        if rec is None:
            raise ValueError("not_found")
        return rec

    def _persist(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"claims": [asdict(c) for c in self._by_id.values()]}
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load(self) -> None:
        data = json.loads(self._path.read_text(encoding="utf-8"))
        for raw in data.get("claims") or []:
            rec = ClaimRecord(**raw)
            self._by_id[rec.claim_id] = rec


def make_claim_store(*, mode: str, db_path: Optional[str] = None, default_rail: str = "mock"):
    """mock | production → 对应登记处。"""
    from .claim_mock import ClaimMockRegistry

    if mode == "production":
        return ClaimRegistry(path=db_path), True
    return ClaimMockRegistry(), False
