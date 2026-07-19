"""到场巡检 Bundle 编排（M5）· S-nested-site-patrol。

一笔业务四张 VDC：车到场 → 无人机 → 机器人 → 可选充电。
编排在客户端；节点不垄断工作流（NP-BUNDLE / ADR-0003）。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from ..bundle import (
    bundle_ready,
    topological_order,
    validate_bundle,
    validate_prior_vdc_refs,
)
from .charge import AvChargeLoop, ChargeControlAdapter, DEFAULT_ENERGY_PRICE
from .constants import ENERGY_RESOURCE, ENERGY_RULE
from .meter import MeterAdapter
from .runtime import AdopterRuntime

LEG_ARRIVAL = "leg_arrival"
LEG_DRONE = "leg_drone"
LEG_ROBOT = "leg_robot"
LEG_CHARGE = "leg_charge"

TASK_RESOURCE = "service.task.generic"
TASK_RULE = "R-task-status-v1"
ROBOT_RESOURCE = "actuation.robot.task"
ROBOT_RULE = "R-actuation-task-v1"
DEFAULT_TASK_PRICE = {"amount": 80, "currency": "USD"}
DEFAULT_ROBOT_PRICE = {"amount": 500, "currency": "USD"}


@dataclass
class LegOutcome:
    leg_id: str
    exchange_id: str
    vdc_id: str
    vdc: dict[str, Any]
    deliverable: dict[str, Any]
    state: str = "SETTLED"
    provider_id: str = ""
    resource_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "leg_id": self.leg_id,
            "exchange_id": self.exchange_id,
            "vdc_id": self.vdc_id,
            "state": self.state,
            "provider_id": self.provider_id,
            "resource_type": self.resource_type,
            "deliverable": self.deliverable,
            "vdc": self.vdc,
        }


@dataclass
class SitePatrolBundle:
    """Owner(client) 编排；各能力方为 provider Runtime。"""

    owner: AdopterRuntime
    gate: AdopterRuntime  # 场站到场确认
    drone: AdopterRuntime
    robot: AdopterRuntime
    pile: AdopterRuntime
    correlation_id: str = ""
    include_charge: bool = True
    task_price: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_TASK_PRICE))
    robot_price: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_ROBOT_PRICE))
    charge_price: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_ENERGY_PRICE))
    charge_control: ChargeControlAdapter = field(default_factory=ChargeControlAdapter)

    outcomes: dict[str, LegOutcome] = field(default_factory=dict)
    bundle: dict[str, Any] = field(default_factory=dict)
    human_gate_status: str = "pending"

    def __post_init__(self) -> None:
        if not self.correlation_id:
            self.correlation_id = "site-patrol-" + uuid.uuid4().hex[:10]

    def _settle_generic(
        self,
        *,
        leg_id: str,
        provider: AdopterRuntime,
        resource_type: str,
        rule_id: str,
        deliverable: dict[str, Any],
        price: dict[str, Any],
        idem_suffix: str,
        prior_refs: Optional[list[dict[str, Any]]] = None,
        intent_summary: str = "",
    ) -> LegOutcome:
        if prior_refs:
            errs = validate_prior_vdc_refs(
                prior_refs,
                resolve_vdc=lambda vid: next(
                    (o.vdc for o in self.outcomes.values() if o.vdc_id == vid), None,
                ),
                resolve_deliverable=lambda vid: next(
                    (o.deliverable for o in self.outcomes.values() if o.vdc_id == vid), None,
                ),
            )
            if errs:
                raise ValueError(f"{leg_id} prior_vdc_refs: {errs}")

        draft = provider.open_draft(
            peer_id=self.owner.agent_id,
            resource_type=resource_type,
            rule_id=rule_id,
            intent_summary=intent_summary or leg_id,
            meta={
                "correlation_id": self.correlation_id,
                "leg_id": leg_id,
                "prior_vdc_refs": prior_refs or [],
            },
        )
        ex = self.owner.client.propose(
            provider=provider.agent_id,
            resource_type=resource_type,
            quantity=1,
            rule_id=rule_id,
            price=price,
            idempotency_key=f"{self.correlation_id}:{idem_suffix}",
        )
        eid = ex["exchange_id"]
        provider.drafts.bind_exchange(draft.draft_id, eid)
        self.owner.client.contract(eid)
        provider.client.contract(eid)
        self.owner.client.escrow(
            eid, amount=int(price["amount"]), currency=str(price["currency"]),
        )
        # 交付物可带 prior / correlation 元数据（schema 允许多余字段时）
        body = dict(deliverable)
        body.setdefault("correlation_id", self.correlation_id)
        if prior_refs:
            body.setdefault("prior_vdc", prior_refs[0]["vdc_id"])
        provider.prepare_deliverable(draft.draft_id, body)
        provider.deliver_from_draft(draft.draft_id)
        verified = self.owner.verify(eid)
        if verified.get("state") == "REJECTED":
            raise RuntimeError(f"{leg_id} verify rejected: {verified.get('verify_result')}")
        settled = self.owner.confirm(eid)
        if settled.get("state") != "SETTLED":
            raise RuntimeError(f"{leg_id} not SETTLED: {settled.get('state')}")
        vdc = settled["vdc"]
        self.owner.remember_settled(
            eid, role="client", deliverable=body, peer_id=provider.agent_id,
        )
        provider.remember_settled(
            eid, role="provider", deliverable=body, peer_id=self.owner.agent_id,
        )
        out = LegOutcome(
            leg_id=leg_id,
            exchange_id=eid,
            vdc_id=vdc["vdc_id"],
            vdc=vdc,
            deliverable=body,
            provider_id=provider.agent_id,
            resource_type=resource_type,
        )
        self.outcomes[leg_id] = out
        return out

    def run_arrival(self) -> LegOutcome:
        return self._settle_generic(
            leg_id=LEG_ARRIVAL,
            provider=self.gate,
            resource_type=TASK_RESOURCE,
            rule_id=TASK_RULE,
            deliverable={"status": "done", "score": "A", "event": "vehicle_on_site"},
            price=self.task_price,
            idem_suffix="arrival",
            intent_summary="车到场确认",
        )

    def run_drone(self) -> LegOutcome:
        prior = self.outcomes[LEG_ARRIVAL]
        return self._settle_generic(
            leg_id=LEG_DRONE,
            provider=self.drone,
            resource_type=TASK_RESOURCE,
            rule_id=TASK_RULE,
            deliverable={
                "status": "done",
                "score": "A",
                "event": "uav_inspect",
                "findings": "clear",
            },
            price=self.task_price,
            idem_suffix="drone",
            prior_refs=[{
                "vdc_id": prior.vdc_id,
                "claim": "vehicle_on_site",
                "required": True,
            }],
            intent_summary="无人机巡检",
        )

    def run_robot(self) -> LegOutcome:
        prior = self.outcomes[LEG_DRONE]
        return self._settle_generic(
            leg_id=LEG_ROBOT,
            provider=self.robot,
            resource_type=ROBOT_RESOURCE,
            rule_id=ROBOT_RULE,
            deliverable={
                "task_id": f"handoff-{self.correlation_id[-8:]}",
                "completion_proof": f"proof-{prior.vdc_id[:12]}",
                "duration_secs": 90,
            },
            price=self.robot_price,
            idem_suffix="robot",
            prior_refs=[{
                "vdc_id": prior.vdc_id,
                "claim": "inspection_passed",
                "required": True,
            }],
            intent_summary="机器人接点交接",
        )

    def run_charge(self, *, kwh_delivered: str = "6.000") -> LegOutcome:
        MeterAdapter.reset_sim()
        priors = [
            {"vdc_id": self.outcomes[LEG_ARRIVAL].vdc_id, "required": True},
            {"vdc_id": self.outcomes[LEG_ROBOT].vdc_id, "required": True},
        ]
        errs = validate_prior_vdc_refs(
            priors,
            resolve_vdc=lambda vid: next(
                (o.vdc for o in self.outcomes.values() if o.vdc_id == vid), None,
            ),
            resolve_deliverable=lambda vid: next(
                (o.deliverable for o in self.outcomes.values() if o.vdc_id == vid), None,
            ),
        )
        if errs:
            raise ValueError(f"charge prior_vdc_refs: {errs}")

        loop = AvChargeLoop(
            car=self.owner,
            pile=self.pile,
            control=self.charge_control,
            price=self.charge_price,
        )
        loop.open_charge_intent(
            target_kwh=kwh_delivered,
            idempotency_key=f"{self.correlation_id}:charge",
            vehicle_label=self.correlation_id,
        )
        loop.run_physical_session(kwh_delivered=kwh_delivered)
        settled = loop.settle(offline_confirm=False, mutual_backup=True)
        if settled["state"] != "SETTLED":
            raise RuntimeError(f"charge not SETTLED: {settled}")
        vdc = settled["vdc"]
        assert loop.exchange_id and loop.deliverable and vdc
        out = LegOutcome(
            leg_id=LEG_CHARGE,
            exchange_id=loop.exchange_id,
            vdc_id=vdc["vdc_id"],
            vdc=vdc,
            deliverable=dict(loop.deliverable),
            provider_id=self.pile.agent_id,
            resource_type=ENERGY_RESOURCE,
        )
        self.outcomes[LEG_CHARGE] = out
        return out

    def run_all(self, *, kwh_delivered: str = "6.000") -> dict[str, Any]:
        self.run_arrival()
        self.run_drone()
        self.run_robot()
        if self.include_charge:
            self.run_charge(kwh_delivered=kwh_delivered)
        return self.finalize_bundle()

    def finalize_bundle(self, *, human_approve: bool = True) -> dict[str, Any]:
        leg_ids = [LEG_ARRIVAL, LEG_DRONE, LEG_ROBOT]
        if self.include_charge and LEG_CHARGE in self.outcomes:
            leg_ids.append(LEG_CHARGE)
        missing = [x for x in leg_ids if x not in self.outcomes]
        if missing:
            raise RuntimeError(f"缺少腿结果: {missing}")

        # 占位 leg_id → 真实 exchange_id 映射后的 Bundle
        id_map = {lid: self.outcomes[lid].exchange_id for lid in leg_ids}
        real_ids = [id_map[lid] for lid in leg_ids]
        depends: dict[str, list[str]] = {
            id_map[LEG_DRONE]: [id_map[LEG_ARRIVAL]],
            id_map[LEG_ROBOT]: [id_map[LEG_DRONE]],
        }
        if self.include_charge and LEG_CHARGE in id_map:
            depends[id_map[LEG_CHARGE]] = [id_map[LEG_ROBOT]]

        if human_approve:
            self.human_gate_status = "approved"
        gate = {
            "required": True,
            "agent_id": self.owner.agent_id,
            "status": self.human_gate_status,
            "note": "目标完成声明闸；不回滚已签 VDC",
        }
        bundle = {
            "bundle_version": "0.1",
            "goal_id": f"goal-{self.correlation_id}",
            "correlation_id": self.correlation_id,
            "title": "到场巡检闭环",
            "catalog_id": "S-nested-site-patrol",
            "exchange_ids": real_ids,
            "depends_on": depends,
            "success_rule": "all_settled",
            "human_gate": gate,
            "vdc_ids": [self.outcomes[lid].vdc_id for lid in leg_ids],
            "leg_map": {
                lid: {
                    "exchange_id": self.outcomes[lid].exchange_id,
                    "vdc_id": self.outcomes[lid].vdc_id,
                    "resource_type": self.outcomes[lid].resource_type,
                    "provider_id": self.outcomes[lid].provider_id,
                }
                for lid in leg_ids
            },
            "profiles_hint": ["NP-MIN", "NP-BUNDLE", "NP-PHYS"],
        }
        errs = validate_bundle(bundle)
        if errs:
            raise ValueError(f"bundle invalid: {errs}")
        order = topological_order(bundle)
        states = {eid: "SETTLED" for eid in real_ids}
        ready = bundle_ready(bundle, exchange_states=states)
        self.bundle = bundle
        return {
            "bundle": bundle,
            "order": order,
            "bundle_ready": ready,
            "human_gate": gate,
            "legs": {lid: self.outcomes[lid].to_dict() for lid in leg_ids},
        }
