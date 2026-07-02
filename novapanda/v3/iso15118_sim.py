"""ISO 15118 可测会话模拟器（非真充电桩；供 plugfest / 集成测试）。"""

from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any, Optional

SIM_VERSION = "iso15118-sim/v1"
_sessions: dict[str, dict] = {}


def _meter_signature(session_id: str, kwh: str) -> str:
    digest = hashlib.sha256(f"{session_id}:{kwh}:{SIM_VERSION}".encode()).hexdigest()
    return f"meter-sim:{digest[:32]}"


def create_session(*, evse_id: str = "EVSE-001") -> dict:
    session_id = secrets.token_hex(8)
    now = time.time()
    doc = {
        "sim_version": SIM_VERSION,
        "session_id": session_id,
        "evse_id": evse_id,
        "status": "charging",
        "started_at": now,
        "kwh_delivered": "0.000",
    }
    _sessions[session_id] = doc
    return doc


def complete_session(session_id: str, *, kwh_delivered: str) -> dict:
    sess = _sessions.get(session_id)
    if sess is None:
        raise KeyError(f"未知 session: {session_id}")
    if sess["status"] != "charging":
        raise ValueError(f"session 状态不可完成: {sess['status']}")
    out = {
        **sess,
        "status": "completed",
        "kwh_delivered": kwh_delivered,
        "completed_at": time.time(),
        "meter_signature": _meter_signature(session_id, kwh_delivered),
    }
    _sessions[session_id] = out
    return out


def get_session(session_id: str) -> Optional[dict]:
    return _sessions.get(session_id)


def build_energy_deliverable(session_id: str, *, kwh_delivered: str) -> dict:
    """完成会话并产出 energy.electric.dc deliverable。"""
    complete_session(session_id, kwh_delivered=kwh_delivered)
    sess = _sessions[session_id]
    return {
        "session_id": session_id,
        "kwh_delivered": kwh_delivered,
        "meter_signature": sess["meter_signature"],
        "iso15118": {
            "adapter": SIM_VERSION,
            "evse_id": sess["evse_id"],
            "status": sess["status"],
        },
    }


def validate_sim_deliverable(deliverable: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(deliverable, dict):
        return ["deliverable 必须为 object"]
    sid = deliverable.get("session_id")
    if not sid:
        return ["缺少 session_id"]
    sess = _sessions.get(sid)
    if sess is None:
        return []
    if sess.get("status") != "completed":
        errors.append(f"session 未完成: {sess.get('status')}")
    kwh = deliverable.get("kwh_delivered")
    if kwh is not None and str(kwh) != str(sess.get("kwh_delivered")):
        errors.append("kwh_delivered 与会话记录不一致")
    expected_sig = sess.get("meter_signature")
    if expected_sig and deliverable.get("meter_signature") != expected_sig:
        errors.append("meter_signature 与会话模拟器不一致")
    return errors


def reset_sessions_for_tests() -> None:
    _sessions.clear()
