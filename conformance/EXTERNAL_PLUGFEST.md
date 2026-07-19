# External Plugfest & Second Implementation Call

面向第三方实现与集成伙伴的 **对外 plugfest** 与 **第二实现征集**（v0.2）。

**可转发邀请**：[`CALL_FOR_SECOND_IMPL.md`](CALL_FOR_SECOND_IMPL.md)  
**起步包（建议先读）**：[`SECOND_IMPL_STARTER.md`](SECOND_IMPL_STARTER.md) · [`second_impl_checklist.json`](second_impl_checklist.json)

---

## 目标

验证**独立** NovaPanda 实现（不必是 Python 参考节点）能否：

1. 通过 Manifest 发现能力（建议 `np manifest validate` 或等价）  
2. 完成 propose → contract → escrow → deliver → verify → confirm  
3. 产出可离线复验的 SETTLED VDC  
4. （可选）Bundle / PHYS / LITE / 信誉 · 按所宣告 Profile 附 Case  

**社会健壮性**：刻意征集第二实现填 [`docs/compatibility.md`](../docs/compatibility.md)。

---

## 谁应该来

| 角色 | 建议证明 |
|------|----------|
| 语言/运行时团队 | 独立节点 · C1–C7（SI-01…05） |
| Agent 框架集成方 | TS SDK + HTTP 或 MCP 全生命周期；可选 `AdopterSkill` 工具面 |
| 结算伙伴 | C10 mock 诚实 · sandbox 样例 |
| 物理/能源垂直 | C9 · `demo/adopter_av_charge.py` 或 plugfest energy |
| 编排/车队 | NP-BUNDLE · `demo/adopter_site_patrol.py` 或 nested diligence |

---

## 自证三步

```bash
# 1) 登记用报告
python -m novapanda conformance report --run

# 2) Manifest 诚实（第二实现用自签 JSON）
python -m novapanda manifest validate ./my-manifest.json --require-profiles

# 3) 场景矩阵（参考实现）
python demo/plugfest.py
```

异语言：用自有测试跑通 [`VECTORS.md`](VECTORS.md) 等价断言，附公开日志即可。

PR [`docs/compatibility.md`](../docs/compatibility.md) 一行：实现名 · 语言 · Profiles · 向量日志 · mock/sandbox 诚实备注。

---

## 最小向量门槛（MUST / SHOULD）

| 等级 | Case / 证据 |
|------|-------------|
| **L0 Client** | SI-03 + SI-04（一笔 SETTLED + reverify） |
| **L1 MIN** | C1–C5 + C7（或报告声明等价） |
| **L2+** | 按宣告 Profile：C8 Bundle · C9 PHYS · C10 SETTLE · C-LITE-RT / Outbox 纪律 |

机器可读：[`second_impl_checklist.json`](second_impl_checklist.json)。

---

## 建议场景矩阵

| 场景 | 说明 | catalog / demo |
|------|------|----------------|
| invoice_happy | 结构化数据 + schema 验收 | S-invoice-extract · `demo/run_demo.py` |
| nested_diligence | 三连 Bundle | S-nested-soft-diligence |
| site_patrol | 四腿物理嵌套 Bundle | S-nested-site-patrol · `demo/adopter_site_patrol.py` |
| energy_dc / av_charge | 物理验收冒烟 | S-energy-dc · `demo/adopter_av_charge.py` |
| witness_stake | witness v2 + stake | S-witness-stake |
| llm_field_match | 内置 LLM judge | S-llm-summary |
| federation | 跨节点 reverify | S-federation |
| auth_lifecycle | 带鉴权 TS SDK | S-access-surfaces |
| confirm_timeout | VERIFIED 后 confirm 超时 | S-timeout-expire |

---

## 参考脚本

```bash
python demo/plugfest.py
python demo/adopter_smoke_all.py
python demo/nested_diligence.py
python demo/adopter_site_patrol.py

cd sdk/typescript && npm ci && npm run attest:l0
cd sdk/typescript && npm run build && node test/plugfest_lifecycle.mjs http://127.0.0.1:8000
```

Schema（informative v0.2 draft）：

- [`spec/schemas/vdc.schema.json`](../spec/schemas/vdc.schema.json)  
- [`spec/schemas/exchange.schema.json`](../spec/schemas/exchange.schema.json)  
- [`spec/schemas/agent-manifest.schema.json`](../spec/schemas/agent-manifest.schema.json)  
- [`spec/schemas/bundle.schema.json`](../spec/schemas/bundle.schema.json)  

---

## 环境变量清单

见 `novapanda/config.py` 模块 docstring（`NOVAPANDA_*`）。

---

## 对外举办 checklist

- [x] 公布测试向量：[`VECTORS.md`](VECTORS.md) · 起步包本目录  
- [x] fake x402/AP2/fiat 网关（`novapanda/*_fake.py`）  
- [x] `python -m novapanda conformance report --run`（参考实现基线）  
- [x] Manifest 校验：`np manifest validate`  
- [x] 接入方 Runtime 竖切：`demo/adopter_smoke_all.py`  
- [ ] 记录互操作矩阵（实现 × 场景 × Case）— **待第二实现填表**  
- [ ] 第二实现至少一行写入 `docs/compatibility.md` — **征集中**  

---

## 登记行模板（粘贴到 compatibility.md）

```text
| my-node | Rust | Org | MIN · PHYS | C1–C7 · C9 | L1 | settlement: mock | https://…/ci-log | YYYY-MM-DD |
```

---

## 状态

**v0.2 征集可用** — 技术材料齐备；对外日程/URL 由 Steward 公布。  
商标与域名纪律见 [`PRE_PUBLISH_CHECKLIST.md`](PRE_PUBLISH_CHECKLIST.md)。
