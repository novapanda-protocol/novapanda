"""Claim mock registry — demo only; Manifest must stay honest (not production NP-CLAIM-XFER)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class MockClaim:
    claim_id: str
    vdc_id: str
    amount: int
    currency: str
    holder: str
    status: str  # open | reserved | spent | released
    created_at: str
    reserved_for: Optional[str] = None


@dataclass
class ClaimMockRegistry:
    """In-memory mock claims anchored on vdc_id."""

    _by_id: dict[str, MockClaim] = field(default_factory=dict)

    def issue(self, *, vdc_id: str, amount: int, currency: str, holder: str) -> MockClaim:
        if not vdc_id or not str(vdc_id).strip():
            raise ValueError("vdc_anchor_required")
        if amount < 0:
            raise ValueError("amount_negative")
        c = MockClaim(
            claim_id="mock-claim-" + uuid.uuid4().hex[:12],
            vdc_id=vdc_id.strip(),
            amount=amount,
            currency=currency or "USD",
            holder=holder,
            status="open",
            created_at=_now(),
        )
        self._by_id[c.claim_id] = c
        return c

    def reserve(self, claim_id: str, *, for_exchange_id: str) -> MockClaim:
        c = self._require(claim_id)
        if c.status != "open":
            raise ValueError("not_open")
        c.status = "reserved"
        c.reserved_for = for_exchange_id
        return c

    def capture(self, claim_id: str) -> MockClaim:
        c = self._require(claim_id)
        if c.status != "reserved":
            raise ValueError("not_reserved")
        c.status = "spent"
        return c

    def release(self, claim_id: str) -> MockClaim:
        c = self._require(claim_id)
        if c.status not in ("open", "reserved"):
            raise ValueError("cannot_release")
        c.status = "released"
        c.reserved_for = None
        return c

    def get(self, claim_id: str) -> Optional[MockClaim]:
        return self._by_id.get(claim_id)

    def list_for_holder(self, holder: Optional[str] = None) -> list[MockClaim]:
        items = list(self._by_id.values())
        if holder:
            items = [c for c in items if c.holder == holder]
        return sorted(items, key=lambda c: c.created_at, reverse=True)

    def public(self, c: MockClaim) -> dict:
        return {
            "claim_id": c.claim_id,
            "vdc_id": c.vdc_id,
            "amount": c.amount,
            "currency": c.currency,
            "holder": c.holder,
            "status": c.status,
            "reserved_for": c.reserved_for,
            "created_at": c.created_at,
            "mock": True,
            "note": "mock only — not production NP-CLAIM-XFER",
        }

    def _require(self, claim_id: str) -> MockClaim:
        c = self._by_id.get(claim_id)
        if c is None:
            raise ValueError("not_found")
        return c
