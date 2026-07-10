# Profile NP-CLAIM-XFER · 结算权柄转让

> **版本**：0.1 · 2026-07-08  
> **状态**：设计定稿 · **默认关闭**；实现前不得在生产 Manifest 中宣称  
> **依赖**：NP-MIN；结算旁路 MUST 可识别 `claim_id`  
> **红线**：不发行协议代币；Claim ≠ NovaPanda Coin

---

## 1. 问题

SETTLED 后，持有方希望把**结算权柄**转给下一跳对手或清算网关 redeem——体感像货币多跳，但锚定 VDC。

## 2. 对象（最小）

```json
{
  "claim_version": "0.1",
  "claim_id": "claim_…",
  "vdc_id": "vdc_…",
  "rail": "mock|x402|fiat|…",
  "holder_agent_id": "ed25519:…",
  "amount": "10.00",
  "currency": "USD",
  "status": "open",
  "issued_at": "…",
  "expires_at": null,
  "lineage": []
}
```

| 字段 | 要求 |
|------|------|
| `vdc_id` | MUST：无锚不得发行可转 Claim |
| `status` | `open` / `reserved` / `spent` / `expired` / `frozen` |
| `lineage` | 每次 assignment 追加 `{from,to,at,sig}` |

## 3. 转让（assignment）

1. 当前 holder 对 `{claim_id, to_agent_id, nonce, at}` 签名。  
2. 接收方或登记处验签后更新 `holder_agent_id` 与 `lineage`。  
3. **防双花**：同一 `claim_id` 在轨上 redeem / transfer MUST 互斥（序号或原子锁）。  

## 4. Redeem

持有方向 Settlement Partner 出示 Claim（+ 可选 VDC）；伙伴按轨规则放款/入账。  
协议不保证资金安全；轨破产时 VDC 事实仍在。

## 5. 显式禁止

- 无 VDC 的空头 Claim  
- 称 Claim 为「NovaPanda 币」或强制全球统一计量  
- 用节点私有余额冒充可转 Claim 而不宣告本 Profile  

## 6. Manifest

```json
"profiles": ["NP-MIN", "NP-CLAIM-XFER"]
```

## 7. 测试（预留）

- 无锚发行 → 拒绝  
- 双花第二次 assignment / redeem → 失败  
- 过期 Claim → 不可花；VDC 仍可复验  

---

*先成文 · 落地排在 Composer / mock Claim 流水之后*
