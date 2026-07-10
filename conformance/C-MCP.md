# C-MCP · MCP 绑定一致性向量（意向 · v0.2 → v0.3）

> **状态**：**informative → suite v0.2** · 2026-07-10  
> **默认 suite**：已挂载 `C-MCP`（`tests/test_c_mcp.py`）；L1 认证硬门槛仍为 C1–C7  
> **规范**：[`spec/BINDING-MCP.md`](../spec/BINDING-MCP.md) · [`NP-SUR-01`](../spec/CORE.md)  
> **实现参考**：`novapanda/surfaces/mcp.py` · `novapanda/bindings/mcp_tools.py` · `tests/test_surfaces.py` · `tests/test_mcp_binding.py`

---

## 1. 目的

证明 **MCP 工具面仅翻译** Exchange 语义，产出与 HTTP/SDK **等价** 的可复验 VDC（NP-SUR-01）。

---

## 2. 预留 Case ID

| Case | 标题 | 状态 |
|------|------|------|
| **C-MCP-01** | MCP 全生命周期 ≡ SDK SETTLED | 意向 |
| **C-MCP-02** | 禁止工具绕过状态机 | 意向 |
| **C-MCP-03** | 只读工具不伪造 SETTLED | 意向 |

**suite.py**：**已挂载** `C-MCP` · `tests/test_c_mcp.py`

---

## 3. C-MCP-01 · 全生命周期等价（意向向量）

**前置**：节点 `NOVAPANDA_AUTH=0` 或测试钥；mock 结算。

**步骤**：

1. 经 `MCPBinding`（或等价）顺序调用：`propose` → `contract`×2 → `escrow` → `deliver` → `verify` → `confirm`  
2. 并行经 `NovaPandaClient` HTTP 跑同参数交换  
3. 比对两路径 `vdc_id`、`result_hash`、终态 `SETTLED`

**通过**：哈希与状态一致；VDC 可 `reverify`。

**现有覆盖**：`tests/test_surfaces.py`（Skill/MCP/A2A 等价）——晋升 C-MCP-01 时 **须** 拆独立 Case 文件 `tests/test_c_mcp.py`。

---

## 4. C-MCP-02 · 禁止绕过（负向）

| 检查 | 期望 |
|------|------|
| `np_force_settled` / `np_admin_settle` | 工具目录 **不存在** 或调用 403 |
| Operator Session 调 propose | 失败（须 Agent 签） |
| MCP 返回未签名 JSON 称 SETTLED | **拒绝** |

**现有覆盖**：`FORBIDDEN_TOOLS` in `mcp_tools.py`；SEC-OP-01 审阅。

---

## 5. C-MCP-03 · 只读工具诚实

| 工具 | 检查 |
|------|------|
| `np_manifest` | 与 `GET /.well-known/novapanda.json` 一致 |
| `np_settlement_quote` | 与 `GET /node/settlement/quote` 一致 |
| `np_get_exchange` | 不注入假 `settlement_receipt` |

**现有覆盖**：`tests/test_mcp_binding.py` 子集。

---

## 6. 与 conformance 升级路径

```text
v0.1  本文 + 现有 tests（informative）
v0.2  tests/test_c_mcp.py + suite.py 挂载 C-MCP-01..03  ✓
v0.3  负向加厚 C-MCP-04..05 · release_check 挂钩  ✓
```

---

## 8. v0.3 负向加厚（设计 · E2）

### C-MCP-04 · Operator 不得经 MCP 代 Agent 缔约

| 检查 | 期望 |
|------|------|
| Operator Session + `novapanda.propose` | **403** / `E_FORBIDDEN`（与 SEC-OP-01 一致） |
| Operator + `novapanda.contract` | **403** |
| 普通 Agent 钥 propose | 成功 |

**实现提示**：复用 `authn` + `operators.is_operator_session`；测试用 `NOVAPANDA_OPERATOR_*` 种子。

### C-MCP-05 · `np_get_exchange` 诚实

| 检查 | 期望 |
|------|------|
| PROPOSED 交换经 `np_get_exchange` | 无 `settlement_receipt` · 无假 `vdc` |
| SETTLED 交换 | 与 `GET /exchanges/{id}` JSON 深度一致（除 transport 包装） |

**现有缺口**：`test_c_mcp.py` 仅覆盖 manifest；E2 补 exchange 路径。

### release_check

`internal/ops/release_check.py` 增步：

```python
("C-MCP", [sys.executable, "-m", "pytest", "tests/test_c_mcp.py", "-q"]),
```

置于 `core_smoke` 之前或并入 `core_smoke` 文件列表——**独立步**便于定位 MCP 回归。

---

## 7. Manifest 诚实

节点 Manifest `transport` 含 `mcp` 时：

- **SHOULD** 链到 BINDING-MCP 版本  
- **MUST NOT** 暗示「仅 MCP 即可兼容」而跳过 C1–C7

---

*C-MCP 意向 · G03/G10 · P6 抬升预备*
