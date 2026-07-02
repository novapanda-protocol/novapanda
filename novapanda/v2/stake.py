"""质押锁定 v2 运行时（可持久化；不触达真实资金）。"""



from __future__ import annotations



from datetime import datetime, timezone

from typing import Optional, Protocol



from . import witness as _witness_mod

from .witness import (

    WitnessV2NotEnabledError,

    build_stake_lock,

    validate_stake_lock,

)





class StakeStore(Protocol):

    def stake_upsert(self, stake: dict) -> None: ...

    def stake_get(self, stake_id: str) -> Optional[dict]: ...

    def stakes_for_exchange(self, exchange_id: str) -> list[dict]: ...

    def stakes_for_agent(self, agent_id: str, *, exchange_id: Optional[str] = None) -> list[dict]: ...





def _now_iso() -> str:

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")





_stakes: dict[str, dict] = {}

_store: Optional[StakeStore] = None





def bind_stake_store(store: Optional[StakeStore]) -> None:

    global _store

    _store = store





def _require_enabled() -> None:

    if not _witness_mod.WITNESS_V2_ENABLED:

        raise WitnessV2NotEnabledError("stake v2 未启用")





def _persist(doc: dict) -> dict:

    if _store is not None:

        _store.stake_upsert(doc)

    _stakes[doc["stake_id"]] = doc

    return doc





def _load(stake_id: str) -> Optional[dict]:

    if _store is not None:

        doc = _store.stake_get(stake_id)

        if doc is not None:

            _stakes[stake_id] = doc

            return doc

    return _stakes.get(stake_id)





def lock_stake(

    *,

    agent_id: str,

    amount: int,

    currency: str,

    purpose: str,

    exchange_id: Optional[str] = None,

    vdc_id: Optional[str] = None,

) -> dict:

    _require_enabled()

    doc = build_stake_lock(

        agent_id=agent_id,

        amount=amount,

        currency=currency,

        purpose=purpose,

        exchange_id=exchange_id,

        vdc_id=vdc_id,

    )

    errors = validate_stake_lock(doc)

    if errors:

        raise ValueError("; ".join(errors))

    return _persist(doc)





def get_stake(stake_id: str) -> Optional[dict]:

    return _load(stake_id)





def find_locked_stake(*, agent_id: str, exchange_id: str) -> Optional[dict]:

    if _store is not None:

        for doc in _store.stakes_for_agent(agent_id, exchange_id=exchange_id):

            if doc.get("status") == "locked":

                return doc

    for doc in _stakes.values():

        if (

            doc.get("agent_id") == agent_id

            and doc.get("exchange_id") == exchange_id

            and doc.get("status") == "locked"

        ):

            return doc

    return None





def release_stake(stake_id: str) -> dict:

    _require_enabled()

    doc = _load(stake_id)

    if doc is None:

        raise KeyError(f"未知 stake: {stake_id}")

    if doc["status"] != "locked":

        raise ValueError(f"stake 状态不可 release: {doc['status']}")

    out = {**doc, "status": "released", "released_at": _now_iso()}

    return _persist(out)





def slash_stake_record(stake: dict, *, reason: str, slashed_by: str) -> dict:

    _require_enabled()

    errors = validate_stake_lock(stake)

    if errors:

        raise ValueError("; ".join(errors))

    sid = stake["stake_id"]

    base = _load(sid) or stake

    out = dict(base)

    out["status"] = "slashed"

    out["slashed_at"] = _now_iso()

    out["slash_reason"] = reason

    out["slashed_by"] = slashed_by

    return _persist(out)





def count_locked_stakes(*, agent_id: str) -> int:
    """统计 agent 当前 locked 质押数（用于信誉 gate 见证加权）。"""
    n = 0
    if _store is not None:
        for doc in _store.stakes_for_agent(agent_id):
            if doc.get("status") == "locked":
                n += 1
        return n
    return sum(
        1
        for doc in _stakes.values()
        if doc.get("agent_id") == agent_id and doc.get("status") == "locked"
    )


def reset_stakes_for_tests() -> None:

    _stakes.clear()

