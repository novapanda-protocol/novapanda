"""Composer · Bundle 编排客户端（AA-Composer失败补偿序列）。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .bundle import bundle_ready, topological_order, validate_bundle


@dataclass
class LegResult:
    leg_id: str
    exchange_id: Optional[str] = None
    vdc_id: Optional[str] = None
    state: str = "pending"
    error: Optional[str] = None


@dataclass
class BundleRunState:
    bundle: dict[str, Any]
    exchange_states: dict[str, str] = field(default_factory=dict)
    vdc_ids: dict[str, str] = field(default_factory=dict)
    failed_legs: list[str] = field(default_factory=list)
    claim_reservations: list[dict[str, Any]] = field(default_factory=list)
    results: dict[str, LegResult] = field(default_factory=dict)


RunLegFn = Callable[[str, dict[str, Any]], LegResult]


class Composer:
    """库优先 Bundle 编排；节点不垄断工作流。"""

    def __init__(
        self,
        *,
        on_leg_failure: str = "abort_rest",
        prior_mode: str = "strict",
        gate_timeout: Optional[int] = None,
    ) -> None:
        self.on_leg_failure = on_leg_failure
        self.prior_mode = prior_mode
        self.gate_timeout = gate_timeout

    def load(self, bundle: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(bundle, dict):
            raise ValueError("bundle must be an object")
        return dict(bundle)

    def validate(self, bundle: dict[str, Any]) -> list[str]:
        return validate_bundle(bundle)

    def next_ready(self, bundle: dict[str, Any], states: dict[str, str]) -> list[str]:
        errs = validate_bundle(bundle)
        if errs:
            raise ValueError("; ".join(errs))
        order = topological_order(bundle)
        depends: dict[str, list[str]] = {
            k: list(v) for k, v in (bundle.get("depends_on") or {}).items()
        }
        ready: list[str] = []
        for leg_id in order:
            if states.get(leg_id) == "SETTLED":
                continue
            if leg_id in states and states[leg_id] in ("failed", "skipped"):
                continue
            parents = depends.get(leg_id, [])
            if all(states.get(p) == "SETTLED" for p in parents):
                ready.append(leg_id)
        return ready

    def run_leg(
        self,
        leg_id: str,
        bundle: dict[str, Any],
        *,
        run_fn: RunLegFn,
        claim_wallet: Any = None,
        claim_id: Optional[str] = None,
        exchange_id: Optional[str] = None,
    ) -> LegResult:
        """执行单腿；可选 claim reserve/capture/release。"""
        reserved = False
        try:
            if claim_wallet is not None and claim_id and exchange_id:
                claim_wallet.reserve(claim_id, for_exchange_id=exchange_id)
                reserved = True
            result = run_fn(leg_id, bundle)
            if result.state == "SETTLED":
                if claim_wallet is not None and claim_id:
                    claim_wallet.capture(claim_id)
                    reserved = False
            elif result.state in ("REJECTED", "EXPIRED_REFUNDED", "CANCELLED", "failed"):
                if claim_wallet is not None and claim_id and reserved:
                    claim_wallet.release(claim_id)
                    reserved = False
            return result
        except Exception as exc:
            if claim_wallet is not None and claim_id and reserved:
                try:
                    claim_wallet.release(claim_id)
                except Exception:
                    pass
            return LegResult(leg_id=leg_id, state="failed", error=str(exc))

    def run_all(
        self,
        bundle: dict[str, Any],
        *,
        run_fn: RunLegFn,
        claim_for_leg: Optional[Callable[[str], tuple[Any, str, str]]] = None,
    ) -> BundleRunState:
        """按拓扑序跑完全部腿；失败策略由 on_leg_failure 控制。"""
        run = BundleRunState(bundle=self.load(bundle))
        optional = set(bundle.get("optional_legs") or [])
        while True:
            ready = self.next_ready(run.bundle, run.exchange_states)
            if not ready:
                break
            for leg_id in ready:
                claim_wallet = None
                claim_id = None
                exchange_id = None
                if claim_for_leg is not None:
                    tup = claim_for_leg(leg_id)
                    if tup:
                        claim_wallet, claim_id, exchange_id = tup
                        run.claim_reservations.append(
                            {"leg_id": leg_id, "claim_id": claim_id, "exchange_id": exchange_id}
                        )
                result = self.run_leg(
                    leg_id,
                    run.bundle,
                    run_fn=run_fn,
                    claim_wallet=claim_wallet,
                    claim_id=claim_id,
                    exchange_id=exchange_id,
                )
                run.results[leg_id] = result
                if result.exchange_id:
                    run.exchange_states[leg_id] = result.state
                if result.vdc_id:
                    run.vdc_ids[leg_id] = result.vdc_id
                if result.state != "SETTLED":
                    run.failed_legs.append(leg_id)
                    if leg_id not in optional and self.on_leg_failure == "abort_rest":
                        return run
        return run

    def finalize(self, bundle: dict[str, Any], run: BundleRunState) -> dict[str, Any]:
        ready = bundle_ready(bundle, exchange_states=run.exchange_states)
        return {
            "bundle": bundle,
            "bundle_ready": ready,
            "exchange_states": dict(run.exchange_states),
            "vdc_ids": dict(run.vdc_ids),
            "failed_legs": list(run.failed_legs),
        }

    def export(self, run: BundleRunState) -> bytes:
        payload = {
            "bundle": run.bundle,
            "exchange_states": run.exchange_states,
            "vdc_ids": run.vdc_ids,
            "failed_legs": run.failed_legs,
            "claim_reservations": run.claim_reservations,
            "results": {
                k: {
                    "leg_id": v.leg_id,
                    "exchange_id": v.exchange_id,
                    "vdc_id": v.vdc_id,
                    "state": v.state,
                    "error": v.error,
                }
                for k, v in run.results.items()
            },
        }
        return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
