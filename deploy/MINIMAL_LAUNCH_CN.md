# 一页启动清单（国内公司 · 境外节点 · 最少合规）

> **非法律意见**。主体用已有 **国内公司**；节点放 **境外云**；第一阶段 **mock 对外试用 = 真实业务**，**不绑 x402**。  
> 冒烟测试：[`MOCK_STABILITY.md`](MOCK_STABILITY.md) · 部署：[`README.md`](README.md)

---

## 一、对外试用是什么（为什么不绑 x402 也能试用）

**试用的是「交割协议 + 节点 API」，不是「真钱支付」。**

| 试用者在 mock 节点上 **真的能做的** | **故意不做的**（阶段 1） |
|-----------------------------------|-------------------------|
| 注册 Agent 身份（本地生成 Ed25519，私钥不上传） | 转 USDC / 人民币 |
| 读 `/.well-known/troodon.json` 发现能力 | 接 x402 / 银行 |
| 完整走状态机：propose → contract → escrow → deliver → verify → confirm | 托管真实资金 |
| 拿到 **SETTLED + 可独立复验的 VDC** | 按交易抽协议费 |
| 走超时、sweep 退款（mock 账本内模拟 void） | 声称「已持牌清算」 |
| 积累节点侧信誉（若开启） | |

mock 下 `escrow / settle / refund` 由 **`MockSettlement`** 在节点内模拟（见 `troodon/settlement.py`），**交换流程、签名、验收、VDC 与将来接 x402 时完全一致**；将来只换 `TROODON_SETTLEMENT=x402` 和网关 URL，**SDK 与 HTTP API 不变**。

**对外一句话：**

> 「公开试用环境：完整 Agent 价值交换与可验证交割（VDC）；结算为 **模拟账本**，不涉及真实资金。生产清算轨（x402/法币）另行开通。」

---

## 二、试用者怎么连（给开发者看的 3 步）

**节点 URL 示例：** `https://node.yourdomain.com`

### 1. 发现节点

```bash
curl -sS https://node.yourdomain.com/.well-known/troodon.json
curl -sS https://node.yourdomain.com/registry/rules
```

### 2. Python SDK（鉴权开启）

```python
from troodon.identity import Identity
from troodon.sdk import TroodonClient

base = "https://node.yourdomain.com"
client = TroodonClient(base, Identity.generate())   # 或从文件加载私钥
provider = TroodonClient(base, Identity.generate())

ex = client.propose(
    provider=provider.agent_id,
    resource_type="data.extraction.structured",
    quantity=1,
    rule_id="R-extract-invoice-v1",
    price={"amount": 100, "currency": "USD"},
    idempotency_key="try-001",
)
eid = ex["exchange_id"]
client.contract(eid)
provider.contract(eid)
client.escrow(eid, amount=100, currency="USD")
provider.deliver(eid, {"invoice_no": "T-1", "total": "100.00", "currency": "USD"})
client.verify(eid)
settled = client.confirm(eid)
print(settled["state"], settled["vdc"]["vdc_id"])
```

### 3. TypeScript SDK（推荐作线上冒烟）

```bash
cd sdk/typescript && npm run build
node test/plugfest_lifecycle.mjs https://node.yourdomain.com
```

或你们文档里链到 [`deploy/scripts/smoke.ps1`](scripts/smoke.ps1) / [`smoke.sh`](scripts/smoke.sh)。

**试用者不需要：** x402 钱包、CDP 账号、银行账号、向你们公司汇款。

---

## 三、你们内部启动清单（按顺序打勾）

### A. 主体与对外表述（国内公司，1–3 天）

| # | 项 | 说明 |
|:-:|-----|------|
| A1 | 国内公司作为运营主体 | 已有即可；对外 ToS / 隐私政策用公司名 |
| A2 | 新品牌 + 域名定稿 | 商标进行中也可先用域名 |
| A3 | **用户协议** | 写明：mock 试用、无真钱、不托管资金、非银行 |
| A4 | **隐私政策** | agent_id、交换 metadata、日志保留 |
| A5 | 对外页面 **Trial / Sandbox** 说明 | 复制本文「一句话」+ 节点 URL + SDK 链接 |
| A6 | `support@` / `security@` 邮箱 | 可用域名邮箱或别名 |

**暂不需要：** 支付牌照、对公收交易款、x402/CDP、ICP（若 API 服务器在境外且官网走 GitHub Pages / 海外托管）。

### B. 境外节点（3–5 天）

| # | 项 | 说明 |
|:-:|-----|------|
| B1 | 云账号 | AWS 国际或阿里云国际，**国内公司执照实名** |
| B2 | 区域 | **新加坡**（或美东），单台 ECS/EC2 即可 |
| B3 | 配置 | 复制 [`env/mock.env.example`](env/mock.env.example) → `production.env` |
| B4 | 必设 | `TROODON_AUTH=1`、`TROODON_SETTLEMENT=mock`、`TROODON_ADMIN_TOKEN` |
| B5 | 部署 | [`docker/docker-compose.yml`](docker/docker-compose.yml) + HTTPS |
| B6 | cron | [`cron/sweep.sh`](cron/sweep.sh) 每 1–5 分钟 |
| B7 | 备份 | 云盘/EBS 每日快照 |
| B8 | 限流 | 反向代理或 WAF，防滥用 |

### C. 上线验证（1 天）

| # | 项 | 命令/标准 |
|:-:|-----|----------|
| C1 | 本地门禁 | `.\deploy\scripts\pre-deploy-gate.ps1` |
| C2 | 线上冒烟 | `smoke.ps1` / `smoke.sh`，`RUN_TS_LIFECYCLE=1` |
| C3 | 稳定标准 | 见 [`MOCK_STABILITY.md`](MOCK_STABILITY.md)（7 天 health + sweep） |

### D. 对外开放（持续）

| # | 项 | 说明 |
|:-:|-----|------|
| D1 | README / 文档站 | 节点 URL、`settlement: mock`、Quickstart |
| D2 | GitHub 开源 + Issues | 收集集成反馈 |
| D3 | 可选配额 | 按 IP / API Key 限流，免费 tier 不写死 |
| D4 | **表述红线** | 不写「已接 x402 / 已持牌 / 银行清算」 |

### E. 商业化（可与 D 并行，仍可不绑 x402）

| # | 项 | 说明 |
|:-:|-----|------|
| E1 | 收费方式 | **技术服务费 / SaaS 订阅**（国内对公 + 发票），与 mock 结算 **分开** |
| E2 | 何时要银行 | 开对公票、收服务费时需要；**mock 试用本身不需要** |
| E3 | 何时接 x402 | mock 稳定 + 有付费/集成需求后，**独立环境** 接 sandbox（见 [`OPERATOR_LEGAL.md`](OPERATOR_LEGAL.md)） |

---

## 四、国内 vs 境外：本阶段怎么放

```
┌─────────────────────────────────────────────────────────┐
│  国内公司（法律主体、合同、商标、将来对公开票）              │
└──────────────────────────┬──────────────────────────────┘
                           │ 运营
                           ▼
┌─────────────────────────────────────────────────────────┐
│  境外云 · 新加坡 ECS/EC2                                  │
│  HTTPS API · TROODON_SETTLEMENT=mock                     │
│  面向全球开发者试用                                        │
└─────────────────────────────────────────────────────────┘

文档站 / GitHub Pages / 海外域名  →  一般无需 ICP
若将来在中国大陆机房对公网提供 Web  →  再单独做 ICP
```

**不必**为第一阶段开境外子公司。

---

## 五、对外 Trial 页面建议文案（可直接改品牌名）

**标题：** 公开试用（Sandbox · Mock Settlement）

**正文要点：**

1. 本环境提供完整的 Agent 价值交换与 **VDC（可验证交割凭证）** 能力。  
2. 结算层为 **模拟账本**，**不涉及** 真实货币、稳定币或银行转账。  
3. 您可在本地生成身份并调用 API；我们 **不托管** 您的私钥与资金。  
4. 生产环境将可选接入 x402 / 法币持牌清算；试用环境与生产 **结算配置不同**，协议与 API 形状一致。  
5. 使用即表示同意 [用户协议] 与 [隐私政策]。

**节点信息块：**

| 项 | 值 |
|----|-----|
| Base URL | `https://node.yourdomain.com` |
| Settlement | `mock` |
| Auth | 必填（SDK 自动签名） |
| Manifest | `/.well-known/troodon.json` |

---

## 六、常见问题

**Q：不绑 x402，试用算什么真实业务？**  
A：真实的是 **开发者集成、交换完成率、VDC 复验、超时与信誉**——这些是你们产品的核心；x402 只是后来的 **清算插件**。

**Q：试用和 demo 有什么区别？**  
A：`demo/run_demo.py` 是本地内存；对外试用是 **同一套代码 + SQLite + HTTPS + 鉴权 + 持久化**，全球可访问。

**Q：用户会不会觉得「没付钱不算数」？**  
A：对 **Agent 协议验证** 不算数的是真钱，**算数** 的是状态机与 VDC；目标用户（开发者）理解 sandbox。页面上写清楚即可。

**Q：什么时候必须接 x402？**  
A：**不必须**。只有 when 你需要 **链上 USDC 清算** 或客户合同要求真钱时，才开独立环境接 sandbox/主网。

---

## 七、相关文档

| 文档 | 用途 |
|------|------|
| [`README.md`](README.md) | Docker 部署 |
| [`MOCK_STABILITY.md`](MOCK_STABILITY.md) | 稳定与 smoke |
| [`OPERATOR_LEGAL.md`](OPERATOR_LEGAL.md) | 主体 / 银行 / x402 时机 |
| [`CHECKLIST.md`](CHECKLIST.md) | 上线勾选项 |
