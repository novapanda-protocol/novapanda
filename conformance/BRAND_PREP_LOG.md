# 品牌占坑记录（Brand Prep Log）

> 由 steward 维护；**非法律意见**。注册前请在 registrar / 商标局再次确认。

最后更新：**2026-06-28**

---

## 域名检索（自动化初筛 + 人工复核）

| 域名 | 初筛结果 | 备注 | 决策 |
|------|----------|------|------|
| `troodon.org` | **已注册** | NS → kasserver.com；A 85.13.156.121 | ☐ 放弃 / ☐ 询价收购 |
| `troodon.dev` | **已注册** | 指向 IT 服务公司站点 | ☐ 放弃 / ☐ 询价收购 |
| `troodon.io` | **NXDOMAIN**（2026-06-28 nslookup） | 需在注册商处再查 WHOIS/RDAP | ☐ 注册 |
| `troodon.protocol` | **NXDOMAIN** | 语义贴合协议定位 | ☐ 注册 |
| `gettroodon.com` | 未查 | 备选 | ☐ 查 / ☐ 注册 |
| `troodon-labs.dev` | 未查 | 备选 | ☐ 查 / ☐ 注册 |

**建议下一步（你本机执行）：**

1. 在注册商（Cloudflare / Namecheap / 阿里云等）查询 **`troodon.io`**、**`troodon.protocol`** 实时价格与可注册性  
2. 选定 **1 主域 + 1 防御域** 后填入下表并打勾清单 [`PRE_PUBLISH_CHECKLIST.md`](PRE_PUBLISH_CHECKLIST.md)

### 已注册主域（填好后更新 README）

| 项 | 值 |
|----|-----|
| 主域名 | _（待填）_ |
| 注册商 | _（待填）_ |
| 注册日期 | _（待填）_ |
| DNS 指向 | _（待填，如 GitHub Pages / 文档站）_ |

---

## 商标检索

| 项 | 状态 | 备注 |
|----|:----:|------|
| 文字「Troodon」近似检索（第 9 类） | ☐ | 中国商标局 / 代理 |
| 文字「Troodon」近似检索（第 42 类） | ☐ | |
| 与现有 IT / 软件类商标冲突评估 | ☐ | |
| 申请提交 | ☐ | 申请号：________ |
| 受理/核准 | ☐ | |

---

## GitHub / 包名占坑

| 项 | 状态 | URL / 名称 |
|----|:----:|------------|
| GitHub 组织 `troodon` 或 `troodon-protocol` | ☐ | |
| 本仓库 remote | ☐ | |
| PyPI `troodon` | ☐ | |
| npm `@troodon/sdk` | ☐ | 本地包名已用，发布前查重 |

---

## 公开前勾选

完成 [`PRE_PUBLISH_CHECKLIST.md`](PRE_PUBLISH_CHECKLIST.md) 第七节后再对外高调宣传。
