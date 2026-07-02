"""交付物外存：内容寻址（sha256:）+ 可选 dedup。

Exchange 只保留 `deliverable_ref`（与 VDC `result_hash` 同形），正文进 BlobStore。
遗留 `blob:{exchange_id}` ref 仍可读（兼容旧数据）。
"""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any, Optional

from .hashing import result_hash_of_json


def inline_ref(exchange_id: str) -> str:
    return f"inline:{exchange_id}"


def is_stored_ref(ref: str) -> bool:
    return ref.startswith("sha256:") or ref.startswith("blob:")


class InMemoryBlobStore:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def put(self, exchange_id: str, content: Any) -> str:
        ref = result_hash_of_json(content)
        self._data[ref] = content
        return ref

    def get(self, ref: str) -> Any:
        if ref not in self._data:
            raise KeyError(f"未知 deliverable ref: {ref}")
        return self._data[ref]

    def has(self, ref: str) -> bool:
        return ref in self._data


class SQLiteBlobStore:
    """内容寻址 blobs 表：ref = sha256(canonical(content))。"""

    def __init__(self, path: str) -> None:
        self._cx = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._cx.execute(
            "CREATE TABLE IF NOT EXISTS blobs("
            "ref TEXT PRIMARY KEY, exchange_id TEXT, data TEXT NOT NULL)"
        )
        self._cx.commit()
        self.path = path

    def put(self, exchange_id: str, content: Any) -> str:
        ref = result_hash_of_json(content)
        payload = json.dumps(content)
        with self._lock:
            self._cx.execute(
                "INSERT OR IGNORE INTO blobs(ref, exchange_id, data) VALUES(?,?,?)",
                (ref, exchange_id, payload),
            )
            self._cx.commit()
        return ref

    def get(self, ref: str) -> Any:
        row = self._cx.execute(
            "SELECT data FROM blobs WHERE ref=?", (ref,)
        ).fetchone()
        if row is None:
            raise KeyError(f"未知 deliverable ref: {ref}")
        return json.loads(row[0])

    def has(self, ref: str) -> bool:
        row = self._cx.execute(
            "SELECT 1 FROM blobs WHERE ref=?", (ref,)
        ).fetchone()
        return row is not None

    @classmethod
    def shared_with_store(cls, store) -> Optional["SQLiteBlobStore"]:
        path = getattr(store, "path", None)
        if path is None:
            return None
        return cls(path)
