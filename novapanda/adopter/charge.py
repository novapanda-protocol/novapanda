"""智能车 ↔ 充电桩交割适配（M2）。

控制回路（ISO 15118 sim）与交割回路（Exchange + Adopter）分离：
会话结束后才 ``deliver``；车为 client，桩为 provider。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..manifest import build_agent_manifest
from ..v3.physical import validate_physical_deliverable
from .constants import DEFAULT_ENERGY_PRICE, ENERGY_RESOURCE, ENERGY_RULE
from .meter import Iso15118MeterBackend, MeterAdapter
from .runtime import AdopterRuntime

__all__ = [
    "ENERGY_RESOURCE",
    "ENERGY_RULE",
    "DEFAULT_ENERGY_PRICE",
    "ChargeControlAdapter",
    "AvChargeLoop",
]


@dataclass
class ChargeControlAdapter:
    """充电控制：委托 MeterAdapter（默认 ISO15118 sim）。不进 Exchange SM。"""

    evse_id: str = "EVSE-ADOPT-01"
    meter: Optional[MeterAdapter] = None
    last_session_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.meter is None:
            self.meter = MeterAdapter(
                backend=Iso15118MeterBackend(evse_id=self.evse_id),
            )

    def start_session(self, *, evse_id: Optional[str] = None) -> dict[str, Any]:
        assert self.meter is not None
        sess = self.meter.start_session(evse_id=evse_id or self.evse_id)
        self.last_session_id = self.meter.last_session_id
        return sess

    def finish_session(self, session_id: str, *, kwh_delivered: str) -> dict[str, Any]:
        assert self.meter is not None
        return self.meter.finish_session(session_id, kwh_delivered=kwh_delivered)

    @staticmethod
    def validate(deliverable: dict[str, Any]) -> list[str]:
        return validate_physical_deliverable(ENERGY_RESOURCE, deliverable)

    @staticmethod
    def reset_sim() -> None:
        MeterAdapter.reset_sim()


@dataclass
class AvChargeLoop:
    """一笔车充交割：挂两侧 AdopterRuntime。"""

    car: AdopterRuntime  # client
    pile: AdopterRuntime  # provider
    control: ChargeControlAdapter = field(default_factory=ChargeControlAdapter)
    price: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_ENERGY_PRICE))
    resource_type: str = ENERGY_RESOURCE
    rule_id: str = ENERGY_RULE

    exchange_id: Optional[str] = None
    draft_id: Optional[str] = None
    deliverable: Optional[dict[str, Any]] = None
    session_id: Optional[str] = None

    def pile_manifest(self, *, exchange_endpoint: str = "http://testserver/exchanges") -> dict:
        return build_agent_manifest(
            self.pile.client.identity,
            capabilities=[{
                "resource_type": self.resource_type,
                "rules": [self.rule_id],
                "price": self.price,
                "np_phys": True,
            }],
            exchange_endpoint=exchange_endpoint,
            profiles=["NP-MIN", "NP-PHYS"],
        )

    def open_charge_intent(
        self,
        *,
        target_kwh: str,
        idempotency_key: str,
        vehicle_label: str = "",
    ) -> dict[str, Any]:
        """车侧草稿意图 + propose/contract/escrow；桩侧开交付草稿。"""
        draft = self.car.open_draft(
            peer_id=self.pile.agent_id,
            resource_type=self.resource_type,
            rule_id=self.rule_id,
            intent_summary=f"充电目标 {target_kwh} kWh",
            meta={
                "target_kwh": target_kwh,
                "vehicle_label": vehicle_label,
                "role": "car_client",
            },
        )
        pile_draft = self.pile.open_draft(
            peer_id=self.car.agent_id,
            resource_type=self.resource_type,
            rule_id=self.rule_id,
            intent_summary=f"向车交付电能 {target_kwh} kWh",
            meta={"role": "pile_provider", "target_kwh": target_kwh},
        )
        self.draft_id = pile_draft.draft_id

        ex = self.car.client.propose(
            provider=self.pile.agent_id,
            resource_type=self.resource_type,
            quantity=1,
            rule_id=self.rule_id,
            price=self.price,
            idempotency_key=idempotency_key,
        )
        eid = ex["exchange_id"]
        self.exchange_id = eid
        self.car.drafts.bind_exchange(draft.draft_id, eid)
        self.pile.drafts.bind_exchange(pile_draft.draft_id, eid)
        self.car.client.contract(eid)
        self.pile.client.contract(eid)
        self.car.client.escrow(
            eid, amount=int(self.price["amount"]), currency=str(self.price["currency"]),
        )
        return {
            "exchange_id": eid,
            "car_draft_id": draft.draft_id,
            "pile_draft_id": pile_draft.draft_id,
            "state": self.car.client.get_exchange(eid)["state"],
        }

    def run_physical_session(self, *, kwh_delivered: str) -> dict[str, Any]:
        """控制回路：启停会话 → 桩 draft 填交付物 → deliver。"""
        if not self.exchange_id or not self.draft_id:
            raise RuntimeError("须先 open_charge_intent")
        sess = self.control.start_session()
        self.session_id = sess["session_id"]
        deliverable = self.control.finish_session(
            sess["session_id"], kwh_delivered=kwh_delivered,
        )
        self.deliverable = deliverable
        self.pile.prepare_deliverable(self.draft_id, deliverable)
        delivered = self.pile.deliver_from_draft(self.draft_id)
        return {
            "session_id": self.session_id,
            "deliverable": deliverable,
            "state": delivered["state"],
            "result_hash": self.pile.deliverable_hash(deliverable),
        }

    def settle(
        self,
        *,
        offline_confirm: bool = False,
        mutual_backup: bool = True,
    ) -> dict[str, Any]:
        """车验收 + 确认（可走 Outbox）+ 双方 Vault。"""
        if not self.exchange_id or self.deliverable is None:
            raise RuntimeError("须先 run_physical_session")
        eid = self.exchange_id
        verified = self.car.verify(eid)
        if verified.get("state") == "REJECTED":
            return {
                "state": "REJECTED",
                "verify_result": verified.get("verify_result"),
                "exchange_id": eid,
            }

        flush_log: list = []
        if offline_confirm:
            self.car.outbox.partition()
            self.car.confirm(eid)
            assert self.car.client.get_exchange(eid)["state"] == "VERIFIED"
            self.car.outbox.restore()
            flush_log = self.car.flush_outbox()
        else:
            self.car.confirm(eid)

        settled = self.car.client.get_exchange(eid)
        self.car.remember_settled(
            eid, role="client", deliverable=self.deliverable, peer_id=self.pile.agent_id,
        )
        self.pile.remember_settled(
            eid, role="provider", deliverable=self.deliverable, peer_id=self.car.agent_id,
        )
        peer_pkg = None
        if mutual_backup:
            peer_pkg = self.pile.mutual_backup_export(eid)

        return {
            "state": settled["state"],
            "exchange_id": eid,
            "vdc": settled.get("vdc"),
            "verify_result": verified.get("verify_result"),
            "flush": flush_log,
            "peer_package": peer_pkg,
            "car_stats": self.car.query.stats(),
            "pile_stats": self.pile.query.stats(),
        }

    def dispute_kwh(self, reason: str = "电量不对") -> dict[str, Any]:
        if not self.exchange_id:
            raise RuntimeError("无 exchange")
        return self.car.apply_intent(self.exchange_id, f"不对：{reason}")
