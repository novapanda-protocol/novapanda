# Mock 节点稳定性与测试

> 配套脚本：[`scripts/smoke.sh`](scripts/smoke.sh)（Linux/服务器）、[`scripts/smoke.ps1`](scripts/smoke.ps1)（Windows 本机打远程）。  
> 部署总览：[`README.md`](README.md) · 清单：[`CHECKLIST.md`](CHECKLIST.md)

---

## 「稳定了」的定义

mock 阶段不要求支付伙伴，但要求 **7 天无人值守仍可服务开发者试用**：

| 维度 | 标准 |
|------|------|
| 可用 | `GET /health` 连续 7 天返回 `{"status":"ok"}` |
| 持久 | `TROODON_DB` 在 **持久卷**；每日快照可恢复 |
| 清扫 | cron **每 1–5 分钟** 调用 `POST /admin/sweep`（带 `X-Admin-Token`） |
| 恢复 | 容器/进程重启后 30s 内 `/health` OK；启动时 `engine.recover()` 已执行 |
| 安全 | `TROODON_AUTH=1`；`TROODON_ADMIN_TOKEN` 已设；无 token 的 sweep 返回 401 |
| 功能 | 至少 1 次 **SETTLED** 全生命周期（TS plugfest）+ sweep 无 5xx |

满足后可认为 mock **足够稳定**，再开独立环境接 x402 sandbox。

---

## 测试分层

### 第 0 层：上云前门禁（本地，必过）

在仓库根目录：

```bash
python -m pytest -q
python -m conformance.run
python demo/plugfest.py
python demo/run_demo.py
```

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m conformance.run
.\.venv\Scripts\python.exe demo\plugfest.py
.\.venv\Scripts\python.exe demo\run_demo.py
```

或一键（需已安装 dev 依赖）：

```bash
./deploy/scripts/pre-deploy-gate.sh
```

```powershell
.\deploy\scripts\pre-deploy-gate.ps1
```

---

### 第 1 层：Staging（与生产同 env）

```bash
cp deploy/env/mock.env.example deploy/env/production.env
# 编辑 TROODON_ADMIN_TOKEN

cd deploy/docker
docker compose --env-file ../env/production.env up -d --build
```

对本机 Caddy（`NODE_DOMAIN=localhost` 时需改 Caddyfile 或直接用 node 端口测）：

```bash
export TROODON_NODE_URL=http://127.0.0.1:8000   # 或 https://your-domain
export TROODON_ADMIN_TOKEN=与 production.env 一致
export RUN_TS_LIFECYCLE=1
./deploy/scripts/smoke.sh
```

---

### 第 2 层：上云后冒烟（15 分钟）

```bash
export TROODON_NODE_URL=https://node.yourdomain.com
export TROODON_ADMIN_TOKEN='your-secret'
export RUN_TS_LIFECYCLE=1
./deploy/scripts/smoke.sh
```

Windows（打远程节点）：

```powershell
$env:TROODON_NODE_URL = "https://node.yourdomain.com"
$env:TROODON_ADMIN_TOKEN = "your-secret"
$env:RUN_TS_LIFECYCLE = "1"
.\deploy\scripts\smoke.ps1
```

脚本检查项：

1. `GET /health` → `status: ok`
2. `GET /.well-known/troodon.json` → 协议 manifest
3. `GET /registry/rules` → 含 `R-extract-invoice-v1`
4. `POST /admin/sweep` **无** token → **401**
5. `POST /admin/sweep` **有** token → 200 + `expired` 字段
6. （可选）TS SDK 全生命周期 → **SETTLED**

仅测基础设施、不跑 TS（无 Node 的服务器上）：

```bash
export RUN_TS_LIFECYCLE=0
./deploy/scripts/smoke.sh
```

---

### 第 3 层：韧性（mock 对外前必做一次）

| 测试 | 操作 | 期望 |
|------|------|------|
| 进程重启 | `docker compose restart node` | `/health` 恢复；SQLite 不丢 |
| recover | 重启后查未完成交换 | SETTLING 等中间态可继续 |
| 超时退款 | `run_demo.py` 场景 3，或等 deadline + sweep | `EXPIRED_REFUNDED` |
| cron 24h | 查看 sweep 日志 | 无 401/5xx |
| 备份恢复 | 云盘快照 → 新卷挂载 | 历史 exchange 仍在 |

超时逻辑单元测试：`tests/test_timeout.py`、`tests/test_confirm_timeout.py`、`tests/test_verify_timeout.py`。

---

### 第 4 层：持续监控（保持稳定）

**合成探测**（每 1–5 分钟）：

```bash
curl -fsS "${TROODON_NODE_URL}/health" | grep -q '"status":"ok"'
```

**每日深度冒烟**（cron，需 Node + 仓库路径）：

```cron
0 4 * * * root TROODON_NODE_URL=https://node.example.com TROODON_ADMIN_TOKEN=... RUN_TS_LIFECYCLE=1 /opt/troodon/deploy/scripts/smoke.sh >> /var/log/troodon-smoke.log 2>&1
```

**告警建议**：health 失败、5xx 率、磁盘 >80%、sweep 连续失败。

---

## 运维配置速查（mock）

```
TROODON_SETTLEMENT=mock
TROODON_AUTH=1
TROODON_ADMIN_TOKEN=<强随机>
TROODON_DB=/data/troodon.sqlite          # 持久卷
TROODON_WITNESS_V2=0
TROODON_FEDERATION_V2=0
cron: deploy/cron/sweep.sh 每 1–5 分钟
备份: 云盘/EBS 每日快照
```

---

## 常见问题

**Q：`run_demo.py` 能测线上吗？**  
A：不能。它用内存 `TestClient`。线上请用 `RUN_TS_LIFECYCLE=1` 的 smoke 脚本或手动 `node sdk/typescript/test/plugfest_lifecycle.mjs <url>`。

**Q：smoke 里 TS 生命周期失败？**  
A：确认节点 `TROODON_AUTH=1`、外网可访问、规则 registry 已 seed；本地先 `cd sdk/typescript && npm run build`。

**Q：health OK 但交换 401？**  
A：检查 Agent 请求签名头（`X-Agent-Id` / `X-Nonce` / `X-Signature`）；TS SDK 会自动签名。

**Q：何时算可以切 x402？**  
A：mock 满足本文「稳定了」+ [`CHECKLIST.md`](CHECKLIST.md) 第 C 节；**新环境 + 新 DB**，勿与 mock 混库。
