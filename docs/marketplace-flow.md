# 市场发现 → propose → 终态 Sink

> Implementer 一页 · NP-REP · **不改** CORE 状态机

## 流程

```text
1. Provider 挂牌（POST /marketplace/listings 或 Manifest 投影）
2. Client GET /marketplace/discover → MatchDecision.winner.agent_id
3. Client 自行 propose(provider=…) → … → SETTLED / REJECTED
4. ExchangeEngine 通知 terminal_observers
5. MarketplaceTerminalSink：记 volume · 风控 · 失效 Score 缓存
6. 下次 discover 使用更新后的 ReputationView
```

## 开启零号市场（默认关）

```bash
set NOVAPANDA_MARKETPLACE=1
# 或 create_app(..., marketplace_enabled=True)
```

开启后 Manifest `profiles` 含 `NP-REP`，`features.marketplace=true`。

## 解耦红线

| 允许 | 禁止 |
|------|------|
| 发现层选 provider | Sink / Score 调用 `assert_transition` |
| 终态旁路写 volume/risk | 市场层自动 escrow/settle |
| 复用 ReputationLog | 用声誉分改 TRANSITIONS |

## 代码入口

| 组件 | 模块 |
|------|------|
| Facade | `novapanda.marketplace.DefaultMarketplaceFacade` |
| Sink | `novapanda.marketplace.MarketplaceTerminalSink` |
| Manifest 投影 | `novapanda.marketplace.sync_manifest_to_registry` |
| Profile | [`profiles/NP-REP.md`](../profiles/NP-REP.md) |
