"""Exchange 存储：可插拔持久化层。

引擎对存储不可知：默认内存（InMemoryStore），生产可换 SQLite/任意 DB。
乐观锁：每个 Exchange 带单调递增 version；每个公开操作恰好推进一次状态机（version +1），
save() 以「上一个 version」为条件更新，冲突即抛 ConcurrencyError。
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import asdict
from typing import Optional


class ConcurrencyError(Exception):
    pass


def _exchange_payload(ex) -> dict:
    """序列化 Exchange：VDC 正文不进 JSON，只留 vdc_id 引用。"""
    d = asdict(ex)
    vdc = d.get("vdc")
    if vdc:
        d["vdc_id"] = vdc.get("vdc_id")
        d["vdc"] = None
    return d


class InMemoryStore:
    def __init__(self) -> None:
        self._d: dict = {}
        self._idem: dict[str, str] = {}
        self._nonces: dict[tuple[str, str], float] = {}
        self._vdcs: dict[str, dict] = {}
        self._vdc_by_ex: dict[str, str] = {}
        self._stakes: dict[str, dict] = {}

    def vdc_upsert(self, exchange_id: str, vdc: dict) -> None:
        vid = vdc["vdc_id"]
        self._vdcs[vid] = vdc
        self._vdc_by_ex[exchange_id] = vid

    def vdc_get(self, vdc_id: str) -> Optional[dict]:
        return self._vdcs.get(vdc_id)

    def vdc_get_by_exchange(self, exchange_id: str) -> Optional[dict]:
        vid = self._vdc_by_ex.get(exchange_id)
        return self._vdcs.get(vid) if vid else None

    def _hydrate_vdc(self, ex) -> None:
        if ex.vdc is not None:
            return
        vdc = self.vdc_get_by_exchange(ex.exchange_id)
        if vdc is not None:
            ex.vdc = vdc

    def add(self, ex) -> None:
        if ex.vdc:
            self.vdc_upsert(ex.exchange_id, ex.vdc)
        self._d[ex.exchange_id] = ex
        ex._pv = ex.version

    def get(self, exchange_id: str):
        ex = self._d.get(exchange_id)
        if ex is not None:
            self._hydrate_vdc(ex)
            ex._pv = ex.version
        return ex

    def save(self, ex) -> None:
        if ex.vdc:
            self.vdc_upsert(ex.exchange_id, ex.vdc)
        self._d[ex.exchange_id] = ex
        ex._pv = ex.version

    def values(self) -> list:
        return list(self._d.values())

    def idem_get(self, key: str) -> Optional[str]:
        return self._idem.get(key)

    def idem_set(self, key: str, exchange_id: str) -> None:
        self._idem[key] = exchange_id

    def nonce_check_and_add(
        self, agent_id: str, nonce: str, *, now_ts: Optional[float] = None,
        window_secs: float = 86400,
    ) -> bool:
        now = now_ts if now_ts is not None else time.time()
        key = (agent_id, nonce)
        if key in self._nonces:
            return False
        cutoff = now - window_secs
        self._nonces = {k: v for k, v in self._nonces.items() if v >= cutoff}
        self._nonces[key] = now
        return True

    def stake_upsert(self, stake: dict) -> None:
        self._stakes[stake["stake_id"]] = stake

    def stake_get(self, stake_id: str) -> Optional[dict]:
        return self._stakes.get(stake_id)

    def stakes_for_exchange(self, exchange_id: str) -> list[dict]:
        return [s for s in self._stakes.values() if s.get("exchange_id") == exchange_id]

    def stakes_for_agent(
        self, agent_id: str, *, exchange_id: Optional[str] = None,
    ) -> list[dict]:
        out = [s for s in self._stakes.values() if s.get("agent_id") == agent_id]
        if exchange_id is not None:
            out = [s for s in out if s.get("exchange_id") == exchange_id]
        return out


class SQLiteStore:
    def __init__(self, path: str = ":memory:") -> None:
        self._cx = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.RLock()
        self._cx.execute(
            "CREATE TABLE IF NOT EXISTS exchanges("
            "id TEXT PRIMARY KEY, version INTEGER NOT NULL, data TEXT NOT NULL)"
        )
        self._cx.execute(
            "CREATE TABLE IF NOT EXISTS idem(k TEXT PRIMARY KEY, exchange_id TEXT NOT NULL)"
        )
        self._cx.execute(
            "CREATE TABLE IF NOT EXISTS nonces("
            "agent_id TEXT NOT NULL, nonce TEXT NOT NULL, seen_at REAL NOT NULL, "
            "PRIMARY KEY (agent_id, nonce))"
        )
        self._cx.execute(
            "CREATE TABLE IF NOT EXISTS vdcs("
            "vdc_id TEXT PRIMARY KEY, exchange_id TEXT NOT NULL, data TEXT NOT NULL)"
        )
        self._cx.execute(
            "CREATE INDEX IF NOT EXISTS idx_vdcs_exchange ON vdcs(exchange_id)"
        )
        self._cx.execute(
            "CREATE TABLE IF NOT EXISTS registry_types("
            "type_id TEXT PRIMARY KEY, data TEXT NOT NULL)"
        )
        self._cx.execute(
            "CREATE TABLE IF NOT EXISTS registry_rules("
            "rule_id TEXT PRIMARY KEY, data TEXT NOT NULL)"
        )
        self._cx.execute(
            "CREATE TABLE IF NOT EXISTS stakes("
            "stake_id TEXT PRIMARY KEY, exchange_id TEXT, agent_id TEXT, data TEXT NOT NULL)"
        )
        self._cx.commit()
        self.path = path

    def vdc_upsert(self, exchange_id: str, vdc: dict) -> None:
        with self._lock:
            self._cx.execute(
                "INSERT OR REPLACE INTO vdcs(vdc_id, exchange_id, data) VALUES(?,?,?)",
                (vdc["vdc_id"], exchange_id, json.dumps(vdc)),
            )
            self._cx.commit()

    def vdc_get(self, vdc_id: str) -> Optional[dict]:
        row = self._cx.execute(
            "SELECT data FROM vdcs WHERE vdc_id=?", (vdc_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def vdc_get_by_exchange(self, exchange_id: str) -> Optional[dict]:
        row = self._cx.execute(
            "SELECT data FROM vdcs WHERE exchange_id=? ORDER BY vdc_id DESC LIMIT 1",
            (exchange_id,),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def _to_ex(self, data: str):
        from .exchange import Exchange  # 延迟导入避免循环

        raw = json.loads(data)
        inline_vdc = raw.pop("vdc", None)
        vdc_id = raw.pop("vdc_id", None)
        ex = Exchange(**raw)
        if inline_vdc:
            ex.vdc = inline_vdc
        elif vdc_id:
            ex.vdc = self.vdc_get(vdc_id)
        ex._pv = ex.version
        return ex

    def _hydrate_vdc(self, ex) -> None:
        if ex.vdc is not None:
            return
        vdc = self.vdc_get_by_exchange(ex.exchange_id)
        if vdc is not None:
            ex.vdc = vdc

    def add(self, ex) -> None:
        with self._lock:
            if ex.vdc:
                self.vdc_upsert(ex.exchange_id, ex.vdc)
            self._cx.execute(
                "INSERT INTO exchanges(id, version, data) VALUES(?,?,?)",
                (ex.exchange_id, ex.version, json.dumps(_exchange_payload(ex))),
            )
            self._cx.commit()
            ex._pv = ex.version

    def get(self, exchange_id: str):
        row = self._cx.execute(
            "SELECT data FROM exchanges WHERE id=?", (exchange_id,)
        ).fetchone()
        if not row:
            return None
        ex = self._to_ex(row[0])
        self._hydrate_vdc(ex)
        return ex

    def save(self, ex) -> None:
        expected = getattr(ex, "_pv", ex.version - 1)
        with self._lock:
            if ex.vdc:
                self.vdc_upsert(ex.exchange_id, ex.vdc)
            cur = self._cx.execute(
                "UPDATE exchanges SET version=?, data=? WHERE id=? AND version=?",
                (ex.version, json.dumps(_exchange_payload(ex)), ex.exchange_id, expected),
            )
            if cur.rowcount == 0:
                raise ConcurrencyError(
                    f"乐观锁冲突：{ex.exchange_id} 期望 version={expected}"
                )
            self._cx.commit()
            ex._pv = ex.version

    def values(self) -> list:
        rows = self._cx.execute("SELECT data FROM exchanges").fetchall()
        out = [self._to_ex(r[0]) for r in rows]
        for ex in out:
            self._hydrate_vdc(ex)
        return out

    def idem_get(self, key: str) -> Optional[str]:
        row = self._cx.execute(
            "SELECT exchange_id FROM idem WHERE k=?", (key,)
        ).fetchone()
        return row[0] if row else None

    def idem_set(self, key: str, exchange_id: str) -> None:
        with self._lock:
            self._cx.execute(
                "INSERT OR REPLACE INTO idem(k, exchange_id) VALUES(?,?)",
                (key, exchange_id),
            )
            self._cx.commit()

    def nonce_check_and_add(
        self, agent_id: str, nonce: str, *, now_ts: Optional[float] = None,
        window_secs: float = 86400,
    ) -> bool:
        now = now_ts if now_ts is not None else time.time()
        with self._lock:
            self._cx.execute(
                "DELETE FROM nonces WHERE seen_at < ?", (now - window_secs,)
            )
            try:
                self._cx.execute(
                    "INSERT INTO nonces(agent_id, nonce, seen_at) VALUES(?,?,?)",
                    (agent_id, nonce, now),
                )
                self._cx.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def registry_load(self) -> Optional[tuple]:
        """从 DB 加载注册表；两表皆空时返回 None。"""
        from .registry import OntologyRegistry, RuleRegistry

        with self._lock:
            type_rows = self._cx.execute("SELECT data FROM registry_types").fetchall()
            rule_rows = self._cx.execute("SELECT data FROM registry_rules").fetchall()
        if not type_rows and not rule_rows:
            return None
        onto = OntologyRegistry()
        for row in type_rows:
            entry = json.loads(row[0])
            onto._types[entry["type_id"]] = entry
        rules = RuleRegistry()
        for row in rule_rows:
            rules.register(json.loads(row[0]))
        return onto, rules

    def registry_save(self, ontology, rules) -> None:
        with self._lock:
            for entry in ontology.list():
                self._cx.execute(
                    "INSERT OR REPLACE INTO registry_types(type_id, data) VALUES(?,?)",
                    (entry["type_id"], json.dumps(entry)),
                )
            for entry in rules.list():
                self._cx.execute(
                    "INSERT OR REPLACE INTO registry_rules(rule_id, data) VALUES(?,?)",
                    (entry["rule_id"], json.dumps(entry)),
                )
            self._cx.commit()

    def stake_upsert(self, stake: dict) -> None:
        with self._lock:
            self._cx.execute(
                "INSERT OR REPLACE INTO stakes(stake_id, exchange_id, agent_id, data) "
                "VALUES(?,?,?,?)",
                (
                    stake["stake_id"],
                    stake.get("exchange_id"),
                    stake.get("agent_id"),
                    json.dumps(stake),
                ),
            )
            self._cx.commit()

    def stake_get(self, stake_id: str) -> Optional[dict]:
        row = self._cx.execute(
            "SELECT data FROM stakes WHERE stake_id=?", (stake_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def stakes_for_exchange(self, exchange_id: str) -> list[dict]:
        rows = self._cx.execute(
            "SELECT data FROM stakes WHERE exchange_id=?", (exchange_id,)
        ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def stakes_for_agent(
        self, agent_id: str, *, exchange_id: Optional[str] = None,
    ) -> list[dict]:
        if exchange_id is None:
            rows = self._cx.execute(
                "SELECT data FROM stakes WHERE agent_id=?", (agent_id,)
            ).fetchall()
        else:
            rows = self._cx.execute(
                "SELECT data FROM stakes WHERE agent_id=? AND exchange_id=?",
                (agent_id, exchange_id),
            ).fetchall()
        return [json.loads(r[0]) for r in rows]
