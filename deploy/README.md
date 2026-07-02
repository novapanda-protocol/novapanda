# 参考节点生产部署指南

> **适用对象**：自营「零号节点」— 开源协议的可运营实例，供全球 Agent 调用；任何人亦可自建同构节点。  
> **结算策略**：**阶段 1 mock** → **阶段 2 x402 sandbox** → 法币持牌伙伴（另文档）。  
> **云**：本文档 **AWS 与阿里云国际通用**；细节见 [`aws/README.md`](aws/README.md)、[`aliyun/README.md`](aliyun/README.md)。

协议实现包名仍为 `troodon`（内部代号）；对外品牌以你定稿域名为准。

---

## 架构概览

```
                    Internet (HTTPS)
                           │
                    [ LB / CDN / WAF ]
                           │
              ┌────────────┴────────────┐
              │  Reverse proxy (TLS)     │  Caddy / Nginx / 云 ALB
              └────────────┬────────────┘
                           │
              ┌────────────┴────────────┐
              │  Troodon Node (FastAPI)  │  uvicorn factory
              │  TROODON_AUTH=1          │
              │  SQLite / 未来 PostgreSQL │
              └────────────┬────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   MockSettlement    HttpX402Gateway    (AP2/Fiat 可选)
   (阶段 1)          (阶段 2 sandbox)
```

**原则**：节点 **不托管用户资金**；mock 无真钱；x402 资金在网关/链下伙伴侧。节点只编排状态机 + VDC + 信誉链。

---

## 阶段规划

| 阶段 | `TROODON_SETTLEMENT` | 需要银行/持牌？ | 目标 |
|:--:|----------------------|-----------------|------|
| **1** | `mock` | **否** | 全球可试用完整交换 + VDC + 信誉 |
| **2** | `x402` + sandbox URL | **通常要企业主体** 向伙伴开户/KYC | 真 authorize/capture/void，仍 sandbox |
| **3** | `fiat` / 生产 x402 | 持牌伙伴 + 商务合同 | 企业客户、法币 |

---

## 快速开始（Docker，任意云 VM）

```bash
# 1. 复制环境文件
cp deploy/env/mock.env.example deploy/env/production.env
# 编辑 production.env：TROODON_ADMIN_TOKEN、域名等

# 2. 构建并启动
cd deploy/docker
docker compose --env-file ../env/production.env up -d --build

# 3. 健康检查
curl -sS https://your-domain/health
```

详见 [`docker/docker-compose.yml`](docker/docker-compose.yml)。

### EC2 网页终端一键恢复（不依赖本地 SSH）

当本地网络到实例 `22` 端口不稳定（例如 banner timeout）时，可直接在 EC2 Instance Connect 执行一条命令恢复：

```bash
sudo bash deploy/scripts/ec2-bootstrap.sh /tmp/novapanda-upload.tar.gz
```

脚本会完成：

1. 安装/修复 Docker 与 Compose Plugin  
2. 启动 `novapanda-node`（`/health`）  
3. 启动 Caddy（`80/443`）并反代到 node  
4. 输出本机健康检查结果

脚本与说明：[`scripts/ec2-bootstrap.sh`](scripts/ec2-bootstrap.sh) · [`scripts/EC2_DEPLOY.md`](scripts/EC2_DEPLOY.md)

---

## 环境变量

| 变量 | 阶段 1 mock | 阶段 2 x402 | 说明 |
|------|-------------|-------------|------|
| `TROODON_AUTH` | `1` | `1` | 生产必须开启 |
| `TROODON_DB` | `/data/troodon.sqlite` | 同左 | 持久卷路径 |
| `TROODON_SETTLEMENT` | `mock` | `x402` | |
| `TROODON_X402_URL` | — | sandbox base URL | |
| `TROODON_X402_API_KEY` | — | 伙伴 API Key | |
| `TROODON_ADMIN_TOKEN` | **必设** | 同左 | `POST /admin/sweep` |
| `TROODON_WITNESS_V2` | `0` | `0` | 公开节点建议先关 |
| `TROODON_FEDERATION_V2` | `0` | `0` | 单节点先关 |

模板：[`env/mock.env.example`](env/mock.env.example)、[`env/x402-sandbox.env.example`](env/x402-sandbox.env.example)。

---

## 超时清扫（cron）

交换超时依赖 `engine.sweep()`。生产由外部调度器调用：

```bash
curl -sS -X POST "https://your-domain/admin/sweep" \
  -H "X-Admin-Token: ${TROODON_ADMIN_TOKEN}"
```

示例脚本：[`cron/sweep.sh`](cron/sweep.sh)。建议 **每 1–5 分钟** 一次。

---

## 上线检查清单

完整列表：[`CHECKLIST.md`](CHECKLIST.md)。

**mock 稳定性与冒烟测试**：[`MOCK_STABILITY.md`](MOCK_STABILITY.md) · [`scripts/smoke.sh`](scripts/smoke.sh) / [`scripts/smoke.ps1`](scripts/smoke.ps1)

---

## 主体、银行、国内公司

见 [`OPERATOR_LEGAL.md`](OPERATOR_LEGAL.md)（自营节点是否需要企业、国内公司可否、何时要银行账户）。

**国内公司 · 境外节点 · mock 对外试用（一页清单）：** [`MINIMAL_LAUNCH_CN.md`](MINIMAL_LAUNCH_CN.md)

---

## 目录

| 路径 | 内容 |
|------|------|
| [`aws/README.md`](aws/README.md) | AWS EC2/ALB/EBS 建议 |
| [`aliyun/README.md`](aliyun/README.md) | 阿里云国际 ECS/SLB 建议 |
| [`docker/`](docker/) | Dockerfile + compose + Caddy |
| [`systemd/`](systemd/) | 非容器部署 unit 示例 |
| [`OPERATOR_LEGAL.md`](OPERATOR_LEGAL.md) | 运营主体与合规 |
| [`CHECKLIST.md`](CHECKLIST.md) | 上线前后检查 |
| [`MINIMAL_LAUNCH_CN.md`](MINIMAL_LAUNCH_CN.md) | 国内公司一页启动 + mock 试用 |
| [`MOCK_STABILITY.md`](MOCK_STABILITY.md) | mock 稳定标准 + 分层测试 |
| [`scripts/`](scripts/) | smoke / pre-deploy-gate 脚本 |
