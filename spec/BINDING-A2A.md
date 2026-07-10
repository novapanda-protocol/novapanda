# BINDING-A2A · Agent-to-Agent 接入绑定（informative → 规范意向）

> **状态**：v0.1 成文 · 2026-07-09 · **BINDING 层，非 CORE MUST**  
> **纪律**：Agent Card / 任务消息 **≠** 交换状态机；本卷只规定 **翻译与诚实边界**  
> **配套**：[`BINDING-MCP.md`](BINDING-MCP.md) · [`NP-SUR-01`](CORE.md) · `novapanda/surfaces/a2a.py`

---

## 1. 问题

实现者希望通过 **A2A（Agent-to-Agent）** 暴露能力卡片与任务处理，同时仍要产出 **NovaPanda-compatible** 的 VDC。

---

## 2. 分层

```text
Agent（持钥） ──► Exchange HTTP / SDK ──► VDC / 状态机
       │
       └── A2A Binding ── agent_card + handle(task) ── 仅翻译
```

| 层 | A2A 可做什么 | A2A MUST NOT |
|----|--------------|--------------|
| 发现 | `agent_card` 列出 NovaPanda 能力与端点摘要 | 冒充 Manifest 真源 |
| 读 | `get_exchange` 类动作 | 返回未验签的假 SETTLED |
| 写 | 经宿主注入 Agent 签后映射 propose/contract/… | Operator token 代签 |
| 结算 | 展示 rail/environment | sandbox=生产到账 |

---

## 3. 推荐动作映射（参考实现）

| A2A action | 映射 | 鉴权 |
|------------|------|------|
| `agent_card` | 静态能力描述 + `base_url` | 无 |
| `propose` | SDK `propose` | Agent 签 |
| `contract` | SDK `contract` | Agent 签 |
| `escrow` | SDK `escrow` | Client 签 |
| `deliver` | SDK `deliver` | Provider 签 |
| `verify` | SDK `verify` | 按节点 |
| `confirm` | SDK `confirm` | Client 签 |
| `get_exchange` | SDK `get_exchange` | 读 |

**MAY**：`list_scenarios` → 说明层。

**MUST NOT**：`force_settled` · `admin_settle` · 绕过状态机。

---

## 4. 与 MCP / Skill 关系

- 三绑定 **共享** `novapanda/surfaces/operations.py` 操作注册表。  
- 差异仅在 **宿主协议**（卡片 vs 工具 vs skill action）。  
- **语义 MUST 一致**（见 `tests/test_surfaces.py`）。

---

## 5. Conformance

- 暂无 **C-A2A**；依赖 `NP-SUR-01` 表面等价测 + 实现者自报。  
- 未来 MAY 增 C-A2A 只读子集。

---

*BINDING-A2A v0.1 · 与参考 surfaces 同步*
