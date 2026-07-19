"""可插拔表计 / 充电控制适配（M4）。

默认走 ISO15118 sim；生产替换为真桩 / OCPP / 硬件表计后端。
产出仍须通过 NP-PHYS ``validate_physical_deliverable``。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from ..v3 import iso15118_adapter as iso
from ..v3.iso15118_sim import reset_sessions_for_tests
from ..v3.physical import validate_physical_deliverable
from .constants import ENERGY_RESOURCE


class MeterBackend(Protocol):
    """控制回路后端：会话启停 → 表计证据。"""

    def start(self, *, evse_id: str) -> dict[str, Any]: ...
    def finish(self, session_id: str, *, kwh_delivered: str) -> dict[str, Any]: ...
    def backend_id(self) -> str: ...


@dataclass
class Iso15118MeterBackend:
    """包装 ``novapanda.v3.iso15118_adapter``（可用 ``bind_backend`` 换真桩）。"""

    evse_id: str = "EVSE-ADOPT-01"

    def start(self, *, evse_id: str) -> dict[str, Any]:
        return iso.create_session(evse_id=evse_id or self.evse_id)

    def finish(self, session_id: str, *, kwh_delivered: str) -> dict[str, Any]:
        return iso.build_energy_deliverable(session_id, kwh_delivered=kwh_delivered)

    def backend_id(self) -> str:
        return f"iso15118:{iso.adapter_info()['backend']}"


@dataclass
class RecordingMeterBackend:
    """测试用：记录调用，委托内层后端。"""

    inner: MeterBackend = field(default_factory=Iso15118MeterBackend)
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def start(self, *, evse_id: str) -> dict[str, Any]:
        out = self.inner.start(evse_id=evse_id)
        self.calls.append(("start", {"evse_id": evse_id, "session_id": out.get("session_id")}))
        return out

    def finish(self, session_id: str, *, kwh_delivered: str) -> dict[str, Any]:
        out = self.inner.finish(session_id, kwh_delivered=kwh_delivered)
        self.calls.append(("finish", {"session_id": session_id, "kwh": kwh_delivered}))
        return out

    def backend_id(self) -> str:
        return f"recording:{self.inner.backend_id()}"


@dataclass
class MeterAdapter:
    """表计门面：backend → 校验后的 energy deliverable（无运行时脏字段）。"""

    backend: MeterBackend = field(default_factory=Iso15118MeterBackend)
    last_session_id: Optional[str] = None

    def backend_id(self) -> str:
        return self.backend.backend_id()

    def start_session(self, *, evse_id: Optional[str] = None) -> dict[str, Any]:
        eid = evse_id or getattr(self.backend, "evse_id", "EVSE-ADOPT-01")
        sess = self.backend.start(evse_id=eid)
        self.last_session_id = str(sess.get("session_id") or "")
        return sess

    def finish_session(self, session_id: str, *, kwh_delivered: str) -> dict[str, Any]:
        deliverable = dict(self.backend.finish(session_id, kwh_delivered=kwh_delivered))
        if "session_id" not in deliverable:
            deliverable["session_id"] = session_id
        errors = validate_physical_deliverable(ENERGY_RESOURCE, deliverable)
        if errors:
            raise ValueError(f"物理交付物无效: {errors}")
        return deliverable

    @staticmethod
    def reset_sim() -> None:
        reset_sessions_for_tests()
