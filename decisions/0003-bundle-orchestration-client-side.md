# ADR-0003: Bundle 编排留在客户端，节点不垄断工作流

- **状态**：Accepted  
- **日期**：2026-07-10  
- **决策者**：Steward  
- **抬 G / P**：G22 · NP-BUNDLE · UC-10/12

## 背景

物联网与多 Agent 业务常需多笔交割；若节点内置巨型工作流引擎，会破坏可替代性与「原子 VDC」联邦携带性。

## 决策

**Bundle** 组合语义由 **Composer（库优先客户端）** 编排；节点 MAY 索引 Bundle，**SHOULD NOT** 成为唯一「执行整个 Goal」的路径。每笔交换仍走完整状态机，各产一张 VDC。

## 理由

- 嵌套 A/B（巡检/尽调）已验证同构。  
- depends_on 失败可局部成功（UC-12）。  
- 排除：单 exchange 塞入多交付物冒充多 VDC。

## 后果

### 正面

- 节点可轻量；plugfest 易复现。  
- C8 向量可测 Bundle 字段。

### 负面 / 风险

- 编排逻辑分散在客户端；需 Composer 失败补偿规范（见 AA 专篇）。  
- 恶意 depends 需 C8 负向。

## 合规

- [x] 通过设计底线 Litmus  
- [x] 已同步 `spec/` 或 `profiles/`（若适用）  
- [x] 已更新 `conformance/VECTORS.md`（若适用）— C8
