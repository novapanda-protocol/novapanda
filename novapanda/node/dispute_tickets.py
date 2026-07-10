"""SEC-OP-02 · 争议工单（身体层；不改 VDC）。"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ticket_id() -> str:
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"DISP-{day}-{uuid.uuid4().hex[:4].upper()}"


@dataclass
class DisputeTicket:
    ticket_id: str
    exchange_id: str
    tier: str  # D0 | D1 | D2
    state: str  # open | awaiting_party | in_review | memo_issued | closed | stale
    opened_at: str
    sla_due: Optional[str]
    parties: dict
    dispute_info: dict
    reason: str = ""


@dataclass
class DisputeTicketRegistry:
    """进程内工单表；生产可换持久化。"""

    _by_id: dict[str, DisputeTicket] = field(default_factory=dict)
    _by_exchange: dict[str, str] = field(default_factory=dict)

    def open_for_exchange(
        self,
        *,
        exchange_id: str,
        reason: str,
        dispute_info: dict,
        client: str,
        provider: str,
        tier: str = "D0",
    ) -> DisputeTicket:
        existing = self._by_exchange.get(exchange_id)
        if existing:
            return self._by_id[existing]
        opened = datetime.now(timezone.utc)
        sla = opened + timedelta(days=3)
        ticket = DisputeTicket(
            ticket_id=_ticket_id(),
            exchange_id=exchange_id,
            tier=tier,
            state="open",
            opened_at=_now(),
            sla_due=sla.strftime("%Y-%m-%dT%H:%M:%SZ"),
            parties={"client_agent_id": client, "provider_agent_id": provider},
            dispute_info=dict(dispute_info or {}),
            reason=reason,
        )
        self._by_id[ticket.ticket_id] = ticket
        self._by_exchange[exchange_id] = ticket.ticket_id
        return ticket

    def get(self, ticket_id: str) -> Optional[DisputeTicket]:
        return self._by_id.get(ticket_id)

    def get_by_exchange(self, exchange_id: str) -> Optional[DisputeTicket]:
        tid = self._by_exchange.get(exchange_id)
        return self._by_id.get(tid) if tid else None

    def list_all(self, *, state: Optional[str] = None, limit: int = 100) -> list[DisputeTicket]:
        items = list(self._by_id.values())
        if state:
            items = [t for t in items if t.state == state]
        items.sort(key=lambda t: t.opened_at, reverse=True)
        return items[:limit]

    def public(self, ticket: DisputeTicket) -> dict:
        return asdict(ticket)
