"""VDC 自动化验证与结算：架构说明（原型）

## 链下验证 × 链上结算

```
Agent A (client)          Verification Gateway           Agent B (provider)
     |                            |                              |
     |---- Create (propose/      |                              |
     |     contract/escrow) ---->|  optional createVDC (EVM)     |
     |                            |<---- Proof/Output -----------|
     |                            |  Local / Docker / TEE        |
     |                            |  → VerificationCredential    |
     |                            |---- fulfill + verify ------->|
     |---- Settle (confirm) ----->|  settlePayment / adapter     |
     |<======= Archive: dual-signed VDC + credential ===========|
```

- **CORE 状态机**（权威）：`PROPOSED→…→SETTLED`，见 `novapanda.state_machine`
- **结算轨**（旁路，ADR-0002）：Mock / x402 / **EVM `VDCSettlement`**
- **VDC 双签**：交割事实；**VerificationCredential**：独立验收见证（可 quorum）

## 反「黑吃黑」

1. 资金先 escrow，验收凭证与双签齐备才 settle  
2. `result_hash` content-addressed，网关复算不一致即拒  
3. 离线 `reverify` / 多后端（Schema · Docker · TEE）可交叉验证  
4. 争议：`VERIFIED→DISPUTED→resolve`；链上 `initiateDispute` + 仲裁人  

## 反单点故障

1. 网关可替换；节点不持有 Agent 私钥  
2. 超时 **permissionless** `refundIfTimedOut` / `ExchangeEngine.sweep` / `expire`  
3. capture-before-execute 结算意图可 recover  

## 映射表

| 叙事 | CORE | EVM rail |
|------|------|----------|
| Create | → ESCROWED | `createVDC` |
| Verify | DELIVERED→VERIFIED | `fulfillVDCWithProof` |
| Settle | → SETTLED | `settlePayment` |
| Archive | 终态 VDC | 事件日志 + 链下归档包 |
"""
