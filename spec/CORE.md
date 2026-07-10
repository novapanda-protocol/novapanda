# NovaPanda CORE · 语义内核

> **卷**：CORE · 配套 [SPEC.md](SPEC.md) 索引  
> **关键词**：RFC 2119

本卷定义智能体之间**跨主体、无预建关系**的价值交割层核心语义：可验证交割凭证（VDC）为第一公民。

---

## 1. 身份（Identity）

- **[NP-ID-01]** Agent 身份 MUST 为 Ed25519 公钥；`agent_id` = `"ed25519:" + base58(pubkey)`。
- **[NP-ID-02]** 私钥 MUST 仅存于本地，MUST NOT 上送任何节点。
- **[NP-ID-03]** 任何一方仅凭对端 `agent_id` 即可验签，**无需预建关系**。

## 2. 规范化与密码学

- **[NP-CAN-01]** 规范化 JSON MUST：键按 Unicode 码点排序、紧凑分隔符、字符串 NFC、UTF-8。
- **[NP-CAN-02]** v0 MUST NOT 使用浮点数；小数以字符串承载。
- **[NP-CAN-03]** 哈希 MUST 为 SHA-256，`sha256:<hex>`。
- **[NP-CAN-04]** 签名 MUST 为 Ed25519，base64url（无填充）。

### 2.1 VDC 签名范围

- **[NP-VDC-01]** `state` MUST NOT 进入签名。
- **[NP-VDC-02]** `provider_sig` = Ed25519( canonical( VDC 去掉 `signatures`、`state` ) )。
- **[NP-VDC-03]** `client_sig` = Ed25519( canonical( VDC 去掉 `state`、`signatures.client_sig` ) )。
- **[NP-VDC-04]** VDC MUST 符合 [`schemas/vdc.schema.json`](schemas/vdc.schema.json)。

## 3. 交换状态机

```
PROPOSED → CONTRACTED → ESCROWED → DELIVERED → VERIFIED → SETTLED
   │            │           │           │
   ├────────────┴───────────┴──→ CANCELLED / EXPIRED_REFUNDED
                                  DELIVERED → REJECTED
                                  VERIFIED  → DISPUTED → SETTLED / REJECTED
```

- **[NP-SM-01]** 终态无出边。
- **[NP-SM-02]** 非法转移 MUST 拒绝。
- **[NP-SM-03]** 退款终态 MUST 触发已冻结资金退款语义。

## 4. 验收

- **[NP-VF-01]** 验收与价格解耦。
- **[NP-VF-02]** 给定 `(deliverable, rule)` 确定性可复算。

## 5. Settlement（原则）

- **[NP-SET-01]** 协议 MUST NOT 托管资金、收协议费、发代币。  
- 适配语义见 Profile **[NP-SETTLE](../profiles/NP-SETTLE.md)**。

## 6. 信誉

- **[NP-REP-01..03]** append-only 哈希链；schema 见 `schemas/reputation-entry.schema.json`；可独立复验。

## 7. 接入面

- **[NP-SUR-01]** 接入面 MUST 仅翻译，MUST NOT 改变凭证与状态机语义。

## 8. 一致性（Conformance）

兼容当且仅当：互验、状态机、schema、确定性验收、Manifest（C7）、可选 Bundle（C8）。  
条款 ↔ Case 见 [VECTORS.md](../conformance/VECTORS.md)。

---

*CORE.md · T16 拆卷*
