"""In-memory notify inbox + audit ring for零号身体层."""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class NotifyInbox:
    """Trial stub: stores notifications; does not send real email."""

    max_items: int = 200
    _items: deque = field(default_factory=lambda: deque(maxlen=200))

    def __post_init__(self) -> None:
        self._items = deque(maxlen=self.max_items)

    def push(
        self,
        *,
        kind: str,
        title: str,
        body: str = "",
        operator_id: Optional[str] = None,
    ) -> dict:
        item = {
            "id": "ntf-" + uuid.uuid4().hex[:10],
            "kind": kind,
            "title": title,
            "body": body,
            "operator_id": operator_id,
            "created_at": _now(),
            "channel": "inbox_stub",
        }
        self._items.appendleft(item)
        return item

    def list(self, *, operator_id: Optional[str] = None, limit: int = 50) -> list[dict]:
        items = list(self._items)
        if operator_id:
            items = [i for i in items if i.get("operator_id") in (None, operator_id)]
        return items[:limit]


@dataclass
class AuditLog:
    max_items: int = 500
    _items: deque = field(default_factory=lambda: deque(maxlen=500))

    def __post_init__(self) -> None:
        self._items = deque(maxlen=self.max_items)

    def record(self, action: str, **meta: Any) -> dict:
        entry = {
            "id": "aud-" + uuid.uuid4().hex[:10],
            "action": action,
            "at": _now(),
            **{k: v for k, v in meta.items() if v is not None},
        }
        self._items.appendleft(entry)
        return entry

    def list(self, limit: int = 100) -> list[dict]:
        return list(self._items)[:limit]


def alert_snapshot(*, held_escrows: int = 0, anon_quota: int = 20, stale_pending: int = 0) -> list[dict]:
    """Lightweight alert catalogue for Admin (design RB names)."""
    alerts = [
        {
            "id": "node.health.ok",
            "severity": "P3",
            "title": "节点进程存活",
            "detail": "合成本地快照；以 GET /health 为准",
        },
        {
            "id": "quota.policy",
            "severity": "P3",
            "title": "配额政策",
            "detail": f"anonymous_propose_per_day={anon_quota}",
        },
    ]
    if stale_pending:
        alerts.append(
            {
                "id": "settlement.intent.stale",
                "severity": "P2",
                "title": "settlement intent 悬挂",
                "detail": f"pending_count={stale_pending} · 见 RB-04",
            }
        )
    if held_escrows:
        alerts.append(
            {
                "id": "settlement.intent.held",
                "severity": "P2",
                "title": "mock escrow 仍 held",
                "detail": f"count={held_escrows}",
            }
        )
    return alerts
