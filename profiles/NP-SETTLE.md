# Profile NP-SETTLE · 结算旁路适配

> **版本**：0.1 · 2026-07-08  
> **状态**：规范性 Profile 草案（旁路 · **不进 CORE 状态机**）  
> **依赖**：NP-MIN；生产真钱轨另依赖持牌/facilitator 合同（身体）  
> **配套设计**：内部《结算清算对接-国际视角》《结算清算-方法论完备》《交换结算清算-价值闭环与安全》  
> **多轨详设**：内部 [`NP-SETTLE-多轨结算能力设计.md`](../internal/design/NP-SETTLE-多轨结算能力设计.md)  
> **红线**：MUST NOT 发行协议代币；MUST NOT 对协议层按笔抽成；节点 MUST NOT 冒充清算牌照主体；对接服务费不在本 Profile 范围

---

## 1. 问题

交割完成后需要把「经济后果」接到可替换的支付/清算轨道，且：

- 异实现、异币种、异司法辖区可协商；  
- VDC（事实）与轨上资金（经济）可分离失效；  
- Agent 可在国际常见轨（x402 / AP2 / 法币…）间选择，而非绑死单一网络。

## 2. In Scope / Out of Scope

### In Scope

- 结算适配语义：`escrow` / `settle` / `refund`（及可选扩展）  
- Manifest 轨能力宣告与交叉协商  
- receipt 最小字段与幂等/崩溃语义（配合节点 recover）  
- 与 Claim（NP-CLAIM-XFER）的衔接点（reserve 证明）  

### Out of Scope

- 自建多边清算所、轧差中心、发卡行业务  
- **二清式**资金池：代收代付、备付金归集、内部余额/充值提现转账  
- KYC/AML/Travel Rule 的监管义务本身（伙伴承担；本档只要求**诚实声明**）  
- 强制全球单一货币或单一链  
- 用结算余额替代 VDC 作为交付真理  
- 发行协议代币或把封闭积分宣称为全球 NovaPanda 币  
- 自营存证链/清算节点（MAY 定义推送报文格式，MUST NOT 自充资金闭环）

---

## 2.1 分层（与外部「信息流 / 钩子 / 清算主体」对齐）

```text
CORE / 交割事实     VDC · 交换状态 · 验收 —— 无资金逻辑
PROFILE 结算钩子    NP-SETTLE：escrow / settle / refund · receipt · 轨协商
BODY / 伙伴         持牌 PSP·卡组·银行·facilitator —— 资金与轧差
```

钩子层还可扩展（身体/资料，非 CORE）：预授权校验、履约回执推送、T+n 对账导出、争议调证、多轨路由（可读取属地标签）。  
支付委托限价/周期/允许轨白名单 → **[`NP-DELEGATE`](NP-DELEGATE.md)**，不塞进状态机。

## 3. 适配器合同（规范性意图）

实现若宣告 `NP-SETTLE`，其对所选 rail MUST 提供语义等价于：

| 操作 | 含义 | 交换阶段典型触发 |
|------|------|------------------|
| `escrow(exchange_id, amount, currency) -> handle` | 锁定/预授权 | → ESCROWED |
| `settle(handle) -> receipt` | 捕获/终局付给受益方 | → SETTLED 路径 |
| `refund(handle) -> receipt` | 撤销/退回 | 退款终态 |

### 3.1 MUST

1. **[NP-SET-A1]** `amount` 不得为负；`currency` 为条款约定字符串（如 `USD`/`EUR`/`USDC`/`mock`）。  
2. **[NP-SET-A2]** `escrow`/`settle`/`refund` 对同一 `handle` **幂等安全**（重复调用不产生双花 capturre）。  
3. **[NP-SET-A3]** 节点侧 MUST 遵循 capture-before-execute：结算意图先落盘再调轨（见 SPEC）。  
4. **[NP-SET-A4]** `receipt` MUST 含：`status`（`settled`|`refunded`|…）、`rail`（轨 id）、`handle`；SHOULD 含伙伴侧 `provider_ref`。  
5. **[NP-SET-A5]** 轨失败 MUST NOT 将交换标为 SETTLED；映射为可重试或退款终态。  
6. **[NP-SET-A6]** `rail=mock` MUST 在 Manifest 明确；MUST NOT 表述为银行到账。  

### 3.2 SHOULD

- **[NP-SET-B1]** 提供轨能力探测或静态 Manifest `settlement.rails[]`。  
- **[NP-SET-B2]** 声明 `finality`（`instant`|`onchain`|`sepa_instant`|`t+0`|`t+1`|…）。  
- **[NP-SET-B3]** 慢轨（如 ACH）与交换 `timeouts` 一并文档化。  

### 3.3 MAY

- `quote`、部分捕获、多币种兑换（**须**经声明伙伴；禁止节点静默假外汇）。  
- 与 NP-CLAIM-XFER：`reservation_receipt` 作为 escrow 前置证明。  

## 4. Manifest 图式（SHOULD）

```json
{
  "profiles": ["NP-MIN", "NP-SETTLE"],
  "settlement": {
    "rails": [
      {
        "id": "mock",
        "currencies": ["USD"],
        "finality": "instant",
        "licensed": false
      },
      {
        "id": "x402",
        "currencies": ["USDC"],
        "networks": ["base"],
        "finality": "onchain",
        "licensed": false
      },
      {
        "id": "ap2",
        "currencies": ["EUR"],
        "finality": "sepa_instant_partner",
        "partner": "example-facilitator",
        "licensed": true
      }
    ]
  }
}
```

协商：双方 `rails` × `currencies` 交集为空 ⇒ 对端 MUST NOT 假设可真钱成交（拒约或明示降级，术语由实现选择但 MUST 可观测）。

## 5. 国际轨登记（informative）

非穷尽、非背书；实现可支持子集：

| rail id 建议 | 族 | 备注 |
|--------------|----|------|
| `mock` | 试验 | 零号默认 |
| `x402` | Agent/HTTP 402 | 稳定币机器支付 |
| `ap2` | Agent Payments | 常衔接银行/ISO 20022 世界 |
| `fiat` | PSP/开放银行 | `partner` 必填宜 |
| `sepa` / `fednow` / `ach` / `fps` | 法币即时或批量 | 经持牌 |
| `points` | 封闭积分 | 禁止宣称为协议币 |

跨族互付（如 x402→SEPA）MUST 经 **声明的桥/facilitator**，不得由未宣告的节点「内部记账」冒充。

## 6. Clearing

本 Profile **不**规定轧差算法或 pacs 报文。  
清算属伙伴基础设施；NovaPanda 只消费「授权/捕获/撤销」结果。

## 7. 与其他 Profile

| Profile | 关系 |
|---------|------|
| NP-MIN | 无结算轨时可用 mock 完成 Litmus |
| NP-NODE | 生产节点 SHOULD 持久化 settlement intent |
| NP-CLAIM-XFER | Claim 消耗不得无 VDC 锚；reserve 与 escrow 对齐 |
| NP-BUNDLE | 多腿可多轨；锁序见 Claim 设计，非本档强制 |

## 8. 与价值闭环

端到端「交换产出 → 结算捕获 → 清算在伙伴」见内部  
`交换结算清算-价值闭环与安全.md`。  
本 Profile 只钉适配合同；**不**规定我方对接服务费（对接收入非现行设计变量）。

## 9. 威胁与减缓（摘要）

| 威胁 | 减缓 |
|------|------|
| 假 SETTLED | A5；意图表与 receipt |
| mock 冒充真钱 | A6；表述红线 |
| 双花 capture | A2；轨侧原子 |
| 静默换轨换汇 | §5 桥声明 |
| 合规甩锅协议 | Out of Scope；Manifest `licensed` |

详版见内部方法论、闭环文 E2E 表与 SECURITY T14/T15。

## 10. 一致性（预留）

| Case | 意图 |
|------|------|
| **C10** | settle/refund 幂等；失败不假 SETTLED；mock 标识 · `tests/test_c10_settlement.py` |

通过 C1–C7 / C10 不等价于真钱合规；真钱另审伙伴（见内部 T13 沙箱方案）。  
T+n 对账列语义：内部 `T14-对账导出模板.md`（informative）。

## 11. 版本

加性演进；破坏 receipt 语义或 escrow 语义 → 大版本 + VERSIONING Breaking。

---

*NP-SETTLE 0.1 · 旁路结算国际可协商*
