"""服务发现市场与动态声誉 — Protocol 契约（无实现体）。

风格对齐：``VerificationBackend`` / ``SettlementAdapter`` / ``StakeStore`` —
用 ``typing.Protocol`` 描述能力，实现可替换。

与 VDC 状态机边界：
- Registry / MatchRouter / ScoreEngine：**禁止**调用 ``state_machine.assert_transition``
- ReputationEventSink：仅消费 ``ExchangeTerminalSnapshot``，委托现有 ``ReputationLog``
- ReputationGatePort：只读；失败由节点层返回 ``E_REPUTATION_LOW``
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from .types import (
    ExchangeTerminalSnapshot,
    GateResultDict,
    ListingCommitment,
    MatchDecision,
    MatchQuery,
    ReputationView,
    RiskSignal,
    ServiceListing,
)


@runtime_checkable
class ListingCache(Protocol):
    """链下高并发挂牌缓存。"""

    def upsert(self, listing: ServiceListing) -> None: ...

    def get(self, listing_id: str) -> Optional[ServiceListing]: ...

    def delete(self, listing_id: str) -> None: ...

    def find_by_resource(
        self,
        resource_type: str,
        *,
        tags: tuple[str, ...] = (),
        limit: int = 50,
    ) -> list[ServiceListing]: ...


@runtime_checkable
class OnChainListingIndex(Protocol):
    """可选链上索引：只存 commitment，防篡改与过期。"""

    def publish(self, commitment: ListingCommitment) -> str:
        """返回 tx / anchor ref。"""
        ...

    def get(self, listing_id: str) -> Optional[ListingCommitment]: ...

    def revoke(self, listing_id: str, *, by_agent_id: str) -> None: ...


@runtime_checkable
class ServiceRegistry(Protocol):
    """轻量服务注册表：挂牌生命周期 + 发现入口。"""

    def register(self, listing: ServiceListing) -> ServiceListing: ...

    def update(self, listing: ServiceListing) -> ServiceListing: ...

    def revoke(self, listing_id: str, *, by_agent_id: str) -> None: ...

    def get(self, listing_id: str) -> Optional[ServiceListing]: ...

    def discover(self, query: MatchQuery) -> list[ServiceListing]:
        """按 resource_type / tags / 价格上限等过滤；不做最终排序加权。"""
        ...


@runtime_checkable
class MatchRouter(Protocol):
    """参数化竞价撮合（无 NL）。输入已发现挂牌 + 声誉视图 → 有序决策。"""

    def route(
        self,
        query: MatchQuery,
        listings: list[ServiceListing],
        views: dict[str, ReputationView],
    ) -> MatchDecision: ...


@runtime_checkable
class ScoreEngine(Protocol):
    """动态声誉：只读派生，不写 Exchange / 不改 SM。"""

    def view(self, agent_id: str) -> ReputationView: ...

    def views(self, agent_ids: list[str]) -> dict[str, ReputationView]: ...

    def invalidate(self, agent_id: str) -> None:
        """账本或风险信号更新后丢弃缓存。"""
        ...


@runtime_checkable
class RiskSignalStore(Protocol):
    """Sybil / 刷单等风控信号（实现阶段填量化规则）。"""

    def observe_terminal(self, snap: ExchangeTerminalSnapshot) -> list[RiskSignal]:
        """终态后增量观察；可返回空列表。"""
        ...

    def signals_for(self, agent_id: str) -> list[RiskSignal]: ...

    def penalty(self, agent_id: str) -> float:
        """聚合惩罚 ∈ [0,1]，供 ScoreEngine / MatchRouter 使用。"""
        ...


@runtime_checkable
class ReputationEventSink(Protocol):
    """SM 终态观察者 → ReputationLog（及可选 RiskSignalStore）。

    实现时应复用 ``ReputationLog.record_settlement`` / ``record_outcome``，
    而不是另起一套 outcome 语义。
    """

    def on_terminal(self, snap: ExchangeTerminalSnapshot) -> None: ...


@runtime_checkable
class ReputationGatePort(Protocol):
    """propose/escrow 前只读门槛；语义对齐 ``novapanda.reputation_gate``。"""

    def check(self, agent_id: str, *, min_score: Optional[float] = None) -> GateResultDict: ...


@runtime_checkable
class MarketplaceFacade(Protocol):
    """Client 侧一站入口：发现 → 撮合 →（调用方自行 propose）。

    刻意不包含 ``propose``/``escrow``，避免市场层耦进 CORE。
    """

    def find_providers(self, query: MatchQuery) -> MatchDecision: ...
