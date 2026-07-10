# NovaPanda 协议规范 v0 — 卷索引

> 本规范（spec 目录）以 **CC BY 4.0** 授权；参考实现以 **Apache-2.0** 授权。  
> **T16 拆卷（2026-07-09）**：全文分布于分卷；本页为**兼容入口**与锚点地图。  
> 读者地图：[README.md](README.md)

协议定义智能体之间**跨主体、无预建关系**的可验证交割层。关键词 MUST / SHOULD / MAY 按 RFC 2119。

---

## 分卷目录

| 原 § | 卷 | 文件 |
|------|-----|------|
| §1–8 | **CORE** | [CORE.md](CORE.md) — 身份、VDC、状态机、验收、一致性 |
| §9、§13 | **NP-HTTP** | [NP-HTTP.md](NP-HTTP.md) — HTTP 鉴权、错误码 |
| §10–12 | **NP-OPS** | [NP-OPS.md](NP-OPS.md) — 超时、recover、Manifest、Admin |
| §14–19 | **NP-V2+** | [NP-V2.md](NP-V2.md) — Witness、联邦、LLM、物理（experimental） |

**Profile**：[../profiles/README.md](../profiles/README.md)  
**Conformance**：[../conformance/VECTORS.md](../conformance/VECTORS.md)

---

## 兼容锚点（旧链接迁移）

| 旧锚点 | 新位置 |
|--------|--------|
| `#7-接入面access-surfaces` | [CORE.md §7](CORE.md#7-接入面) |
| `#8-一致性conformance` | [CORE.md §8](CORE.md#8-一致性conformance) |
| HTTP / 错误码 | [NP-HTTP.md](NP-HTTP.md) |
| recover / sweep | [NP-OPS.md](NP-OPS.md) |

---

## 一句话摘要（不变）

> 不规定价格、不发币、不托管资金；只规定如何产出可独立复验的 **VDC**。

完整条款请阅 **CORE.md** 起各分卷。

---

*SPEC.md · 索引 · T16 后不再承载 §1–19 全文重复*
