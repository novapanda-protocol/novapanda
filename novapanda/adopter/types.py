"""Adopter Runtime 共享类型。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class DraftStatus(str, Enum):
    OPEN = "open"
    READY = "ready"
    COMMITTED = "committed"
    DISCARDED = "discarded"


class OutboxOp(str, Enum):
    CONFIRM = "confirm"
    DISPUTE = "dispute"
    DELIVER = "deliver"
    VERIFY = "verify"
    CONTRACT = "contract"
    ESCROW = "escrow"


class OutboxStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


@dataclass
class DraftRecord:
    draft_id: str
    agent_id: str
    peer_id: str
    resource_type: str
    rule_id: str
    intent_summary: str
    deliverable: Optional[dict[str, Any]] = None
    exchange_id: Optional[str] = None
    status: str = DraftStatus.OPEN.value
    created_at: str = ""
    updated_at: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DraftRecord":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass
class OutboxItem:
    item_id: str
    op: str
    exchange_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = OutboxStatus.PENDING.value
    attempts: int = 0
    last_error: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "OutboxItem":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass
class VaultEntry:
    """本地持有的终态（或可导出）交割包。"""

    vdc_id: str
    exchange_id: str
    peer_id: str
    role: str  # client | provider
    state: str
    resource_type: str
    vdc: dict[str, Any]
    deliverable: Optional[dict[str, Any]] = None
    result_hash: str = ""
    stored_at: str = ""
    source: str = "local"  # local | peer_backup | import
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "VaultEntry":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})
