# BINDING-MCP · MCP 接入绑定（informative → 规范意向）

> **状态**：v0.1 成文 · 2026-07-09 · **BINDING 层，非 CORE MUST**  
> **纪律**：MCP 工具/资源列表 **≠** 交换状态机；本卷只规定 **翻译与诚实边界**  
> **配套**：[`CHARTER.md`](../CHARTER.md) · [`NP-SUR-01`](CORE.md)（接入面仅翻译）· [`ecosystem-eight-domains.md`](../docs/scenarios/ecosystem-eight-domains.md)

---

## 1. 问题

实现者希望通过 **Model Context Protocol (MCP)** 暴露工具与资源，同时仍要产出 **NovaPanda-compatible** 的 VDC。  
本卷回答：哪些语义 MUST 映射到 Exchange API，哪些 MUST NOT 被 MCP 替代。

---

## 2. 分层

```text
Agent（持钥） ──► Exchange HTTP（或 SDK）──► VDC / 状态机
       │
       └── MCP Server（工具面）── 仅翻译：读状态 / 触发已授权动作
```

| 层 | MCP 可做什么 | MCP MUST NOT |
|----|--------------|--------------|
| 发现 | 列出节点 Manifest 摘要、resource_type、rule_id | 冒充 Manifest 真源 |
| 读 | `get_exchange`、`get_vdc`、health | 返回未验签的「假 SETTLED」 |
| 写 | **无密钥时**不得代签 propose/contract/confirm | 用 Operator token 顶替 Agent 签 |
| 结算 | 展示 rail/mock 标识；触发 simulate（若节点开放） | 宣称 sandbox=生产到账 |

---

## 3. 推荐工具映射（参考节点意向）

| MCP tool（建议名） | 映射 API | 鉴权 |
|-------------------|----------|------|
| `np_manifest` | `GET /.well-known/novapanda.json` | 无 |
| `np_propose` | `POST /exchanges` | Agent 签名头 |
| `np_get_exchange` | `GET /exchanges/{id}` | 无/读 |
| `np_deliver` | `POST …/deliver` | Provider 签名 |
| `np_verify` | `POST …/verify` | 按节点 |
| `np_confirm` | `POST …/confirm` | Client 签名 |
| `np_reverify` | 本地 CLI / 库 | 无节点 |

**MAY**：`np_list_scenarios` → `/node/scenarios`（说明层）。

**MUST NOT** 提供：`np_admin_settle`、`np_force_settled` 等绕过状态机的工具。

---

## 4. 与 ToolBundle / Bundle

- **ToolBundle**（多 MCP 工具一次编排）留在 **客户端**；协议落点为 Composer + 可选 [`NP-BUNDLE`](../profiles/NP-BUNDLE.md)。  
- MCP 工具成功 ≠ 交割完成；**成功判据仍是 SETTLED + 双签 VDC**。

---

## 5. 与 DELEGATE

若 Agent 通过 MCP 代调用写路径：

- MUST 支持 `X-Delegation-Id`（或等价头）并走 [`NP-DELEGATE`](../profiles/NP-DELEGATE.md) 校验。  
- MCP 会话令牌 **MUST NOT** 替代 `issuer_sig`。

---

## 6. 测试与互操作

| 级别 | 要求 |
|------|------|
| L0 | MCP 能读 Manifest + exchange 状态 |
| L1 | MCP 路径完成的写操作与 HTTP 向量 **同结论**（C1–C5 子集） |
| 认证 | MCP 绑定 **不单独**发证；随 NP-MIN/NODE 宣告 |

Conformance：**不**新增独立 C-MCP Case；BINDING 测并入实现者自测 + surfaces 测试（参考 `tests/test_surfaces.py`）。

---

## 7. 版本

加性演进；新增 tool 名不破坏 CORE。破坏映射语义 → BINDING 卷 Minor + 公示。

---

*BINDING-MCP v0.1 · 生态八域 P1 出口 · 2026-07-09*
