# 多链资产结算抽象层（AgentWalletManager）

> 状态：骨架 + 内存原型 · **不进 CORE SM** · 对齐 ADR-0002（结算旁路）  
> 与 `SettlementAdapter` 关系：Wallet 管 **Agent 持仓/Gas/法币合规入口**；Exchange escrow 仍走 NP-SETTLE。

## 边界

| 层 | 职责 |
|----|------|
| `ChainAdapter` | EVM / Solana 等链适配（余额、转账、估 Gas） |
| `Paymaster` | 用 ERC-20（如 USDC）代付 Native Gas |
| `FiatComplianceGateway` | `payWithFiat` / `settleToFiat` **合规存根**（Circle/Stripe 后续） |
| `SmartAccount` | 对业务统一账户视图 |
| `AgentWalletManager` | 按 `agent_id` 管理多链账户 |

## 实现

| 组件 | 状态 |
|------|------|
| SmartAccount / AgentWalletManager / UsdcPaymaster / Fiat stub | ✅ |
| `WalletBackedSettlement` | ✅ |
| `EntryPointPaymaster4337` · `UserOperation` | ✅ |
| `SolanaFeePayer` | ✅ |
| `EvmRpcChainAdapter` · `SolanaRpcChainAdapter` · `EntryPointRpcPaymaster` | ✅ |
| `LicensedFiatComplianceGateway` · Stripe `mode=stripe` | ✅ |
| `signer_broadcast` 真链提交 | ⏳ 身体层持钥 |
