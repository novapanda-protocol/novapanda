# VERSIONING · 版本与兼容政策

> **状态**：现行 · 2026-07-08  
> **配套**：[CHARTER.md](CHARTER.md) · [GOVERNANCE.md](GOVERNANCE.md) · [spec/SPEC.md](spec/SPEC.md)

---

## 1. 版本化对象

| 对象 | 版本形式 | 说明 |
|------|----------|------|
| 规范文本 / Schema | SemVer 或文件内 `spec_version` | 破坏复验语义 → **MAJOR** |
| VDC `vdc_version` / schema | 字段内声明 | 旧版 MUST 保持可复验路径或提供迁移 |
| 参考实现（Python / SDK） | 包 SemVer | 可快于规范；不得静默改变 MUST 语义 |
| Profile 文档 | `NP-*` + 文档版本 | 加性为主 |
| Manifest `protocol_version` | 节点宣告 | 对端按能力协商 |

## 1.5 分卷规范（T16b）

| 卷 | 版本演进 |
|----|----------|
| `spec/CORE.md` | 语义最稳；破坏复验 / 状态机 → **全局 MAJOR** |
| `spec/NP-HTTP.md` | 可更频 Patch（错误码、头字段加性） |
| `spec/NP-OPS.md` | 运维面；recover / Manifest 加性为主 |
| `spec/NP-V2.md` | experimental 直至 witness 默认启用；破坏独立标注 |
| `spec/SPEC.md` | 索引 stub；不另起语义 |

拆卷本身 **不**自动升 Major；破坏性变更仍走全局 Breaking 流程。

## 2. 变更等级

| 等级 | 定义 | 流程 |
|------|------|------|
| **Editorial** | 措辞、笔误、非语义澄清 | PR；可无长公示 |
| **Additive** | 新可选字段 / 新 Profile / 新错误码 | RFC；公示 ≥ 14 日 |
| **Breaking** | 改变已签 VDC 复验结果、状态机终态语义、canonical 规则 | RFC；MAJOR；**必须**给迁移 / 双轨复验窗口 |

## 3. 兼容承诺

1. 已 `SETTLED` 的 VDC：在 MAJOR 升级后，**仍**须能被声明支持的复验工具验真（或文档化的迁移工具输出等价可验表项）。  
2. 未知字段：遵循加性演进——老实现 MUST 忽略未知非关键键（以 Schema `additionalProperties` 策略为准）。  
3. 弃用：先标记 deprecated ≥ **一个次要周期**（建议 ≥ 90 日），再移除（属 Breaking 则走 MAJOR）。  
4. Profile：可独立演进；节点不得把未宣告 Profile 的行为当作默认 MUST。

## 4. 实现 vs 规范

- 参考实现版本号**不等于**规范符合性。  
- 符合性以 [conformance](conformance/) 与 [profiles](profiles/) 为准。  
- 零号域名或本仓库默认分支**不是**版本真源；以带版本标签的规范发布为准（当前 Steward 阶段：打 tag + 变更日记）。

## 5. 建议发布物

每次规范相关释放：

- 变更摘要（等级标注）  
- Schema 与黄金向量是否更新  
- 迁移说明（若 Breaking）

---

*与治理 RFC 流程一并遵守*
