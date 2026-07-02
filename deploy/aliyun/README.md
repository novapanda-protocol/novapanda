# 阿里云国际部署参考（ECS 路径）

> 与 [`../README.md`](../README.md) 配合使用。**国内公司** 可注册 **阿里云国际站**（alibabacloud.com）账号，用公司资料实名；与 **阿里云中国站**（域名 troodon 问题那站）账号可分开。

---

## 推荐拓扑（阶段 1 mock）

```
域名 DNS → 公网 IP / SLB
       ↓
ECS（Ubuntu）Docker Compose
       ↓
Caddy TLS + Troodon Node
       ↓
云盘 ESSD → /data/troodon.sqlite
```

**区域**：**新加坡**、**美国（硅谷/弗吉尼亚）** 等面向海外 Agent；若用户主要在亚太，选新加坡。

---

## 步骤摘要

### 1. 安全组

| 方向 | 端口 | 授权 |
|------|------|------|
| 入 | 443, 80 | 0.0.0.0/0 |
| 入 | 22 | 运维 IP |
| 出 | 全部 | 访问 x402 sandbox 等 |

### 2. ECS 规格（起步）

| 项 | 建议 |
|----|------|
| 规格 | ecs.c6.large 或同等 2vCPU 4G |
| 镜像 | Ubuntu 22.04 |
| 系统盘 | 40GB+ |
| **数据盘** | 单独 ESSD 挂载 `/data`（SQLite 与系统盘分离） |

### 3. 安装（同 AWS）

```bash
# Docker + clone 仓库 + deploy/env/production.env + docker compose up
# 见 deploy/README.md 快速开始
export NODE_DOMAIN=node.yourdomain.com
cd /opt/troodon/deploy/docker
docker compose --env-file ../env/production.env up -d --build
```

### 4. SLB（可选）

- **简单**：ECS 弹性公网 IP + Caddy  
- **生产**：SLB 监听 443 → ECS:443，证书上传 SLB 或 Caddy 仍终止 TLS

### 5. 备份

- 云盘 **自动快照** 策略（每日）  
- 跨区复制视合规需要

### 6. 切换 x402 sandbox

与 AWS 相同：独立环境、独立 `TROODON_DB`、Secrets 存 API Key。

---

## 中国站 vs 国际站

| | 阿里云 **国际** | 阿里云 **中国** |
|--|----------------|-----------------|
| 部署全球 mock 节点 | ✅ 推荐 | ⚠️ 需 ICP 备案（对公网 Web） |
| 域名 | 国际域名 DNS | `.cn` 等 |
| 支付/x402 伙伴 | 视伙伴 | 视伙伴 |

**建议**：全球参考节点用 **阿里云国际 + 境外区域 ECS**，国内公司主体实名即可。

---

## 监控与运维

- 云监控：CPU、内存、磁盘、`/health` 探测（站点监控）  
- 日志：SLS 或 compose logs 采集  
- 限流：WAF 或 SLB + 应用层 rate limit
