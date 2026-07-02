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

**快照不在「实例」列表里**，在左侧菜单：

```
EC2 控制台 → 左侧「弹性块存储」
  ├─ 卷 (Volumes)        ← 选手动快照时从这里进
  ├─ 快照 (Snapshots)    ← 已创建的快照在这里看
  └─ 生命周期管理器 (Lifecycle Manager)  ← 自动每日快照在这里配
```

直接链接（新加坡区）：
- 快照列表：https://ap-southeast-1.console.aws.amazon.com/ec2/home?region=ap-southeast-1#Snapshots:
- 生命周期管理器：https://ap-southeast-1.console.aws.amazon.com/ec2/home?region=ap-southeast-1#LifecyclePolicies:

### 自动每日快照（配一次即可，不用每天手动）

1. 左侧 **弹性块存储** → **生命周期管理器**
2. **创建生命周期策略**
3. 类型选 **快照策略 (Snapshot policy)**
4. 目标：选中 `claude` 实例的**根卷**（系统盘）
5. 频率：每 **24** 小时，保留 **7** 份
6. 保存

之后 AWS **自动**每天拍快照，你不用每天点。

### 手动做一次（可选，立刻备份）

1. 左侧 **弹性块存储** → **卷**
2. 勾选 `claude` 用的那块卷 → **操作** → **创建快照**
3. 左侧 **快照** 里可看到新建记录

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

**不必每天手敲**——注册一次计划任务即可：

```powershell
# 以管理员打开 PowerShell
cd D:\project\jiazhi
.\deploy\scripts\install-health-watch-task.ps1
```

默认每天 **09:00** 自动执行，日志：`deploy/logs/health-watch.log`。

手动立即测一次：

```powershell
.\deploy\scripts\health-watch.ps1
```

---

## 每日 2 分钟巡检

| 检查 | 命令 |
|------|------|
| 外部 health | `curl -fsS https://node.novapanda.io/health` |
| 本机观察 | `.\deploy\scripts\health-watch.ps1` |
| 服务器 sweep | `sudo tail -3 /var/log/novapanda-sweep.log` |
