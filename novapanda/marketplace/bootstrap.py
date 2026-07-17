"""组装市场运行时（Registry · Score · Facade · Sink），供零号 create_app 挂载。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .facade import DefaultMarketplaceFacade
from .match_router import WeightedMatchRouter
from .policy import ReputationMatchPolicy
from .registry import InMemoryOnChainListingIndex, InMemoryServiceRegistry
from .risk import InMemoryRiskSignalStore
from .score_engine import DynamicScoreEngine
from .sink import MarketplaceTerminalSink
from .sybil import SybilGraphDetector
from .volume import InMemoryVolumeIndex


@dataclass
class MarketplaceRuntime:
    """节点侧市场组件句柄（feature flag 开启后挂到 ``app.state``）。"""

    registry: InMemoryServiceRegistry
    volume: InMemoryVolumeIndex
    risk: InMemoryRiskSignalStore
    score_engine: DynamicScoreEngine
    sink: MarketplaceTerminalSink
    facade: DefaultMarketplaceFacade
    policy: ReputationMatchPolicy
    sybil: SybilGraphDetector
    chain_index: Optional[InMemoryOnChainListingIndex] = None


def build_marketplace_runtime(
    reputation_log: Any,
    *,
    with_chain_index: bool = True,
    policy: Optional[ReputationMatchPolicy] = None,
) -> MarketplaceRuntime:
    policy = policy or ReputationMatchPolicy()
    volume = InMemoryVolumeIndex()
    risk = InMemoryRiskSignalStore()
    score = DynamicScoreEngine(
        reputation_log=reputation_log,
        volume=volume,
        risk=risk,
    )
    sybil = SybilGraphDetector(risk=risk)
    chain = InMemoryOnChainListingIndex() if with_chain_index else None
    registry = InMemoryServiceRegistry(chain_index=chain)
    sink = MarketplaceTerminalSink(
        volume=volume,
        risk=risk,
        score_engine=score,
        write_reputation=False,
        sybil=sybil,
    )
    facade = DefaultMarketplaceFacade.build_default(
        registry,
        score,
        router=WeightedMatchRouter(cold_reputation=policy.cold_reputation),
        policy=policy,
    )
    return MarketplaceRuntime(
        registry=registry,
        volume=volume,
        risk=risk,
        score_engine=score,
        sink=sink,
        facade=facade,
        policy=policy,
        sybil=sybil,
        chain_index=chain,
    )
