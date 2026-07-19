"""DraftStore：任务中草稿；半成品不得冒充已签 VDC。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .paths import ensure_dir, read_json, atomic_write_json
from .types import DraftRecord, DraftStatus


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class DraftStore:
    def __init__(self, root: Path) -> None:
        self.root = ensure_dir(Path(root) / "drafts")
        self._index = self.root / "index.json"
        if not self._index.is_file():
            atomic_write_json(self._index, {"ids": []})

    def _path(self, draft_id: str) -> Path:
        return self.root / f"{draft_id}.json"

    def _ids(self) -> list[str]:
        return list(read_json(self._index, {"ids": []}).get("ids", []))

    def _set_ids(self, ids: list[str]) -> None:
        atomic_write_json(self._index, {"ids": ids})

    def create(
        self,
        *,
        agent_id: str,
        peer_id: str,
        resource_type: str,
        rule_id: str,
        intent_summary: str = "",
        meta: Optional[dict[str, Any]] = None,
    ) -> DraftRecord:
        now = _now()
        rec = DraftRecord(
            draft_id="draft-" + uuid.uuid4().hex[:12],
            agent_id=agent_id,
            peer_id=peer_id,
            resource_type=resource_type,
            rule_id=rule_id,
            intent_summary=intent_summary,
            created_at=now,
            updated_at=now,
            meta=dict(meta or {}),
        )
        atomic_write_json(self._path(rec.draft_id), rec.to_dict())
        ids = self._ids()
        ids.append(rec.draft_id)
        self._set_ids(ids)
        return rec

    def get(self, draft_id: str) -> DraftRecord:
        data = read_json(self._path(draft_id))
        if data is None:
            raise KeyError(f"未知草稿: {draft_id}")
        return DraftRecord.from_dict(data)

    def list(
        self,
        *,
        status: Optional[str] = None,
        peer_id: Optional[str] = None,
    ) -> list[DraftRecord]:
        out: list[DraftRecord] = []
        for did in self._ids():
            try:
                rec = self.get(did)
            except KeyError:
                continue
            if status and rec.status != status:
                continue
            if peer_id and rec.peer_id != peer_id:
                continue
            out.append(rec)
        return out

    def set_deliverable(self, draft_id: str, deliverable: dict[str, Any]) -> DraftRecord:
        rec = self.get(draft_id)
        if rec.status in (DraftStatus.COMMITTED.value, DraftStatus.DISCARDED.value):
            raise ValueError(f"草稿已结束: {rec.status}")
        rec.deliverable = dict(deliverable)
        rec.status = DraftStatus.READY.value
        rec.updated_at = _now()
        atomic_write_json(self._path(draft_id), rec.to_dict())
        return rec

    def bind_exchange(self, draft_id: str, exchange_id: str) -> DraftRecord:
        rec = self.get(draft_id)
        rec.exchange_id = exchange_id
        rec.updated_at = _now()
        atomic_write_json(self._path(draft_id), rec.to_dict())
        return rec

    def mark_committed(self, draft_id: str) -> DraftRecord:
        rec = self.get(draft_id)
        if rec.deliverable is None:
            raise ValueError("无交付物，不能 commit")
        rec.status = DraftStatus.COMMITTED.value
        rec.updated_at = _now()
        atomic_write_json(self._path(draft_id), rec.to_dict())
        return rec

    def discard(self, draft_id: str) -> DraftRecord:
        rec = self.get(draft_id)
        rec.status = DraftStatus.DISCARDED.value
        rec.updated_at = _now()
        atomic_write_json(self._path(draft_id), rec.to_dict())
        return rec
