"""Agent 任务自主拆解、子任务拍卖与动态定价（上层编排，不改 CORE/RPC/Sybil）。"""

from .auctioneer import LocalPricingBidProvider, MarketplaceAuctioneer, default_auctioneer
from .dispatcher import HeuristicTaskDispatcher
from .inject import (
    ChainInjection,
    build_chain_injection_from_env,
    build_exchange_runner,
    build_orchestrator_from_env,
    env_wants_real_rails,
    make_signer_broadcast,
)
from .orchestrator import (
    ConcatAggregator,
    InMemoryExchangeRunner,
    SupplyChainOrchestrator,
    on_terminal_leg_update,
)
from .pricing import DynamicPricingEngine, PricingPolicy
from .protocols import (
    Auctioneer,
    BidProvider,
    ExchangeRunner,
    PricingEngine,
    ResultAggregator,
    TaskDispatcher,
)
from .real_runner import RealExchangeRunner
from .types import (
    AuctionResult,
    Award,
    Bid,
    BidInvitation,
    LegRuntime,
    OrchestrationPhase,
    OrchestrationReport,
    PriceQuoteSnapshot,
    PricingInput,
    SubTask,
    SubTaskGraph,
    TaskSpec,
)

__all__ = [
    "AuctionResult",
    "Auctioneer",
    "Award",
    "Bid",
    "BidInvitation",
    "BidProvider",
    "ChainInjection",
    "ConcatAggregator",
    "DynamicPricingEngine",
    "ExchangeRunner",
    "HeuristicTaskDispatcher",
    "InMemoryExchangeRunner",
    "LegRuntime",
    "LocalPricingBidProvider",
    "MarketplaceAuctioneer",
    "OrchestrationPhase",
    "OrchestrationReport",
    "PriceQuoteSnapshot",
    "PricingEngine",
    "PricingInput",
    "PricingPolicy",
    "RealExchangeRunner",
    "ResultAggregator",
    "SubTask",
    "SubTaskGraph",
    "SupplyChainOrchestrator",
    "TaskDispatcher",
    "TaskSpec",
    "build_chain_injection_from_env",
    "build_exchange_runner",
    "build_orchestrator_from_env",
    "default_auctioneer",
    "env_wants_real_rails",
    "make_signer_broadcast",
    "on_terminal_leg_update",
]
