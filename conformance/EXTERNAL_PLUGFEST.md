# External Plugfest & Second Implementation Call

面向第三方实现与集成伙伴的 **对外 plugfest** 与 **第二实现征集**（v0.2 · 准备稿，未正式发布）。

## 目标

验证**独立** NovaPanda 实现（不必是 Python 参考节点）能否：

1. 通过 manifest 发现能力  
2. 完成 propose → contract → escrow → deliver → verify → confirm  
3. 产出可离线复验的 SETTLED VDC  
4. （可选）写入信誉链 · 宣告 Profile Case  

**社会健壮性**：我们刻意征集第二实现填 [`docs/compatibility.md`](../docs/compatibility.md)。详见内部设计 `G01-第二实现征集.md`。

---

## 谁应该来

| 角色 | 建议证明 |
|------|----------|
| 语言/运行时团队 | 独立节点 · C1–C7 |
| Agent 框架集成方 | TS SDK + HTTP 或 MCP 全生命周期 |
| 结算伙伴 | C10 mock 诚实 · sandbox 样例 |
| 物理/能源垂直 | C9 冒烟（非持牌清算） |

---

## 自证三步

```bash
# 生成登记用报告（gap audit + case 列表）
python -m novapanda conformance report

# 全套件（可选，耗时）
python -m novapanda conformance report --run

# 场景矩阵
python demo/plugfest.py
```

PR [`docs/compatibility.md`](../docs/compatibility.md) 一行：实现名 · 语言 · Profiles · 向量日志链接 · mock/sandbox 诚实备注。

流程对齐 **UC-40** L0→L1（[`internal/design/UC-40-认证流程设计.md`](../internal/design/UC-40-认证流程设计.md)）。

---

## 参考脚本

```bash
# 本地 8 场景（含 energy / witness / LLM）
python demo/plugfest.py

# TS SDK 生命周期 + auth
cd sdk/typescript && npm run build && node test/plugfest_lifecycle.mjs http://127.0.0.1:8000

# 嵌套 Bundle 旗舰
python demo/nested_diligence.py
```

---

## 建议场景矩阵

| 场景 | 说明 | catalog |
|------|------|---------|
| invoice_happy | 结构化数据 + schema 验收 | S-invoice-extract |
| nested_diligence | 三连 Bundle | S-nested-soft-diligence |
| energy_dc | 物理验收冒烟 | S-energy-dc |
| witness_stake | witness v2 + stake | S-witness-stake |
| llm_field_match | 内置 LLM judge | S-llm-summary |
| federation | 跨节点 reverify | S-federation |
| auth_lifecycle | 带鉴权 TS SDK | S-access-surfaces |
| confirm_timeout | VERIFIED 后 confirm 超时 | S-timeout-expire |

---

## 环境变量清单

见 `novapanda/config.py` 模块 docstring（`NOVAPANDA_*`）。

---

## 对外举办 checklist

- [ ] 公布测试向量：`tests/fixtures/` · [`conformance/VECTORS.md`](VECTORS.md)  
- [ ] 提供 fake x402/AP2/fiat 网关（`novapanda/*_fake.py`）  
- [ ] 运行 `python -m novapanda conformance report --run` 全绿  
- [ ] 记录互操作矩阵（实现 × 场景 × Case）  
- [ ] 第二实现至少一行写入 `docs/compatibility.md`  

---

## 状态

**v0.2 准备稿** — 征集与 plugfest 文案就绪；待 Owner 下令公开发布 / 定对外 URL。
