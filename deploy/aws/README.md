# AWS 部署参考（通用 EC2 路径）

> 与 [`../README.md`](../README.md) 配合使用。适用于 **AWS 全球区域**；国内公司可注册 **AWS 国际站** 账号。

---

## 推荐拓扑（阶段 1 mock）

```
Route 53 (可选) → ACM 证书
       ↓
Application Load Balancer (HTTPS:443)
       ↓
EC2 Auto Scaling Group (min=1) 或 单 EC2
       ↓
Docker Compose: troodon node + Caddy
       ↓
EBS gp3 卷 → /data/troodon.sqlite
```

**区域选择**：面向全球开发者优先 **ap-southeast-1（新加坡）**、**us-east-1**；延迟与合规自行权衡。

---

## 步骤摘要

### 1. 网络与安全组

| 入站 | 来源 | 端口 |
|------|------|------|
| HTTPS | 0.0.0.0/0 | 443 |
| HTTP | 0.0.0.0/0 | 80（Caddy 自动跳转 HTTPS） |
| SSH | 你的 IP | 22 |

**不要** 对公网开放 8000；仅 Caddy 反代。

### 2. EC2 规格（起步）

| 项 | 建议 |
|----|------|
| 实例 | `t3.small` 或 `t3.medium` |
| OS | Ubuntu 22.04 LTS |
| 磁盘 | 30GB+ gp3，挂载 `/data` |
| IAM | 可选 SSM Session Manager，减少 SSH 暴露 |

### 3. 安装与启动

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin git
sudo usermod -aG docker ubuntu

git clone <your-repo> /opt/troodon
cd /opt/troodon/deploy/env
cp mock.env.example production.env
# 编辑 production.env

cd ../docker
export NODE_DOMAIN=node.yourdomain.com
docker compose --env-file ../env/production.env up -d --build
```

### 4. TLS

- **简单**：Caddy 自动 Let's Encrypt（`NODE_DOMAIN` 指向 EC2 公网 IP / EIP）  
- **企业**：ACM 证书 + ALB 终止 TLS，后端 HTTP 到 EC2:443 或内网

### 5. 备份

- **EBS 快照**：每日自动快照 `/dev/nvme1n1` 或 Docker volume  
- 恢复：挂载快照 → 复制 `troodon.sqlite`

### 6. 定时 sweep

```bash
# /etc/cron.d/troodon-sweep
*/5 * * * * root TROODON_NODE_URL=https://node.yourdomain.com TROODON_ADMIN_TOKEN=... /opt/troodon/deploy/cron/sweep.sh
```

### 7. 切换 x402 sandbox

1. 新建 **独立 EC2 或独立 compose 项目**，使用 [`../env/x402-sandbox.env.example`](../env/x402-sandbox.env.example)  
2. 或 **蓝绿**：staging 域名先接 sandbox，验证后改 production env  
3. 在 **Secrets Manager** 存 `TROODON_X402_API_KEY`，注入 EC2 user-data 或 compose secrets

---

## AWS 特有可选增强

| 服务 | 用途 |
|------|------|
| CloudWatch | 日志、CPU、磁盘、`/health` 合成监控 |
| WAF | 限流、Geo block |
| Secrets Manager | Admin token、x402 API Key |
| Route 53 | 域名 DNS |

---

## 成本粗算（mock 单节点）

- EC2 t3.small + 30GB EBS：约 **$15–25/月** 量级（视区域）  
- 流量另计；免费 tier 全球节点需 **限流** 控制账单
