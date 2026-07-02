# 品牌占坑记录（Brand Prep Log）

> 由 steward 维护；**非法律意见**。注册前请在 registrar / 商标局再次确认。

最后更新：**2026-06-28**（`novapanda.io` + `novapanda.xyz` 已购；NovaPanda 商标已提交，待缴费/受理）

**并行任务清单**：[`NOVAPANDA_PARALLEL_CHECKLIST.md`](NOVAPANDA_PARALLEL_CHECKLIST.md)  
**同步上线对齐包**：[`SYNC_LAUNCH_ALIGNMENT.md`](SYNC_LAUNCH_ALIGNMENT.md)（初衷 · 最少保障 · 文案 · 当日顺序）

---

## 已注册域名（当前 · NovaPanda）

| 域名 | 注册商 | 注册日 | 角色 | DNS / 跳转 |
|------|--------|--------|------|------------|
| **`novapanda.io`** | Namecheap | 2026-06-28 | **主域** | BasicDNS；GitHub Pages / 文档站（待配置） |
| **`novapanda.xyz`** | Namecheap | 2026-06-28 | 防御 | **待配置** Redirect → `https://novapanda.io`（含 `www`） |

| 项 | 值 |
|----|-----|
| 主域名 | **https://novapanda.io** |
| 注册商 | **Namecheap** |
| 隐私保护 | Withheld for Privacy（已开） |
| 自动续费 | **建议给 `.io` 开启**（结账时若未勾，请在控制台打开） |
| 规划子域 | `node.novapanda.io` → mock 参考节点（境外云，部署后） |

**`.com`：** `novapanda.com` — **已被他人注册**（暂不收购；主品牌用 `.io`）。

**国内：** `novapanda.cn` / `.com.cn` — 购买前在注册商再查。

---

## 历史域名（Troodon · 建议迁移）

| 域名 | 注册商 | 有效期 | 建议 |
|------|--------|--------|------|
| **`troodon.io`** | Namecheap | 2026-06-28 → 2027-06-28 | **301 → `https://novapanda.io`**（避免双品牌） |
| **`troodon.xyz`** | Namecheap | 同上 | Redirect → `novapanda.io`（或保留 → troodon.io 再跳主域） |

---

## 域名检索（历史初筛）

| 域名 | 初筛结果 | 备注 | 决策 |
|------|----------|------|------|
| `novapanda.com` | **已注册** | 他人持有 | ☐ 放弃 / ☐ 询价收购 |
| `novapanda.io` | **已注册（Namecheap）** | **主域** | ☑ |
| `novapanda.xyz` | **已注册（Namecheap）** | → novapanda.io | ☑ |
| `novapanda.dev` / `.ai` 等 | 初筛可注册 | 可选防御 | ☐ |
| `troodon.org` | **已注册** | NS → kasserver.com | ☐ 放弃 |
| `troodon.io` | **已注册** | 建议 301 → novapanda.io | ☑ 保留跳转 |
| `troodon.xyz` | **已注册** | 301 | ☑ |

---

## 商标（国内 · NovaPanda · 9+35+42 类）

| 项 | 状态 | 备注 |
|----|:----:|------|
| 申请主体 | ☑ | 北京青合数智科技有限公司 |
| 商标名称 | ☑ | **NovaPanda**（图形+英文组合，黑白） |
| 类别 | ☑ | 第 **9** + **35** + **42** 类 |
| 网上提交 | ☑ | 待缴费 / 待受理 |
| 申请号 | ☐ | ____________（受理通知书） |
| 申请日 | ☐ | ____________ |
| 近似检索（提交前） | ☐ | 建议保留检索记录 |

---

## GitHub / 包名占坑

| 项 | 状态 | URL / 名称 |
|----|:----:|------------|
| GitHub 组织 **`novapanda-protocol`** + 仓库 **`novapanda`** | ☐ | `@NoVaPanda` 为他人账号，不可用 |
| GitHub Pages（`/docs` → **novapanda.io**） | ☐ | DNS 已配；push + Pages Custom domain 后启用 |
| PyPI `troodon` | ☐ | |
| npm `@troodon/sdk` | ☐ | 本地包名已用，发布前查重 |

---

## 公开前勾选

完成 [`PRE_PUBLISH_CHECKLIST.md`](PRE_PUBLISH_CHECKLIST.md) 第七节后再对外高调宣传。
