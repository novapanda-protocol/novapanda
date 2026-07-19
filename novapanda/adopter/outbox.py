"""Outbox：弱网排队；恢复后幂等重放。禁止离线伪 SETTLED。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from .paths import ensure_dir, read_json, atomic_write_json
from .types import OutboxItem, OutboxOp, OutboxStatus


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


FlushHandler = Callable[[OutboxItem], Any]


class Outbox:
    def __init__(self, root: Path) -> None:
        self.root = ensure_dir(Path(root) / "outbox")
        self._index = self.root / "index.json"
        if not self._index.is_file():
            atomic_write_json(self._index, {"ids": []})
        self.network_up: bool = True

    def partition(self) -> None:
        """模拟断网。"""
        self.network_up = False

    def restore(self) -> None:
        self.network_up = True

    def _path(self, item_id: str) -> Path:
        return self.root / f"{item_id}.json"

    def _ids(self) -> list[str]:
        return list(read_json(self._index, {"ids": []}).get("ids", []))

    def _set_ids(self, ids: list[str]) -> None:
        atomic_write_json(self._index, {"ids": ids})

    def enqueue(
        self,
        op: OutboxOp | str,
        exchange_id: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> OutboxItem:
        now = _now()
        item = OutboxItem(
            item_id="ob-" + uuid.uuid4().hex[:12],
            op=op.value if isinstance(op, OutboxOp) else str(op),
            exchange_id=exchange_id,
            payload=dict(payload or {}),
            created_at=now,
            updated_at=now,
        )
        atomic_write_json(self._path(item.item_id), item.to_dict())
        ids = self._ids()
        ids.append(item.item_id)
        self._set_ids(ids)
        return item

    def get(self, item_id: str) -> OutboxItem:
        data = read_json(self._path(item_id))
        if data is None:
            raise KeyError(f"未知 outbox: {item_id}")
        return OutboxItem.from_dict(data)

    def list_pending(self) -> list[OutboxItem]:
        out: list[OutboxItem] = []
        for iid in self._ids():
            try:
                item = self.get(iid)
            except KeyError:
                continue
            if item.status == OutboxStatus.PENDING.value:
                out.append(item)
        return out

    def _save(self, item: OutboxItem) -> None:
        item.updated_at = _now()
        atomic_write_json(self._path(item.item_id), item.to_dict())

    def flush(self, handler: FlushHandler, *, max_items: int = 100) -> list[dict[str, Any]]:
        """网络恢复后重放 pending；handler 抛错则标记 failed 并继续。"""
        if not self.network_up:
            raise RuntimeError("网络仍断开，拒绝 flush（禁止离线伪终态）")
        results: list[dict[str, Any]] = []
        for item in self.list_pending()[:max_items]:
            item.attempts += 1
            try:
                result = handler(item)
                item.status = OutboxStatus.DONE.value
                item.last_error = ""
                self._save(item)
                results.append({
                    "item_id": item.item_id,
                    "op": item.op,
                    "exchange_id": item.exchange_id,
                    "ok": True,
                    "result": result,
                })
            except Exception as exc:  # noqa: BLE001 — 队列项隔离失败
                item.status = OutboxStatus.FAILED.value
                item.last_error = str(exc)
                self._save(item)
                results.append({
                    "item_id": item.item_id,
                    "op": item.op,
                    "exchange_id": item.exchange_id,
                    "ok": False,
                    "error": str(exc),
                })
        return results
