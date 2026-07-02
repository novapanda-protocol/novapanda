# 同步上线对齐包（NovaPanda · 方案 B）

> **状态**：对齐稿，**尚未执行 push / 部署**。确认后再按「当日顺序」操作。  
> **方案**：GitHub org **`novapanda-protocol`** + 全量开源 + 境外 **mock** 节点 **同一天**。  
> **保障**：**最少化**；商标 **少写**；初衷与原则 **写清楚**。

---

## 一、这样可不可以？（对齐结论）

**可以。** 与此前规划一致：

| 你的选择 | 对齐结果 |
|----------|----------|
| 方案 B（org 托管） | ✅ 商务形态与长期治理更顺 |
| 节点 + 代码 **同步上线** | ✅ 对外故事完整，避免「空壳开源」或「空节点」 |
| 商标 **未核准** | ✅ **不阻止** 开源与 mock 节点；表述克制即可 |
| 保障 **最少化** | ✅ 短版 ToS + 隐私 + footnote 即可启动 Trial |
| 商标 **少写** | ✅ 不写 ®、不写申请号（受理后再补一句） |

**暂不做的（对齐同意）：** 大规模宣传、®、x402 主网、法币清算宣传、国内 ICP 大陆机房。

---

## 二、你为什么要开源（初衷 · 对外可原文使用）

### 2.1 我们在解决什么问题

智能体与智能设备之间，要在 **无预建关系** 下交换价值。  
价值交换的第一公民不是支付，而是 **可验证的交付记录**——**VDC（可验证交割凭证）**：结构化、可双签、**任何人可脱离单一平台独立复验**。

### 2.2 我们开源什么、不开源什么

| 开源（公共物） | 说明 |
|----------------|------|
| **协议规范**（CC BY 4.0） | 状态机、VDC 格式、资源本体、规则注册表 |
| **参考实现**（Apache-2.0） | Python 节点与 SDK 骨架，便于验证与自建 |
| **一致性套件** | 独立第三方可跑 C1–C7 / plugfest |

| 不等于开源 / 不等于承诺 |
|-------------------------|
| 持牌清算、法币、x402 生产环境 | 可插拔 **下游**，单独评估 |
| 你运营的 **信誉策略与节点运营数据** | 策略见 GOVERNANCE，默认不随代码一并「开放给竞品抄作业」 |
| **® 商标排他** | 商标核准前 **无 ®** |

### 2.3 不可动摇的原则（你文档里已有的「魂」）

1. **开放、平等**：协议是公共能力，任何人可 **无许可** 实现、自建节点、独立复验 VDC。  
2. **永不铸币**：协议层不造全球流通、可投机的货币。  
3. **永不对协议每笔抽成**：规范归共域；公司价值在 **运营与服务质量**，不在协议租金。  
4. **先证交付，后谈价格**：VDC 与验收是一等公民；mock / x402 / 法币只是 **可选清算轨**。  
5. **灵魂与身体分离**：规范 + 商标意图归 **中立公共物**；公司是 **可替代的托管与运营主体**（见 GOVERNANCE）。

### 2.4 为什么现在开源

- 让陌生 Agent **按规范完成交割并被独立复验**（Litmus 测试），而不是锁在私有栈里。  
- 参考实现与 **公开 mock 节点** 同时提供，降低接入门槛。  
- 当前 Trial 使用 **mock 结算**，**无真实资金**，用于验证 **协议与 VDC**，而非宣传已持牌清算。

---

## 三、同步上线当日顺序（执行清单）

```
T-1  本地：pre-deploy-gate.ps1 全绿
T-0  ① 境外 mock 部署 + cron + 快照
     ② smoke.ps1（RUN_TS_LIFECYCLE=1）打 node URL
     ③ Namecheap：CNAME www → novapanda-protocol.github.io
                   A node → 服务器 IP
     ④ GitHub：建 org novapanda-protocol
               Public repo novapanda，push 全量代码
               Pages：main /docs，Custom domain novapanda.io
     ⑤ 更新 docs/index.html（见下文）链 ToS / Privacy
     ⑥ README 官方链接 + footnote（见下文）
T+1  商标网：若有受理号，只加一句 footnote（可选）
```

---

## 四、最少保障（必须具备）

| # | 项 | 位置 | 状态 |
|---|-----|------|------|
| 1 | **用户协议（短版）** | [`docs/terms.html`](../docs/terms.html) | 已起草 |
| 2 | **隐私政策（短版）** | [`docs/privacy.html`](../docs/privacy.html) | 已起草 |
| 3 | **Trial 说明** | `docs/index.html` · mock · 非 ® | 已起草 |
| 4 | **开源许可** | README + LICENSE 文件 | 仓库已有 Apache-2.0 / spec CC BY |
| 5 | **运营主体** | ToS / 隐私 | 北京青合数智科技有限公司 |
| 6 | **滥用防护** | 节点 | AUTH=1、ADMIN_TOKEN、sweep、限流 |
| 7 | **联系邮箱** | 页脚 / 隐私 | **kwu65348@gmail.com**（上线可用；日后可换域名邮箱） |

**不必首日具备：** 完整白皮书 PDF、MkDocs、®、x402、对公收款说明、ICP（节点在境外）。

---

## 五、商标怎么写（最少 · 按你要求）

### 5.1 现在（未核准 / 可能未受理）

**推荐只写一句（footer / README）：**

> NovaPanda 名称与标识的使用遵循开源许可与网站条款；**尚未获得商标注册核准，不使用 ®**。

**不写：** 申请号、已注册、®、「商标已注册」。

### 5.2 受理后（可选，仍从简）

> NovaPanda 商标已向中国国家知识产权局提交申请（申请号：____）。**未核准前非 ®**。

### 5.3 核准后（将来）

> NovaPanda® 仅在核准类别内使用。

---

## 六、对外文案草稿（复制即用）

### 6.1 官网首段（`docs/index.html`）

见已更新的 [`docs/index.html`](../docs/index.html)。

### 6.2 GitHub 仓库 About / README 顶部一句

> **NovaPanda** — 智能体之间可验证价值交割（VDC）的开放协议与参考实现。  
> 规范 CC BY 4.0 · 代码 Apache-2.0 · 公开 Trial 节点为 **mock 结算**（无真钱）。  
> 官网：https://novapanda.io · 试用：https://node.novapanda.io

### 6.3 GitHub 仓库 Description（一行）

```
Open protocol & reference impl for verifiable agent value delivery (VDC). Mock trial node. Apache-2.0.
```

### 6.4 对外一句话（媒体 / 开发者）

> 我们开源 NovaPanda 协议与参考实现，并运营 mock 试用节点，让任意 Agent 在无预建关系下完成可独立复验的交割；**不涉及真实资金**；清算轨（x402/法币）为可选下游。

---

## 七、表述红线（同步上线仍遵守）

- ❌ NovaPanda® / 已注册商标  
- ❌ 已接入某某银行 / 已持牌清算 / 全球法币已通  
- ❌ 暗示 x402/AP2/ISO 官方背书  
- ❌ 「协议费」「平台抽成每笔交换」  
- ✅ mock 试用、VDC、独立复验、可自建节点、Apache-2.0 / CC BY  

---

## 八、方案 B · GitHub / DNS（对齐，暂不操作）

| 项 | 值 |
|----|-----|
| 登录账号 | `kwu65348-byte`（仅管理） |
| 组织 | `novapanda-protocol` |
| 仓库 | `novapanda`（Public，上线日 push 全量） |
| Pages | `novapanda.io` ← `docs/` |
| CNAME `www` | `novapanda-protocol.github.io` |
| 节点 | `node.novapanda.io` → A 记录 |

**不要用** `novapanda.github.io`（他人账号 @NoVaPanda）。

---

## 九、你确认后我再动手的项

- [ ] 你确认本对齐稿 OK  
- [ ] 联系邮箱：**kwu65348@gmail.com**（已写入 `docs/privacy.html`）  
- [ ] 节点 IP 就绪  
- [ ] 商标：保持「最少表述」或受理后补申请号  

确认后：可按 **第三节顺序** 执行；需要时可让我协助改 README footnote、push 前最后一轮 smoke 文案检查。

---

## 十、相关文件

| 文件 | 用途 |
|------|------|
| [`docs/index.html`](../docs/index.html) | 官网占位 / 上线页 |
| [`docs/terms.html`](../docs/terms.html) | 用户协议（最少） |
| [`docs/privacy.html`](../docs/privacy.html) | 隐私政策（最少） |
| [`docs/CNAME`](../docs/CNAME) | `novapanda.io` |
| [`GITHUB_SETUP.md`](../GITHUB_SETUP.md) | GitHub + DNS 细节 |
| [`deploy/MINIMAL_LAUNCH_CN.md`](../deploy/MINIMAL_LAUNCH_CN.md) | mock 节点 |
| [`GOVERNANCE.md`](../GOVERNANCE.md) | 灵魂/身体、治理 |
