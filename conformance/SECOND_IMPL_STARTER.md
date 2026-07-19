# 第二实现起步包 · Second Implementation Starter

> **用途**：第三方用**任意语言**做第二节点/客户端时的最短路径。  
> **邀请短文（可转发）**：[`CALL_FOR_SECOND_IMPL.md`](CALL_FOR_SECOND_IMPL.md)  
> **配套**：[`EXTERNAL_PLUGFEST.md`](EXTERNAL_PLUGFEST.md) · 机器可读 [`second_impl_checklist.json`](second_impl_checklist.json)  
> **状态**：v0.2 公开可用（征集进行中）

---

## 1. 你要证明什么（Litmus）

陌生 Agent、无预建关系、仅凭公开规范：完成 **SETTLED + 双签 VDC**，并可 **离线 reverify**。  
不要求用我们的节点、语言或结算牌照。

---

## 2. 阅读顺序（强制纪律）

1. [`CHARTER.md`](../CHARTER.md)  
2. [`profiles/NP-MIN.md`](../profiles/NP-MIN.md)  
3. [`spec/CORE.md`](../spec/CORE.md) · [`spec/NP-HTTP.md`](../spec/NP-HTTP.md)  
4. [`VECTORS.md`](VECTORS.md)（至少 C1–C5、C7）  
5. 误区挡板：[`docs/record-vs-vdc.md`](../docs/record-vs-vdc.md)  
6. （产品面参考，非 MUST）[`docs/adopter-closed-loop.md`](../docs/adopter-closed-loop.md)

---

## 3. 最小证明清单（MUST）

对照 [`second_impl_checklist.json`](second_impl_checklist.json) 的 `must[]`：

| ID | 证明 |
|----|------|
| SI-01 | 本地持钥 |
| SI-02 | C1 向量 |
| SI-03 | 完整生命周期 → SETTLED |
| SI-04 | 离线 reverify |
| SI-05 | Manifest + `np manifest validate`（或等价自验） |

可选 SHOULD：C2–C5/C7、Bundle、PHYS、LITE。

---

## 4. 参考命令（Python 参考实现；异语言请等价自建）

```bash
pip install -e ".[dev]"
python -m conformance.run --list
python -m novapanda conformance report --run

# Manifest 诚实
python -m novapanda manifest validate path/to/manifest.json --require-profiles

# 场景冒烟
python demo/plugfest.py
python demo/adopter_smoke_all.py   # 可选：接入方 Runtime 竖切

# TS 客户端
cd sdk/typescript && npm ci && npm test
```

Schema（informative）：`spec/schemas/vdc.schema.json` · `exchange.schema.json` · `agent-manifest.schema.json` · `bundle.schema.json`。

---

## 5. 登记到兼容表

PR [`docs/compatibility.md`](../docs/compatibility.md) 新增一行，备注必须诚实写明结算环境：

`settlement: mock | sandbox | licensed partner`

登记草稿可从：

```bash
python -m novapanda conformance report --run
```

输出的 `registration_draft` 起步。

---

## 6. 禁止当作 CORE 的东西

见 `second_impl_checklist.json` → `anti_patterns`（Record 两态 API、W3C-VC 换皮、协议积分、运营账号代签、mock 冒充持牌等）。

---

## 7. 联系与发布

正式对外 URL / 日程由 Steward 公布（见 EXTERNAL_PLUGFEST 状态节）。  
技术问题：按 [`CONTRIBUTING.md`](../CONTRIBUTING.md) 开 issue/PR。
