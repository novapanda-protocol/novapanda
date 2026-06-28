"""ISO 15118 适配层：抽象会话 + 默认 sim 后端，可替换为真桩/OCPP 驱动。"""

from __future__ import annotations

from typing import Any, Optional, Protocol

from . import iso15118_sim as sim


class Iso15118Backend(Protocol):
    def create_session(self, *, evse_id: str = "EVSE-001") -> dict: ...
    def complete_session(self, session_id: str, *, kwh_delivered: str) -> dict: ...
    def get_session(self, session_id: str) -> Optional[dict]: ...


class SimIso15118Backend:
    """默认后端：内存 sim（plugfest / 单测）。"""

    def create_session(self, *, evse_id: str = "EVSE-001") -> dict:
        return sim.create_session(evse_id=evse_id)

    def complete_session(self, session_id: str, *, kwh_delivered: str) -> dict:
        return sim.complete_session(session_id, kwh_delivered=kwh_delivered)

    def get_session(self, session_id: str) -> Optional[dict]:
        return sim.get_session(session_id)


_backend: Iso15118Backend = SimIso15118Backend()


def bind_backend(backend: Iso15118Backend) -> None:
    global _backend
    _backend = backend


def adapter_info() -> dict:
    return {
        "adapter": "troodon/iso15118-adapter/v1",
        "backend": type(_backend).__name__,
        "sim_version": sim.SIM_VERSION,
    }


def create_session(*, evse_id: str = "EVSE-001") -> dict:
    doc = _backend.create_session(evse_id=evse_id)
    return {**doc, "adapter": adapter_info()}


def complete_session(session_id: str, *, kwh_delivered: str) -> dict:
    doc = _backend.complete_session(session_id, kwh_delivered=kwh_delivered)
    return {**doc, "adapter": adapter_info()}


def get_session(session_id: str) -> Optional[dict]:
    doc = _backend.get_session(session_id)
    if doc is None:
        return None
    return {**doc, "adapter": adapter_info()}


def build_energy_deliverable(session_id: str, *, kwh_delivered: str) -> dict:
    complete_session(session_id, kwh_delivered=kwh_delivered)
    sess = _backend.get_session(session_id)
    if sess is None:
        raise KeyError(f"未知 session: {session_id}")
    return {
        "session_id": session_id,
        "kwh_delivered": kwh_delivered,
        "meter_signature": sess["meter_signature"],
        "iso15118": {
            "adapter": adapter_info()["adapter"],
            "backend": adapter_info()["backend"],
            "evse_id": sess["evse_id"],
            "status": sess["status"],
        },
    }


def validate_deliverable(deliverable: Any) -> list[str]:
    return sim.validate_sim_deliverable(deliverable)
