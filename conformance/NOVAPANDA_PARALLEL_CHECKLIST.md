# NovaPanda 并行任务清单

> **适用阶段**：国内商标已网上提交，待缴费/受理；域名已购；产品 mock 试用准备上线。  
> **原则**：商标与域名 **独立**——商标未核准 **仍可** 用域名做技术发布；表述准确即可。  
> **主体**：北京青合数智科技有限公司 · **非法律意见**

相关文档：[`BRAND_PREP_LOG.md`](BRAND_PREP_LOG.md) · [`deploy/MINIMAL_LAUNCH_CN.md`](../deploy/MINIMAL_LAUNCH_CN.md) · [`deploy/MOCK_STABILITY.md`](../deploy/MOCK_STABILITY.md)

---

## 阶段 0 · 本周必做（不等商标）

### A. 商标跟进

- [ ] 每天登录 [商标网上服务系统](https://sbj.cnipa.gov.cn) 看 **待支付**
- [ ] 收到缴费通知后 **15 日内** 完成缴费（金额以系统为准，约 3 类 × 270 元）
- [ ] 保存：提交截图、缴费回执、**受理通知书**（下来后填申请号与申请日）
- [ ] 更新 [`BRAND_PREP_LOG.md`](BRAND_PREP_LOG.md) 申请号字段

**若最终驳回**：看驳回理由 → 复审/改图样重提/Plan B 品牌名；**域名仍可继续用**（见下文「商标未过」）

### B. 域名（与商标进度无关，先占坑再用）

- [ ] Namecheap CNAME `www` → **`novapanda-protocol.github.io`**（`novapanda.github.io` 为他人账号）
- [x] **novapanda.io** Advanced DNS（4×A 已配）
- [x] **novapanda.xyz** Redirect（根域 + www → novapanda.io）
- [ ] 创建 GitHub **`novapanda-protocol/novapanda`** 并 push — 见 [`GITHUB_SETUP.md`](../GITHUB_SETUP.md)
- [ ] Pages：Custom domain `novapanda.io` + Enforce HTTPS

### C. 对外表述（现在就能用）

- [ ] 用户协议 + 隐私政策（公司全称：**北京青合数智科技有限公司**）
- [ ] 官网/Trial 页 **禁止** 写「®」「已注册商标」「已持牌清算」
- [ ] **受理前**：可不写商标状态，或写「品牌筹备中」
- [ ] **受理后**：可写「NovaPanda 商标已向中国国家知识产权局提交申请，申请号：____」
- [ ] **核准前**：不得使用 ®

### D. 占坑（与商标无依赖）

- [ ] GitHub 组织 **`novapanda-protocol`** — 见 [`GITHUB_SETUP.md`](../GITHUB_SETUP.md)
- [ ] `support@` / `security@` 邮箱（域名邮箱或别名）
- [ ] （可选）PyPI / npm 包名检索 `@novapanda/sdk` 等

---

## 阶段 1 · 产品与技术（2 周内，核心）

> **初心**：试用的是 **VDC + 交换记录 + 协议 API**；结算 mock，不绑 x402。

### E. 本地门禁

```powershell
cd d:\project\jiazhi
.\deploy\scripts\pre-deploy-gate.ps1
```

- [ ] pytest + conformance + plugfest + run_demo 全绿

### F. 境外 mock 节点

- [ ] 云账号：AWS 国际或阿里云国际（**国内公司**实名），区域 **新加坡**
- [ ] `deploy/env/mock.env.example` → `production.env`（`TROODON_ADMIN_TOKEN` 强随机）
- [ ] Docker compose 部署 — 见 [`deploy/README.md`](../deploy/README.md)
- [ ] cron：`deploy/cron/sweep.sh` 每 1–5 分钟
- [ ] 云盘/EBS **每日快照**
- [ ] 反向代理限流

### G. 上线冒烟

```powershell
$env:TROODON_NODE_URL = "https://node.你的域名"
$env:TROODON_ADMIN_TOKEN = "..."
$env:RUN_TS_LIFECYCLE = "1"
.\deploy\scripts\smoke.ps1
```

- [ ] `/health`、manifest、registry、sweep 401/200、TS 全生命周期 **SETTLED**
- [ ] 连续 7 天 health 绿 — 见 [`deploy/MOCK_STABILITY.md`](../deploy/MOCK_STABILITY.md)

### H. 对外 Trial 页（mock 试用说明）

- [ ] 发布 Quickstart（Python / TS SDK 连 `node.` 子域）
- [ ] 写明：`settlement: mock`，无真钱
- [ ] 链到 spec / GOVERNANCE（协议开放、不铸币、不对协议抽成）

---

## 阶段 2 · 品牌文档（与代码可渐进）

### I. 对外品牌 NovaPanda（代码包名 `troodon` 可暂不改）

| 优先级 | 文件/位置 | 动作 |
|:--:|-----------|------|
| 高 | 官网 / GitHub Pages | 主品牌 NovaPanda，链到 Trial + 文档 |
| 高 | `docs/CNAME` | 指向新主域（启用 Pages 后） |
| 中 | README 开篇 | 官方站点、品牌 footnote |
| 低 | 代码目录 `troodon/` | 大改名可等 v1 或对外稳定后再做 |
| 低 | `/.well-known/troodon.json` | 协议路径可保留兼容，文档说明别名 |

- [ ] 更新 [`BRAND_PREP_LOG.md`](BRAND_PREP_LOG.md) 主域与 NovaPanda 商标行

---

## 阶段 3 · 商标结果后分支

### 若 **核准注册**

- [ ] 证书下来后可在指定类别使用 **®**（仅限核准图样与类别）
- [ ] 规划 **马德里** 或美/新/欧单国（申请日起 6 个月内可主张优先权）
- [ ] 加大对外宣传（仍遵守 GOVERNANCE 表述红线）

### 若 **驳回 / 未核准**

- [ ] 读驳回理由 → 代理评估 **复审** 或 **改标重提**
- [ ] **域名继续用**（若无他人更强在先商标）
- [ ] Plan B：微调产品名（如加 Labs）+ 新图样再申
- [ ] `troodon.io` 或备用域作跳转，避免浪费

---

## 阶段 4 · 暂不做（避免分心）

- [ ] x402 / CDP 主网、法币持牌 — 等 mock 稳定 + 有付费/合同需求
- [ ] 境内服务器 + 对公网 Web — 避免 ICP 备案复杂度（节点放境外）
- [ ] 第 36 类金融商标 — 非当前必需
- [ ] 大规模媒体投放 — 建议商标 **受理后** 再放大

---

## 两周节奏建议

| 周 | 重点 |
|----|------|
| **第 1 周** | 商标缴费 + 域名 DNS/GitHub 占坑 + pre-deploy-gate + 云主机 mock 部署 |
| **第 2 周** | smoke 通过 + Trial 页 + 用户协议/隐私 + 7 天 health 观察 |

---

## 每日 5 分钟检查

1. 商标网：待支付 / 补正 / 受理通知书  
2. 节点：`GET /health`  
3. sweep cron 是否 401/5xx  

---

## 一句话优先级

**缴费商标 → 域名解析与 GitHub → mock 节点 smoke → Trial 文档 → 受理后更新申请号 → 核准后再 ® 与海外商标。**
