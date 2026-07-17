# Agent 自主拆解 / 拍卖 / 定价

> 设计权威副本：[`internal/ops/NEXT_ACTIONS_CN.md`](../../internal/ops/NEXT_ACTIONS_CN.md)  
> **不修改** `state_machine` · RPC · Sybil

闭环：`TaskDispatcher` → `Auctioneer`(+ MatchRouter/ScoreEngine) → `SupplyChainOrchestrator`(+ ExchangeRunner) → Aggregate。
