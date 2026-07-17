"""供应链编排：拍卖中标 → 子任务 VDC → 聚合交付。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from novapanda import state_machine as sm

from .dispatcher import HeuristicTaskDispatcher
from .protocols import Auctioneer, ExchangeRunner, ResultAggregator, TaskDispatcher
from .types import (
    AuctionResult,
    LegRuntime,
    OrchestrationPhase,
    OrchestrationReport,
    SubTaskGraph,
    TaskSpec,
)


@dataclass
class ConcatAggregator:
    """默认聚合：按 sub_id 排序拼接结果。"""

    def aggregate(self, *, goal_id: str, leg_results: dict[str, Any]) -> Any:
        ordered = sorted(leg_results.items(), key=lambda kv: kv[0])
        return {
            "goal_id": goal_id,
            "parts": [{"sub_id": k, "result": v} for k, v in ordered],
        }


@dataclass
class InMemoryExchangeRunner:
    """测试用 Runner：立即「交割成功」，不碰真实引擎。"""

    results: dict[str, Any] = field(default_factory=dict)
    _seq: int = 0

    def start_leg(
        self,
        *,
        sub,
        provider_agent_id: str,
        client_agent_id: str,
        price: dict,
        correlation_id: str,
    ) -> dict:
        self._seq += 1
        eid = f"ex-sim-{self._seq}"
        result = self.results.get(sub.sub_id, {"ok": True, "echo": sub.payload})
        return {
            "exchange_id": eid,
            "state": sm.SETTLED,
            "vdc_id": f"vdc-{self._seq}",
            "result": result,
            "provider": provider_agent_id,
        }

    def poll_leg(self, exchange_id: str) -> dict:
        return {"state": sm.SETTLED, "exchange_id": exchange_id}


@dataclass
class SupplyChainOrchestrator:
    """闭环编排器：split → auction → run legs（尊重 depends_on）→ aggregate。

    Exchange 生命周期交给 ``ExchangeRunner``；本类不调用 ``assert_transition``。

    For LLM / Agent Skill callers, prefer ``NovaPandaAgentSkill.invoke(
    "novapanda_run_supply_chain", ...)`` which returns a token-compact report
    or a structured ``AgentFault`` instead of raw exceptions.
    """

    dispatcher: TaskDispatcher = field(default_factory=HeuristicTaskDispatcher)
    auctioneer: Optional[Auctioneer] = None
    runner: ExchangeRunner = field(default_factory=InMemoryExchangeRunner)
    aggregator: ResultAggregator = field(default_factory=ConcatAggregator)

    def run(self, spec: TaskSpec) -> OrchestrationReport:
        """Execute one goal end-to-end.

        Parameters
        ----------
        spec:
            Structured ``TaskSpec`` (goal_id, resource_type, integer budget,
            client_agent_id, optional steps/tags). Do not pass raw tx hex.

        Returns
        -------
        OrchestrationReport
            Includes phase, graph, auction awards, per-leg states, optional bundle_view.
            On failure ``phase`` is FAILED and ``error`` is a short string.
        """
        graph = self.dispatcher.split_task(spec)
        report = OrchestrationReport(
            goal_id=spec.goal_id,
            phase=OrchestrationPhase.SPLIT,
            graph=graph,
            auction=None,
            legs={t.sub_id: LegRuntime(sub_id=t.sub_id) for t in graph.tasks},
        )
        if self.auctioneer is None:
            report.phase = OrchestrationPhase.FAILED
            report.error = "auctioneer not configured"
            return report

        auction = self.auctioneer.hold_auction(graph, spec=spec)
        report.auction = auction
        report.phase = OrchestrationPhase.AUCTION
        if auction.unfilled:
            report.phase = OrchestrationPhase.FAILED
            report.error = f"auction unfilled: {list(auction.unfilled)}"
            return report

        awards = {a.sub_id: a for a in auction.awards}
        report.phase = OrchestrationPhase.EXECUTING
        try:
            self._execute_dag(spec, graph, awards, report)
        except Exception as exc:  # noqa: BLE001
            report.phase = OrchestrationPhase.FAILED
            report.error = str(exc)
            return report

        if any(leg.state != sm.SETTLED for leg in report.legs.values()):
            report.phase = OrchestrationPhase.FAILED
            report.error = "not all legs SETTLED"
            return report

        report.phase = OrchestrationPhase.AGGREGATING
        leg_results = {sid: leg.result for sid, leg in report.legs.items()}
        report.final_delivery = self.aggregator.aggregate(
            goal_id=spec.goal_id, leg_results=leg_results
        )
        report.bundle_view = self._to_bundle_view(spec, graph, report)
        report.phase = OrchestrationPhase.DONE
        return report

    def _execute_dag(
        self,
        spec: TaskSpec,
        graph: SubTaskGraph,
        awards: dict,
        report: OrchestrationReport,
    ) -> None:
        by_id = graph.by_id()
        done: set[str] = set()
        correlation = spec.correlation_id or spec.goal_id
        # 简单轮询就绪集（依赖均 SETTLED）
        while len(done) < len(graph.tasks):
            progressed = False
            for sub in graph.tasks:
                if sub.sub_id in done:
                    continue
                parents = sub.depends_on
                if any(report.legs[p].state != sm.SETTLED for p in parents):
                    continue
                award = awards[sub.sub_id]
                leg = report.legs[sub.sub_id]
                leg.state = "running"
                leg.provider = award.winner.agent_id
                started = self.runner.start_leg(
                    sub=sub,
                    provider_agent_id=award.winner.agent_id,
                    client_agent_id=spec.client_agent_id,
                    price={
                        "amount": award.winner.quote.price.amount,
                        "currency": award.winner.quote.price.currency,
                    },
                    correlation_id=correlation,
                )
                leg.exchange_id = started.get("exchange_id")
                state = started.get("state")
                if state not in (sm.SETTLED, sm.REJECTED) and leg.exchange_id:
                    polled = self.runner.poll_leg(leg.exchange_id)
                    state = polled.get("state", state)
                    if polled.get("vdc_id"):
                        started["vdc_id"] = polled["vdc_id"]
                    if "result" in polled:
                        started["result"] = polled["result"]
                leg.state = state or "failed"
                leg.vdc_id = started.get("vdc_id")
                leg.result = started.get("result")
                if leg.state != sm.SETTLED:
                    leg.error = f"leg ended in {leg.state}"
                    raise RuntimeError(leg.error)
                done.add(sub.sub_id)
                progressed = True
            if not progressed:
                raise RuntimeError("DAG deadlock or missing awards")

    def _to_bundle_view(
        self, spec: TaskSpec, graph: SubTaskGraph, report: OrchestrationReport
    ) -> dict:
        return {
            "bundle_version": "0.1",
            "goal_id": spec.goal_id,
            "correlation_id": spec.correlation_id or spec.goal_id,
            "title": f"autonomy:{spec.goal_id}",
            "exchange_ids": [
                leg.exchange_id
                for leg in report.legs.values()
                if leg.exchange_id
            ],
            "depends_on": graph.depends_map(),
            "success_rule": graph.success_rule,
            "vdc_ids": [leg.vdc_id for leg in report.legs.values() if leg.vdc_id],
        }


def on_terminal_leg_update(
    report: OrchestrationReport, *, exchange_id: str, state: str, vdc_id: Optional[str] = None
) -> bool:
    """供 TerminalSink / 外部观察者回写腿状态；返回是否全部终态。"""
    for leg in report.legs.values():
        if leg.exchange_id == exchange_id:
            leg.state = state
            if vdc_id:
                leg.vdc_id = vdc_id
            break
    terminal = {sm.SETTLED, sm.REJECTED, sm.EXPIRED_REFUNDED, sm.CANCELLED}
    return all(leg.state in terminal for leg in report.legs.values())
