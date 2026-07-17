# Profile NP-REP · 服务发现市场与动态声誉

> **版本**：0.1 · 2026-07-17  
> **状态**：规范性 Profile **草案** · 可选；默认零号 **关闭**（`NOVAPANDA_MARKETPLACE=1` 开启）  
> **依赖**：NP-MIN（VDC / 状态机）· 复用 `[NP-REP-01..03]` 信誉账本  
> **设计**：[`novapanda/marketplace/DESIGN.md`](../novapanda/marketplace/DESIGN.md)

---

## 1. 问题

陌生 Agent 需要**结构化发现与撮合**（非 NL 谈判），并把交割终态沉淀为可路由的声誉——且 **不得** 改写 CORE `state_machine.TRANSITIONS`。

---

## 2. In Scope / Out of Scope

### In Scope

- 挂牌（`ServiceListing`）注册 / 发现 / 参数化撮合  
- 动态声誉视图（金额衰减、wash/sybil 惩罚）  
- 终态 Sink（volume + risk + score invalidate）  
- Manifest `capabilities` → 挂牌投影  

### Out of Scope

- 改 CORE 状态机或用声誉分直接驱动转移  
- 托管资金 / 二清（结算仍走 NP-SETTLE）  
- 强制链上挂牌全文（链上仅 MAY 存 commitment）  

---

## 3. 规范性要求

### 3.1 MUST

1. **[NP-REP-M1]** 宣告本档的实现 MUST NOT 调用交换状态机非法转移；市场层仅在 `propose` 之前与终态旁路运作。  
2. **[NP-REP-M2]** 声誉写入 MUST 对齐 `reputation-entry.schema.json` outcome 枚举；终态旁路 SHOULD 复用节点已有 `ReputationLog`。  
3. **[NP-REP-M3]** 挂牌正文 MUST 可映射 [`service-listing.schema.json`](../spec/schemas/service-listing.schema.json)。  
4. **[NP-REP-M4]** 撮合输出（`MatchDecision`）MUST NOT 自动 `escrow`/`settle`；由 Client 自行发起交换。  

### 3.2 SHOULD

- **[NP-REP-B1]** 支持金额衰减权重与 wash/sybil 惩罚（见 `DynamicScoreEngine`）。  
- **[NP-REP-B2]** 同一 `exchange_id` 终态 Sink MUST 幂等。  
- **[NP-REP-B3]** Agent Manifest 验签通过后 MAY 投影为挂牌。  

### 3.3 MAY

- 链上 `ListingCommitment` 索引  
- HTTP `GET /marketplace/discover` · `POST /marketplace/listings`  

---

## 4. Manifest

```json
{
  "profiles": ["NP-MIN", "NP-NODE", "NP-REP"],
  "features": { "marketplace": true }
}
```

---

## 5. 参考实现

- Python：`novapanda.marketplace` · 零号 `NOVAPANDA_MARKETPLACE=1`  
- 流程：[`docs/marketplace-flow.md`](../docs/marketplace-flow.md)
