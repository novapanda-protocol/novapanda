"""MarketplaceFacade：发现 → 声誉视图 → 撮合（不含 propose）。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from .match_router import WeightedMatchRouter
from .policy import ReputationMatchPolicy
from .protocols import MatchRouter, ScoreEngine, ServiceRegistry
from .types import MatchDecision, MatchQuery


@dataclass
class DefaultMarketplaceFacade:
    """Client 一站入口；调用方再用 ``decision.winner`` 自行 ``propose``。"""

    registry: ServiceRegistry
    score_engine: ScoreEngine
    router: MatchRouter
    policy: Optional[ReputationMatchPolicy] = None

    @classmethod
    def build_default(
        cls,
        registry: ServiceRegistry,
        score_engine: ScoreEngine,
        *,
        router: MatchRouter | None = None,
        policy: ReputationMatchPolicy | None = None,
    ) -> "DefaultMarketplaceFacade":
        return cls(
            registry=registry,
            score_engine=score_engine,
            router=router or WeightedMatchRouter(),
            policy=policy,
        )

    def find_providers(self, query: MatchQuery) -> MatchDecision:
        q = query
        if self.policy is not None:
            floor = self.policy.match_min_reputation()
            if q.min_reputation < floor:
                q = replace(q, min_reputation=floor)
        listings = self.registry.discover(q)
        agent_ids = list({lst.agent_id for lst in listings})
        views = self.score_engine.views(agent_ids)
        return self.router.route(q, listings, views)
