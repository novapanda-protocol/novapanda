# ADR-0002: 结算作为适配器，不进 CORE 状态机

- **状态**：Accepted  
- **日期**：2026-07-10  
- **决策者**：Steward  
- **抬 G / P**：G15 · CHARTER Out of Scope · P8

## 背景

交换状态机需稳定跨行业；若把 Stripe/法币/x402 细节塞进 CORE，会破坏最小内核与多轨协商。

## 决策

结算语义为 **适配器层**（`NP-SETTLE` Profile + rail registry）：CORE 只规定 escrow/settle/refund **意图**与 receipt 挂接；具体资金移动由伙伴实现。

## 理由

- 牌照义务不可由协议承担。  
- mock/sandbox/live 可诚实宣告（Manifest `environment`）。  
- 排除：CORE MUST 绑定单一 PSP。

## 后果

### 正面

- 多轨共存；Trial 零摩擦 mock。  
- UC-41 伙伴对接可迭代。

### 负面 / 风险

- F-rail 关停时 Claim 不可用（UC-24）；需用户教育。  
- 对账形状靠 T14 与身体导出。

## 合规

- [x] 通过设计底线 Litmus  
- [x] 已同步 `spec/` 或 `profiles/`（若适用）  
- [x] 已更新 `conformance/VECTORS.md`（若适用）— C10
