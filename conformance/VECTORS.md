# Conformance · 黄金向量与 SPEC / Profile 挂钩

> **状态**：索引现行 · 2026-07-08  
> **原则**：条款 ID（`NP-*`）指向可执行检查；以本表 + `suite.py` 为人工真源。

运行：

```bash
python -m conformance.run
python -m conformance.run --list
python -m conformance.run C8
```

---

## 1. 套件 ↔ Profile

| Case | 含义 | NP-MIN | NP-NODE | NP-BUNDLE | 测试 |
|------|------|:------:|:-------:|:---------:|------|
| **C1** | 规范化 / 签名 | ✓ | ✓ | | `test_canonical` / cbor / dual |
| **C2** | VDC schema | ✓ | ✓ | | `test_conformance` |
| **C3** | 状态机与超时 | ✓ | ✓ | | state_machine / timeout |
| **C4** | 幂等与 nonce | SHOULD | ✓ | | replay / hardening / auth |
| **C5** | 验收确定性 | ✓ | ✓ | | verifier / llm |
| **C6** | 信誉链 | MAY | SHOULD | | reputation* |
| **C7** | Manifest / 发现 | SHOULD | ✓ | | `test_manifest` |
| **C8** | Bundle / prior_vdc_refs | | | ✓ | `tests/test_bundle.py` |
| **C9** | 物理/计量证据 | | | | `tests/test_phys_c9.py` · NP-PHYS |
| **C10** | Settlement 适配幂等/失败语义 | | SHOULD | | `tests/test_c10_settlement.py` |
| **C11** | Claim 无锚 / 双花拒绝 | | | | `tests/test_c11_claim.py` |
| **C12** | DELEGATE 约束向量 | | | | `tests/test_c12_delegate.py` |
| **C-NODE-R** | recover / pending intent | | ✓ | | `tests/test_c_node_r.py` |
| **C-LITE-RT** | LITE ↔ C1 round-trip | | | | `tests/test_c_lite_rt.py` |
| **C-PRIV** | PRIV hash_only / 无 Operator PII | | | | `tests/test_c_priv.py` |
| **C-S1-SANDBOX** | S1 沙箱诚实 Manifest | | SHOULD | | `tests/test_c_s1_sandbox.py` |
| **C-MCP** | MCP 绑定 ≡ SDK | | SHOULD | | `tests/test_c_mcp.py` |

设计审计（滚动）：内部 [`MUST-向量缺口表.md`](../internal/design/MUST-向量缺口表.md)（T15 · 2026-07-09）。

---

## 2. 条款 ID ↔ Case

| 条款 ID | 意图 | Case |
|---------|------|------|
| NP-ID-01..03 | 身份与私钥不上送 | 实现审 + identity 测试 |
| NP-CAN-01..04 | canonical / hash / sig | **C1** |
| NP-VDC-01..04 | 签名范围与 schema | **C1** / **C2** |
| NP-SM-01..03 | 状态机与退款终态 | **C3** |
| NP-VF-01..02 | 验收确定性 | **C5** |
| NP-SET-01 | 不托管/不抽成/不发币 | 认证政策审阅 |
| NP-REP-01..03 | 信誉可复验 | **C6** |
| NP-SUR-01 | 接入面仅翻译 | surfaces 测试 · **C-MCP 意向** |
| （Bundle Profile） | 字段 / topo / prior 拒收 | **C8** |
| NP-PHYS | 物理/计量 | **C9** |
| NP-SET-A1..A6 | 结算旁路适配 | **C10** · NP-SETTLE |
| NP-DLG-01..06 | 临时委托 / 支付约束 | **C12** · NP-DELEGATE |
| NP-PRIV-01..06 | 隐私姿态 | **C-PRIV** · SEC-PRIV-01 |
| NP-LITE-01..04 | 弱网 / C1 绑定 | **C-LITE-RT** |
| NP-NODE recover | capture-before-execute | **C-NODE-R** |
| NP-CLAIM-XFER | 权柄转让（mock 向量） | **C11** |
| T13 S1 sandbox | 沙箱轨诚实 | **C-S1-SANDBOX** |

---

## 3. 旗舰 demo（非 Cx，但是应用级金线）

| 场景 | 命令 |
|------|------|
| 尽调三连 Bundle | `python demo/nested_diligence.py` |

---

## 4. 资产位置

| 资产 | 位置 |
|------|------|
| 套件 | `conformance/suite.py` |
| 缺口审计 | `conformance/gap_audit.py`（`python -m conformance.gap_audit`） |
| Schema | `spec/schemas/` · [`README.md`](../spec/schemas/README.md) |
| Bundle 库 | `novapanda/bundle.py` |

---

## 5. 认证声明

通过 C1–C8 ≠ 自动获得商标权；见 [CERTIFICATION.md](CERTIFICATION.md)。

> 本实现宣告 `NP-MIN`+`NP-NODE`[+`NP-BUNDLE`]，并公开 `conformance.run` 日志。

---

*挂钩索引 · 2026-07-09 · 随 SPEC 条款增补同步本表*

设计审计（哪些 MUST 仍无向量）：内部 `MUST-向量缺口表.md`（T15 · 2026-07-09）。
