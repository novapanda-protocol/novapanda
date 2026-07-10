# Implementer Guide · 实现者最短路径

> **对象**：要接 NovaPanda 的工程师（异语言/异栈欢迎）  
> **目标**：30 分钟内知道「先读什么、测什么、别踩什么」  
> **版本**：2026-07-09 · 与设计 v0 对齐  
> **兼容证明**：靠向量与 Profile，**不靠** `node.novapanda.io` 域名

---

## 1. 你在实现什么

一套**可验证交割语法**：陌生 Agent 完成交付后留下可离线复验的 **VDC**。  
不是钱包、不是链、不是持牌清算、不是工作流引擎。

成功判据（Litmus）见根目录 [`CHARTER.md`](../CHARTER.md)。

---

## 2. 阅读顺序（强制纪律）

| 序 | 读什么 | 为何 |
|----|--------|------|
| 1 | [`CHARTER.md`](../CHARTER.md) | In/Out of Scope；禁止运营账号顶替签名 |
| 2 | [`profiles/NP-MIN.md`](../profiles/NP-MIN.md) | 最小可互通档 |
| 3 | [`spec/README.md`](../spec/README.md) → [`CORE.md`](../spec/CORE.md) | 分卷规范；兼容入口 [`SPEC.md`](../spec/SPEC.md) |
| 4 | [`conformance/VECTORS.md`](../conformance/VECTORS.md) | 你必须能对上的 Case（含 C10–C12） |
| 5 | （可选）[`profiles/NP-NODE.md`](../profiles/NP-NODE.md) 等 | 仅当你宣告对应 Profile |

说明层（非 MUST）：[`docs/scenarios/`](scenarios/) · 含 [`生态八域`](scenarios/ecosystem-eight-domains.md) 公开登记。

---

## 3. 建议落地步骤

```text
① 身份：本地 Ed25519（或规范声明的算法）——私钥永不上传节点
② 规范化 + 签名：对齐 C1 向量（同语义 → 同哈希）
③ 跑通状态机主路径 → SETTLED + 双签 VDC（可对参考节点或自测）
④ 独立 reverify(VDC, deliverable) 全绿（不依赖原节点数据库）
⑤ Manifest 宣告 profiles[]；只承诺测过的档
⑥ 结算：先 mock；真轨另见 NP-SETTLE + 持牌伙伴（非 Litmus 必选项）
```

参考：Python 包 `novapanda/`、TS `sdk/typescript`、试用节点（可替代）。

```bash
python -m conformance.run --list
python -m conformance.run          # C1–C8、C10–C12（环境具备时）
python -m conformance.gap_audit    # 套件完整性
python internal/ops/release_check.py   # 发布前冒烟（T23）
```

---

## 4. 兼容等级（对外自称时用）

| 级 | 含义 | 最低证据 |
|----|------|----------|
| **L0 Client** | 能签验并对某节点完成一笔 | 自测记录 |
| **L1 MIN** | NP-MIN | 宣称并通过 **C1–C5**（C6/C7 按 Profile SHOULD） |
| **L2 NODE** | NP-NODE | L1 + recover/sweep/持久化相关检查 |
| **L3+** | 额外 Profile | 各档自洽：如 NP-BUNDLE→**C8**；NP-SETTLE→**C10**；NP-DELEGATE→**C12** |

公开实现登记表：[`compatibility.md`](compatibility.md)（欢迎 PR 自报，Steward 可复核）。

认证标识流程草案：[`conformance/CERTIFICATION.md`](../conformance/CERTIFICATION.md)。  
**自测通过 ≠ 必须向青合付费**；正式认证标另议，且不作入网闸。

---

## 5. 常见误区（禁止）

| 误区 | 正确 |
|------|------|
| 只有官方节点才算兼容 | 兼容靠向量 |
| 邮箱登录代替 Agent 签 | 永远不行 |
| mock 写成「已银行到账」 | Manifest 必须诚实 |
| Claim / 积分 = 协议币 | Charter 禁止 |
| 未交付就 capture | NP-SETTLE / 闭环：先证后付 |
| 把 MCP/工作流塞进 CORE | 只用 BINDING / 客户端编排 |

---

## 6. 版本与安全

- 变更等级：[`VERSIONING.md`](../VERSIONING.md)  
- 威胁摘要：[`SECURITY.md`](../SECURITY.md)  
- 节点上线审阅（内部）：[`SEC-OP-01`](../internal/design/SEC-OP-01-Operator禁代签检查表.md) · [`SEC-PRIV-01`](../internal/design/SEC-PRIV-01-隐私审阅检查表.md)  
- 治理与许可：[`GOVERNANCE.md`](../GOVERNANCE.md) · [`CONTRIBUTING.md`](../CONTRIBUTING.md)（DCO）

漏洞：优先私信 Steward / GitHub Security Advisory（勿公开完整利用细节）。

---

## 7. 钱与清算（实现者视角）

协议**不持客资**。真钱轨：适配 `escrow/settle/refund`，清算在伙伴。  
试验默认 **mock**。详见 Profile [`NP-SETTLE`](../profiles/NP-SETTLE.md)。

「钱记在谁账上」的商务说明：内部 `BA-商用落地路径.md`（运营可读；不改变本 Guide 的技术 MUST）。

---

## 8. CLI 路线图（informative）

| 命令 | 现状 | 说明 |
|------|:----:|------|
| `python -m novapanda.reverify` | ✓ | 独立复验 VDC |
| `python -m conformance.run` | ✓ | 套件入口 |
| `python -m novapanda rails` | ✓ | 本机 `NOVAPANDA_RAILS` Manifest 块 |
| `python -m novapanda quote -a 50 -c USDC` | ✓ | 多轨报价探测 |
| `python -m novapanda negotiate …` | ✓ | 预览 `settlement_binding` |
| `python -m novapanda conformance list/run` | ✓ | 包装一致性套件 |
| `np …`（pip install 后） | ✓ | 同上，`pyproject` scripts 入口 |
| `np manifest validate` | 待 | Manifest / Profile 诚实检查 |
| `np lite roundtrip` | △ | 已有 HTTP 工具；CLI 薄封装 |

**纪律**：CLI **不得**上传私钥；签验在本地完成。

生态八域：[`ecosystem-eight-domains.md`](scenarios/ecosystem-eight-domains.md) · MCP 绑定：[`spec/BINDING-MCP.md`](../spec/BINDING-MCP.md)

---

*实现者指南 · 2026-07-09 · 先互通交割，再谈真钱与认证*
