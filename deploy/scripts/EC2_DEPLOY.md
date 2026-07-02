# EC2 部署指南（我无法代你 SSH，请你按此操作）

> **说明**：部署需在 AWS 控制台或本机 SSH/Instance Connect 执行。  
> 推荐优先使用 **EC2 Instance Connect**（浏览器终端），减少本地网络对 22 端口的干扰。

---

## 部署前检查

- [ ] 安全组：**80、443** 对 `0.0.0.0/0`；22 仅当前 IP 或删掉后用 Instance Connect
- [ ] **弹性 IP** 已关联实例（推荐）
- [ ] Namecheap：**`node.novapanda.io` A 记录** → 弹性 IP
- [ ] `novapanda.io` 的 **www CNAME** → `novapanda-protocol.github.io`（GitHub Pages，与节点分开）

---

## 方式一：代码尚未 push GitHub（今天最快）

### A. 本机 Windows 打包并上传

把 `你的密钥.pem` 路径和 **EC2 公网 IP** 换成真实值：

```powershell
cd d:\project\jiazhi

# 打包（排除 .venv、git）
tar -czf $env:TEMP\novapanda-upload.tar.gz --exclude=.git --exclude=.venv --exclude=__pycache__ .

# 上传（用户名多为 ubuntu 或 ec2-user，看 AMI）
scp -i "C:\path\to\your-key.pem" $env:TEMP\novapanda-upload.tar.gz ubuntu@YOUR_EC2_PUBLIC_IP:/tmp/

# SSH 登录
ssh -i "C:\path\to\your-key.pem" ubuntu@YOUR_EC2_PUBLIC_IP
```

### B. 在服务器上执行

```bash
sudo apt-get update && sudo apt-get install -y git curl
# 把仓库里的脚本先 scp 上去，或粘贴 deploy/scripts/ec2-bootstrap.sh 内容

export NODE_DOMAIN=node.novapanda.io
sudo bash /tmp/ec2-bootstrap.sh /tmp/novapanda-upload.tar.gz
```

脚本结束会打印 **`ADMIN_TOKEN`**，务必保存。

---

## 方式二：已 push 到 GitHub 后

```bash
export REPO_URL="https://github.com/novapanda-protocol/novapanda.git"
export NODE_DOMAIN="node.novapanda.io"
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/novapanda-protocol/novapanda/main/deploy/scripts/ec2-bootstrap.sh)"
```

（需仓库 **public** 且含 `deploy/scripts/ec2-bootstrap.sh`。）

---

## 方式三：EC2 浏览器连接（推荐，最少切换）

1. AWS 控制台 → EC2 → 实例 → **连接**
2. **EC2 Instance Connect** → 连接
3. 一次粘贴执行（已上传 tar 的情况下）：

```bash
export NODE_DOMAIN="node.novapanda.io"
sudo bash /tmp/ec2-bootstrap.sh /tmp/novapanda-upload.tar.gz
```

若已 push GitHub，可直接：

```bash
export NODE_DOMAIN="node.novapanda.io"
export REPO_URL="https://github.com/novapanda-protocol/novapanda.git"
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/novapanda-protocol/novapanda/main/deploy/scripts/ec2-bootstrap.sh)"
```

---

## 验证

```bash
# 服务器上
curl -fsS http://127.0.0.1:8000/health

# DNS + Caddy 证书就绪后（几分钟）
curl -fsS https://node.novapanda.io/health
```

Windows 本机：

```powershell
$env:TROODON_NODE_URL = "https://node.novapanda.io"
$env:TROODON_ADMIN_TOKEN = "脚本输出的 token"
$env:RUN_TS_LIFECYCLE = "1"
cd d:\project\jiazhi
.\deploy\scripts\smoke.ps1
```

---

## 常见问题

| 问题 | 处理 |
|------|------|
| Caddy 证书失败 | 确认 `node.novapanda.io` DNS 已指向本机 IP |
| SSH 连不上 | IP 变了 → 用 Instance Connect；或改安全组 22 |
| `docker compose` 找不到 | `sudo apt install docker-compose-plugin` |
| AMI 用户名 | Ubuntu → `ubuntu`；Amazon Linux → `ec2-user` |

---

## AI 能帮你做什么

- ✅ 写好脚本与命令（本文件 + `ec2-bootstrap.sh`）
- ✅ 你在本机跑 `scp`/`ssh` 时，把 **报错贴过来** 我帮排查
- ❌ 不能代替你登录 AWS 或持有 `.pem` 私钥
