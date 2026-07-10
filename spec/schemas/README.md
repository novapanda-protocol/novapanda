# JSON Schema 索引（spec/schemas）

> **状态**：v0.1 · 2026-07-09  
> **原则**：CORE 实体优先；Profile / 邻接扩展加性演进；`additionalProperties` 策略见各文件  
> **DA 对照**：[`internal/design/DA-数据架构.md`](../../internal/design/DA-数据架构.md)

---

## 1. 文件清单

| 文件 | 实体 / Profile | 层级 | 状态 |
|------|----------------|------|:----:|
| [`vdc.schema.json`](./vdc.schema.json) | VDC | CORE | ✓ |
| [`did-document.schema.json`](./did-document.schema.json) | Agent DID | CORE | ✓ |
| [`key-history.schema.json`](./key-history.schema.json) | 密钥历史 | CORE | ✓ |
| [`reputation-entry.schema.json`](./reputation-entry.schema.json) | 信誉条目 | CORE | ✓ |
| [`reputation-bundle.schema.json`](./reputation-bundle.schema.json) | 信誉聚合 | CORE | ✓ |
| [`stake-lock.schema.json`](./stake-lock.schema.json) | 质押锁 | CORE/扩展 | ✓ |
| [`witness-attestation.schema.json`](./witness-attestation.schema.json) | 见证 | 扩展 | ✓ |
| [`bundle.schema.json`](./bundle.schema.json) | Bundle | NP-BUNDLE | **v0.1 新增** |
| [`claim.schema.json`](./claim.schema.json) | Claim | NP-CLAIM-XFER | **v0.1 新增** |
| [`reputation.schema.json`](./reputation.schema.json) | REP 聚合 (G09) | 扩展 | **v0.6 新增** |
| [`witness.schema.json`](./witness.schema.json) | WIT 见证 (G09) | 扩展 | **v0.6 新增** |
| [`compute-pod-manifest.schema.json`](./compute-pod-manifest.schema.json) | `extensions.compute` | 邻接 | **v0.1 新增** |

**未文件化（待 v0.2）**：Exchange 文档、Node Manifest 顶对象、SettlementReceipt、QuotaLedger、AuditEvent。

---

## 2. 使用方式

```bash
# 示例：用 check-jsonschema 校验（可选 dev 依赖）
check-jsonschema --schemafile spec/schemas/bundle.schema.json demo/out/nested_diligence_bundle.json
```

实现者 **MAY** 在 CI 引用本目录；conformance **C2** 仍以 `vdc.schema.json` + 黄金向量为准。

---

## 3. 版本策略

| 字段 | 规则 |
|------|------|
| `vdc_version` / `bundle_version` / `claim_version` | 主版本与 Profile 文对齐 |
| 破坏性变更 | 新 `$id` 或新主版本；旧 VDC 字节永久可验 |

---

## 4. 交叉引用

| 文档 | 关系 |
|------|------|
| [`profiles/NP-BUNDLE.md`](../../profiles/NP-BUNDLE.md) | Bundle 语义真源 |
| [`profiles/NP-CLAIM-XFER.md`](../../profiles/NP-CLAIM-XFER.md) | Claim 语义真源 |
| [`NP-MANIFEST-Remote-Pod登记.md`](../../internal/design/NP-MANIFEST-Remote-Pod登记.md) | Pod 扩展 |
| [`MUST-向量缺口表.md`](../../internal/design/MUST-向量缺口表.md) G08 | 缺口滚动 |

---

*Schema 索引 · G08 v0.1 · 设计优先*
