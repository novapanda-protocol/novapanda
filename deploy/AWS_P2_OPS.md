# P2 稳定运行 — AWS 控制台操作（新加坡 ap-southeast-1）

> 实例：`claude` · `i-0d71c1dbff037a107` · 公网 `node.novapanda.io`  
> 服务器内验收：`curl -fsSL .../deploy/scripts/verify-ops.sh | sudo bash`

---

## 1. 确认 cron sweep（服务器）

EC2 **Instance Connect** 执行：

```bash
sudo bash -c 'curl -fsSL https://raw.githubusercontent.com/novapanda-protocol/novapanda/main/deploy/scripts/verify-ops.sh | bash'
```

或已 clone 时：

```bash
sudo bash /opt/novapanda/src/deploy/scripts/verify-ops.sh
```

预期：`OPS VERIFY OK`；`/var/log/novapanda-sweep.log` 每 5 分钟有新行。

---

## 2. EBS 每日快照

### 控制台（推荐）

1. EC2 → **Elastic Block Store** → **Lifecycle Manager**
2. **Create lifecycle policy**
3. 类型：**Snapshot policy**
4. 目标卷：选中实例系统盘（及若有独立 `/data` 卷一并选）
5. 计划：每 **24** 小时，保留 **7** 份
6. 标签：`Name=novapanda-node-daily`

### 手动一次快照（立即可做）

1. EC2 → **Volumes** → 选中实例根卷
2. **Actions** → **Create snapshot**
3. 描述：`novapanda-manual-YYYY-MM-DD`

数据在 Docker 卷 `novapanda_data`（SQLite）；快照根盘即可覆盖 `/var/lib/docker/volumes`。

---

## 3. 安全组收紧 SSH

1. EC2 → 实例 → **Security** → 安全组
2. **Inbound rules** → 编辑
3. **删除** `SSH 22` 来源 `0.0.0.0/0` 的规则
4. 保留：
   - `HTTPS 443` ← `0.0.0.0/0`
   - `HTTP 80` ← `0.0.0.0/0`（Caddy 跳转）
5. 运维登录改用 **EC2 Instance Connect**（浏览器），无需开放 22 公网

> 若你本机 SSH 将来修好，可再加一条 `22` 仅你的固定 IP。

---

## 4. Elastic IP（暂缓）

当前使用自动分配 IP `18.142.231.250`。**停止→再启动**实例后 IP 会变，需更新 Namecheap `node` A 记录。

---

## 5. 连续 7 天 health 观察（本机）

```powershell
cd D:\project\jiazhi
.\deploy\scripts\health-watch.ps1
```

日志：`deploy/logs/health-watch.log`（本地，已 gitignore）。连续 7 天无失败即通过 P2 稳定性门禁。

---

## 每日 2 分钟巡检

| 检查 | 命令 |
|------|------|
| 外部 health | `curl -fsS https://node.novapanda.io/health` |
| 本机观察 | `.\deploy\scripts\health-watch.ps1` |
| 服务器 sweep | `sudo tail -3 /var/log/novapanda-sweep.log` |
