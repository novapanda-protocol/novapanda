# Profile NP-MIN · 最小交割

> **版本**：0.1 · 2026-07-08  
> **目的**：通过 Litmus 的最小能力集。满足本档 ⇒ 可称实现了 NovaPanda **最小互通**（正式标仍走认证流程）。

---

## 1. 要求

实现 MUST：

1. 支持 Ed25519 `agent_id`；私钥不上送（[SPEC](../spec/SPEC.md) §身份）。  
2. 实现 VDC 规范化、SHA-256、双签；`state` 不进签名。  
3. 实现交换状态机至终态；非法转移拒绝；退款终态触发已冻结资金退款语义。  
4. 提供至少一种接入绑定（HTTP 参考 API 或等价 SDK 翻译），翻译 MUST NOT 改变语义。  
5. 验收对同一 `(deliverable, rule)` 确定性可复算（至少一种确定性 verifier）。  
6. 结算可 mock；协议 MUST NOT 强制特定真钱轨。  
7. 任意第三方可对 SETTLED VDC **独立复验**（提供或兼容 `reverify` 输入）。  

实现 SHOULD：

- 幂等键与 nonce 重放防护。  
- 通过 conformance **C1、C2、C3、C5**（见向量索引）。

实现 MAY：

- LLM judge、见证、联邦、Bundle——须另宣告对应 Profile。

---

## 2. 显式不要求

- 持久化 DB、sweep、Operator 登录、目录搜索、Claim 转让。

---

## 3. Manifest

```json
"profiles": ["NP-MIN"]
```

---

## 4. 测试挂钩

见 [conformance/VECTORS.md](../conformance/VECTORS.md) 中 NP-MIN 行。
