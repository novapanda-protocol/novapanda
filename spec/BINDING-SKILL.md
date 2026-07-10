# BINDING-SKILL · Skill 接入绑定（informative → 规范意向）

> **状态**：v0.1 成文 · 2026-07-09 · **BINDING 层，非 CORE MUST**  
> **纪律**：Skill 动作列表 **≠** 交换状态机；本卷只规定 **翻译与诚实边界**  
> **配套**：[`BINDING-MCP.md`](BINDING-MCP.md) · [`NP-SUR-01`](CORE.md) · `novapanda/surfaces/skill.py`

---

## 1. 问题

宿主（IDE、设备、编排器）通过 **Skill** 暴露「能力动作」，需映射到 NovaPanda Exchange 语义而不改写 VDC。

---

## 2. 分层

```text
Agent（持钥） ──► Exchange HTTP / SDK ──► VDC
       │
       └── ExchangeSkill.run(action, **params) ── 仅翻译
```

| 层 | Skill 可做什么 | Skill MUST NOT |
|----|----------------|----------------|
| 发现 | `skill_manifest` 列出 actions | 宣称 skill 列表 = 节点真源 |
| 读 | `get_exchange` | 假 SETTLED |
| 写 | `propose`…`confirm`（宿主持钥代调 SDK） | 无钥代签；Operator 顶替 |
| 结算 | 回执展示 `rail` / `environment` | 隐瞒 mock/sandbox |

---

## 3. 推荐动作（与 OPERATIONS 注册表对齐）

| action | 映射 SDK 方法 |
|--------|---------------|
| `propose` | `NovaPandaClient.propose` |
| `contract` | `contract` |
| `escrow` | `escrow` |
| `deliver` | `deliver` |
| `verify` | `verify` |
| `confirm` | `confirm` |
| `get_exchange` | `get_exchange` |

**MAY**：`reverify` → 本地库/CLI（不经节点写路径）。

---

## 4. 参数纪律

- `agent_id` / 签名材料 **不得**经 Skill 上传到不可信宿主以外的节点（见 IMPLEMENTER_GUIDE）。  
- Skill **MAY** 在本地完成签验后再调 HTTP。  
- `settlement` / `preferred_rails` 参数 **SHOULD** 原样传入 propose（多轨协商）。

---

## 5. Conformance

- 暂无 **C-SKILL**；`test_surfaces.py` 证明与 SDK 生命周期等价。  
- Manifest `transport` 含 `skill` 时 **MUST NOT** 暗示已认证宿主安全。

---

*BINDING-SKILL v0.1 · 与 ExchangeSkill 同步*
