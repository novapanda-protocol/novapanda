# Compatibility Matrix · 实现兼容登记

> **状态**：公开空表 · **v0.3**（登记挂钉 + C-MCP 向量）  
> **用途**：社会健壮性（开源尺子 P5）——兼容靠向量，不靠单一代码库。  
> **谁可填**：实现维护者自报 PR；Steward 可抽检向量。  
> **等级定义**：见 [`IMPLEMENTER_GUIDE.md`](IMPLEMENTER_GUIDE.md) §4。

---

## 1. 登记表

| 实现 | 语言 | 维护方 | Profiles 宣告 | 向量/套件 | 等级自报 | 备注 | plugfest / 日志 | 更新日期 |
|------|------|--------|---------------|-----------|----------|------|-----------------|----------|
| novapanda（参考） | Python | 青合 / 社区 | MIN · NODE · **BUNDLE** · PHYS · SETTLE · DELEGATE · PRIV · LITE ·（可选 CLAIM-XFER） | C1–C12 · C-NODE-R · C9 · C-LITE-RT · C-PRIV · C-S1-SANDBOX · C-MCP | L2+ | 结算 mock/sandbox；**Stripe 沙箱真网已测**；CLAIM 生产需 env | `python -m novapanda conformance report --run` | 2026-07-10 |
| @novapanda/sdk | TypeScript | 同上 | 偏 Client / MIN | C1 交叉 · 部分 | L0–L1 | 以 npm 包测试为准 | — | 2026-07-08 |
| *（第二节点欢迎）* | | | | | | **刻意征集** · 见 G01 | | |

### 1.1 Manifest 诚实说明（参考节点）

| Profile | 何时出现在 Manifest |
|---------|---------------------|
| NP-BUNDLE | 默认宣告（C8 库 + `/node/tools/bundle/validate`） |
| NP-CLAIM-XFER | 仅 `NOVAPANDA_CLAIM_MODE=production` |
| NP-SETTLE sandbox | `NOVAPANDA_RAILS` 含 sandbox + `SETTLEMENT_ENV=sandbox` |

### 1.2 现行 Case 索引（登记用）

`C1`–`C8` · `C9` · `C10`–`C12` · `C-NODE-R` · `C-LITE-RT` · `C-PRIV` · `C-S1-SANDBOX` · **`C-MCP`**（informative）—— 见 [`conformance/VECTORS.md`](../conformance/VECTORS.md) · [`conformance/C-MCP.md`](../conformance/C-MCP.md)。

---

## 2. 如何新增一行

1. 跑通 `python -m novapanda conformance report --run`（或等价自建套件对齐 VECTORS）。  
2. 复制 CLI 输出的 `registration_draft` JSON 为起点。  
3. 在 Manifest 中诚实列出 `profiles`。  
4. PR 本文件一行 + 链接到公开 repo / 测试日志。  
5. 结算若仅 mock/sandbox，须在备注写明，勿写成持牌清算。

### 2.1 PR 勾选（v0.3）

- [ ] `conformance report --run` 日志链接（或 CI artifact）  
- [ ] Manifest `/.well-known/novapanda.json` 样例 URL  
- [ ] Profiles 与实测向量一致  
- [ ] 备注写明 `settlement: mock | sandbox | licensed partner`  
- [ ] 本表一行 + 公开 repo 永久链接  

---

## 3. 与认证的关系

| | 兼容矩阵 | 正式认证标 |
|--|----------|------------|
| 费用 | 无 | 身体服务，可另议；**前期可不收** |
| 强制入网 | 否 | 否（红线） |
| 证明物 | 向量与自报 | Steward/基金会流程（见 CERTIFICATION） |

**钱在哪？** 见 [`docs/faq-money.md`](faq-money.md) · [网页版](faq-money.html) · [EN](en/faq-money.html)。

---

*空表也是设计：先有挂钉，再长第二实现 · v0.3*
