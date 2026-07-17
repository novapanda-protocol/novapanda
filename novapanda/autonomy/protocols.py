"""自主拆解 / 拍卖 / 编排 — Protocol（不碰 CORE SM / RPC / Sybil）。"""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

from .types import (
    AuctionResult,
    Bid,
    BidInvitation,
    OrchestrationReport,
    PriceQuoteSnapshot,
    PricingInput,
    SubTask,
    SubTaskGraph,
    TaskSpec,
)


@runtime_checkable
class PricingEngine(Protocol):
    def quote(self, inp: PricingInput) -> PriceQuoteSnapshot: ...


@runtime_checkable
class TaskDispatcher(Protocol):
    def split_task(self, spec: TaskSpec) -> SubTaskGraph: ...


@runtime_checkable
class BidProvider(Protocol):
    """候选 Agent 的询价回调；测试可注入固定报价。"""

    def bid(self, invitation: BidInvitation, agent_id: str, listing_id: Optional[str]) -> Optional[Bid]:
        ...


@runtime_checkable
class Auctioneer(Protocol):
    def hold_auction(self, graph: SubTaskGraph, *, spec: TaskSpec) -> AuctionResult: ...


@runtime_checkable
class ExchangeRunner(Protocol):
    """把中标子任务交给既有 VDC 流水线；实现方可包装 ExchangeEngine。"""

    def start_leg(
        self,
        *,
        sub: SubTask,
        provider_agent_id: str,
        client_agent_id: str,
        price: dict,
        correlation_id: str,
    ) -> dict:
        """返回 {exchange_id, state?, vdc_id?, result?}；至少含 exchange_id。"""
        ...

    def poll_leg(self, exchange_id: str) -> dict:
        """返回 {state, vdc_id?, result?}。"""
        ...


@runtime_checkable
class ResultAggregator(Protocol):
    def aggregate(self, *, goal_id: str, leg_results: dict[str, Any]) -> Any: ...
