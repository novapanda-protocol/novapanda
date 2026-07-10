# Profile NP-DELEGATE · 临时委托（含支付约束域）

> **版本**：0.1 · 2026-07-08  
> **状态**：规范性 Profile 草案 · **可选旁路**；**不进 CORE 状态机**  
> **依赖**：NP-MIN；支付相关约束依赖结算旁路可见性（常与 NP-SETTLE 同宣告）  
> **任务**：T10 · 命令溯源 `继续设计：NP-DELEGATE`  
> **红线**：委托 ≠ 资金账户；≠ 托管备付金；≠ Operator 登录可签交割；限价/白名单是**能力边界**，不是协议抽成

---

## 1. 问题

主体 A 希望在有限时间内，让执行面 B（子 agent、设备控制器、自动化脚本）代为：

- 发起或签署交换相关动作；和/或  
- 在约定约束下触发结算适配（escrow / settle 意图），  

且 A 可过期、可撤销，失败可审计——而不把私钥长期裸交给 B，也不在协议层开「子账户余额」。

---

## 2. In Scope / Out of Scope

### In Scope

- **委托凭证**（Delegation Credential）的最小字段与生命周期：签发、校验、过期、撤销  
- **能力范围**（scope）：允许的动作集合（如 `propose`、`contract_ack`、`escrow`、`confirm`）  
- **支付约束域**（payment constraints）：限价、周期额度、允许结算轨白名单、约束自身过期  
- Manifest 宣告与对端协商时「是否接受带委托的调用」  
- 与现有 auth（nonce / 签名头）的绑定意图（实现翻译层）  

### Out of Scope

- 节点内存放委托方可花余额 / 充值提现（二清形态）  
- 用委托凭证冒充 VDC 或替代 SETTLED 事实  
- 社交账号 OAuth 直接等于 Agent 身份（Operator ≠ Agent）  
- CORE 状态机新状态（如 `DELEGATED`）——委托是**调用鉴权旁路**  
- 强制全球统一 KYC；伙伴侧风控政策本身  

---

## 3. 对象（最小图式）

```json
{
  "delegate_version": "0.1",
  "delegation_id": "dlg_…",
  "issuer_agent_id": "ed25519:…",
  "subject_agent_id": "ed25519:…",
  "scope": ["propose", "escrow"],
  "constraints": {
    "max_amount": 100,
    "currency": "USD",
    "period": "P1D",
    "rails_allowlist": ["mock", "x402"],
    "expires_at": "2026-07-09T00:00:00Z"
  },
  "not_before": "2026-07-08T00:00:00Z",
  "expires_at": "2026-07-09T00:00:00Z",
  "revoked": false,
  "issued_at": "…",
  "issuer_sig": "…"
}
```

| 字段 | 要求 |
|------|------|
| `issuer_agent_id` | MUST：委托人；持有对应私钥签发 |
| `subject_agent_id` | MUST：被委托人；请求中呈现此身份或证明持有委托绑定密钥 |
| `scope` | MUST：显式动作白名单；空 scope ⇒ 无效 |
| `constraints.max_amount` | SHOULD：单笔上限（与 `currency` 同用）；缺省 = 无协议层限价（实现可更严） |
| `constraints.period` | SHOULD：额度重置周期（ISO-8601 duration，如 `P1D`）；与累计计数由**实现**维护 |
| `constraints.rails_allowlist` | SHOULD：允许的 `rail` id；与 NP-SETTLE Manifest 交集为空 ⇒ 不得真钱成交 |
| `constraints.expires_at` | MAY：约束域单独提前过期（≤ 委托 `expires_at`） |
| `expires_at` / `revoked` | MUST：过期或撤销后调用 MUST 拒绝 |
| `issuer_sig` | MUST：对规范化委托体（不含 `revoked` 可变广告位时，以实现规范为准）签名 |

**规范意图**：`revoked` 可由撤销清单 / 短 TTL 重取表达；破坏性大版本再钉编码细则。

---

## 4. 规范性要求

### 4.1 MUST

1. **[NP-DLG-01]** 委托过期或已撤销时，实现 MUST 拒绝其授权范围内的写操作。  
2. **[NP-DLG-02]** `scope` 未列出的动作 MUST NOT 因持有该委托而获准。  
3. **[NP-DLG-03]** 若声明了 `rails_allowlist`，结算相关调用的 `rail` MUST ∈ 白名单。  
4. **[NP-DLG-04]** 若声明了 `max_amount`+`currency`，单笔金额 MUST NOT 超过限价（币种不匹配 ⇒ 拒绝）。  
5. **[NP-DLG-05]** 委托凭证 MUST NOT 被表述为可兑付存款、协议币或节点「托管余额」。  
6. **[NP-DLG-06]** Operator 会话令牌 MUST NOT 单独作为 `issuer_sig` 的替代；交割鉴权仍是 Agent 密码学身份（或其明确绑定的委托验签）。

### 4.2 SHOULD

- **[NP-DLG-B1]** 周期额度超额时返回可区分错误码（与普通 auth 失败可分）。  
- **[NP-DLG-B2]** Manifest 声明 `delegation.supported=true` 与可选默认约束天花板。  
- **[NP-DLG-B3]** 审计日志记录 `delegation_id`（无私钥、无完整 PII）。  

### 4.3 MAY

- 嵌套委托（B 再委 C）——若实现，MUST 缩短有效 `expires_at` 且 scope ⊆ 父委托；v0.1 **不要求**。  
- 设备端短生命周期委托（配 NP-LITE / PHYS）。  

---

## 5. 与状态机 / 结算

```text
CORE 交换态 ── 不变
鉴权旁路     ── NP-DELEGATE 决定「谁可以代表谁调用」
结算钩子     ── NP-SETTLE；DELEGATE 只裁剪允许的 rail/金额
资金         ── 仍在持牌伙伴；协议不池化
```

Capture-before-execute、幂等 receipt 仍遵守 NP-SETTLE；委托失败 ≠ 假 SETTLED。

---

## 6. Manifest

```json
{
  "profiles": ["NP-MIN", "NP-SETTLE", "NP-DELEGATE"],
  "delegation": {
    "supported": true,
    "max_ttl_seconds": 86400,
    "payment_constraints": true
  }
}
```

未见 `NP-DELEGATE` ⇒ 对端 MUST NOT 假设可接受委托调用。

---

## 7. 威胁与减缓（摘要）

| 威胁 | 减缓 |
|------|------|
| 委托永久有效 | 强制 `expires_at`；短 TTL 惯例 |
| 无限额代付 | `max_amount` / `period`；实现侧计数 |
| 偷偷切到未授权轨 | `rails_allowlist` ∩ Manifest rails |
| Operator 越权签 | DLG-06；私钥不上送 |
| 把委托当账户 | DLG-05；二清禁令（NP-SETTLE） |

---

## 8. 测试（预留）

| 意图 | 说明 |
|------|------|
| 过期拒绝 | `expires_at` 后 propose/escrow → 401/403 类 |
| 超限价拒绝 | amount > max_amount |
| 轨不在白名单 | rail 不在 allowlist → 拒绝 |
| 撤销生效 | revoke 后同 delegation_id 失败 |
| 无关 scope | 仅 `propose` 的委托不可 `confirm`（按宣告） |

正式 Cx：**C12** · `tests/test_c12_delegate.py`（含撤销/周期额度/币种/HTTP 登记）。

---

## 9. 版本

加性演进；破坏 scope 语义或签名覆盖范围 → 大版本。

---

*NP-DELEGATE 0.1 · 临时委托与支付约束域 · 旁路*
