"""自主任务拆解 / 拍卖 / 定价 — 数据类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from novapanda.marketplace.types import MatchScoreBreakdown, PriceQuote, SlaOffer


class OrchestrationPhase(str, Enum):
    SPLIT = "split"
    AUCTION = "auction"
    EXECUTING = "executing"
    AGGREGATING = "aggregating"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class PricingInput:
    """动态定价输入快照。

    DePIN / 具身：可选 ``grid_load_ratio``（电网负荷）与 ``queue_length``（排队）
    作为复杂度变量；缺省 0 时行为与纯软件报价一致。
    """

    resource_type: str
    market_benchmark: PriceQuote
    load_ratio: float  # [0,1] 资源利用率
    token_estimate: int = 0
    step_estimate: int = 1
    effective_reputation: Optional[float] = None  # 报价方可选自报/自知声誉
    min_price: Optional[PriceQuote] = None
    max_price: Optional[PriceQuote] = None
    grid_load_ratio: float = 0.0  # [0,1] 电网负荷
    queue_length: int = 0  # 充电桩 / 泊位排队


@dataclass(frozen=True)
class PriceQuoteSnapshot:
    """结构化报价 + SLA + 可解释因子。"""

    price: PriceQuote
    sla: SlaOffer
    complexity_factor: float
    load_factor: float
    reputation_factor: float
    rationale: str


@dataclass(frozen=True)
class TaskSpec:
    """委托方大任务。"""

    goal_id: str
    resource_type: str
    payload: Any
    budget: PriceQuote
    client_agent_id: str
    max_response_ms: int = 60_000
    required_tags: tuple[str, ...] = ()
    # 可选显式步骤；缺省时由 Dispatcher 按 payload 启发式拆
    steps: tuple[dict[str, Any], ...] = ()
    correlation_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SubTask:
    sub_id: str
    resource_type: str
    payload: Any
    depends_on: tuple[str, ...] = ()
    token_estimate: int = 0
    step_estimate: int = 1
    required_tags: tuple[str, ...] = ()
    rule_id_hint: Optional[str] = None


@dataclass(frozen=True)
class SubTaskGraph:
    goal_id: str
    tasks: tuple[SubTask, ...]
    success_rule: str = "all_settled"

    def depends_map(self) -> dict[str, list[str]]:
        return {t.sub_id: list(t.depends_on) for t in self.tasks}

    def by_id(self) -> dict[str, SubTask]:
        return {t.sub_id: t for t in self.tasks}


@dataclass(frozen=True)
class BidInvitation:
    """参数化询价（非 NL）。"""

    sub_id: str
    resource_type: str
    token_estimate: int
    step_estimate: int
    max_price: PriceQuote
    max_response_ms: int
    required_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Bid:
    sub_id: str
    agent_id: str
    listing_id: Optional[str]
    quote: PriceQuoteSnapshot
    effective_reputation: float


@dataclass(frozen=True)
class Award:
    sub_id: str
    winner: Bid
    breakdown: MatchScoreBreakdown
    runners_up: tuple[Bid, ...] = ()


@dataclass(frozen=True)
class AuctionResult:
    goal_id: str
    awards: tuple[Award, ...]
    unfilled: tuple[str, ...] = ()
    reason: str = ""


@dataclass
class LegRuntime:
    sub_id: str
    exchange_id: Optional[str] = None
    vdc_id: Optional[str] = None
    provider: Optional[str] = None
    state: str = "pending"  # pending|running|SETTLED|REJECTED|failed
    result: Any = None
    error: Optional[str] = None


@dataclass
class OrchestrationReport:
    goal_id: str
    phase: OrchestrationPhase
    graph: SubTaskGraph
    auction: Optional[AuctionResult]
    legs: dict[str, LegRuntime]
    final_delivery: Any = None
    bundle_view: Optional[dict] = None
    error: Optional[str] = None
