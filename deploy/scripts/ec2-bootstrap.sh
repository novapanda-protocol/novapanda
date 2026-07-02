#!/usr/bin/env bash
# NovaPanda mock 节点 — EC2 一键部署（在服务器上执行）
#
# 前置：
#   1. 安全组已开 80/443（22 可选）
#   2. DNS：node.novapanda.io → 本机公网 IP（建议 Elastic IP）
#   3. 代码已在 GitHub：novapanda-protocol/novapanda（或设 REPO_URL）
#
# 用法（EC2 Instance Connect 或 SSH 里粘贴）：
#   export REPO_URL="https://github.com/novapanda-protocol/novapanda.git"
#   export NODE_DOMAIN="node.novapanda.io"
#   curl -fsSL https://raw.githubusercontent.com/novapanda-protocol/novapanda/main/deploy/scripts/ec2-bootstrap.sh | bash
#   —— 首次 push 前请用下面「本地上传」方式，不要 curl 上面这条。
#
# 首次未 push GitHub 时，在服务器上：
#   sudo bash ec2-bootstrap.sh /tmp/novapanda-upload.tar.gz
# （tar 由本机 scp 上传，见 deploy/scripts/EC2_DEPLOY.md）

set -euo pipefail

NODE_DOMAIN="${NODE_DOMAIN:-node.novapanda.io}"
INSTALL_DIR="${INSTALL_DIR:-/opt/novapanda}"
REPO_URL="${REPO_URL:-https://github.com/novapanda-protocol/novapanda.git}"
TARBALL="${1:-}"

echo "== NovaPanda EC2 bootstrap =="
echo "NODE_DOMAIN=$NODE_DOMAIN"
echo "INSTALL_DIR=$INSTALL_DIR"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请用 sudo 运行： sudo bash $0"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git curl ca-certificates openssl

if ! command -v docker >/dev/null 2>&1; then
  echo "== 安装 Docker =="
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
fi

if ! docker compose version >/dev/null 2>&1; then
  apt-get install -y -qq docker-compose-plugin || true
fi

mkdir -p "$INSTALL_DIR"
if [[ -n "$TARBALL" && -f "$TARBALL" ]]; then
  echo "== 从上传的 tar 包解压 =="
  rm -rf "${INSTALL_DIR}/src"
  mkdir -p "${INSTALL_DIR}/src"
  tar -xzf "$TARBALL" -C "${INSTALL_DIR}/src" --strip-components=1 2>/dev/null || \
    tar -xzf "$TARBALL" -C "${INSTALL_DIR}/src"
elif [[ -d "${INSTALL_DIR}/src/.git" ]]; then
  echo "== git pull =="
  git -C "${INSTALL_DIR}/src" pull --ff-only
else
  echo "== git clone =="
  rm -rf "${INSTALL_DIR}/src"
  git clone --depth 1 "$REPO_URL" "${INSTALL_DIR}/src"
fi

ADMIN_TOKEN="$(openssl rand -hex 32)"
ENV_FILE="${INSTALL_DIR}/src/deploy/env/production.env"
cp "${INSTALL_DIR}/src/deploy/env/mock.env.example" "$ENV_FILE"
sed -i "s/change-me-to-long-random-secret/${ADMIN_TOKEN}/" "$ENV_FILE"

echo "== 启动 docker compose =="
cd "${INSTALL_DIR}/src/deploy/docker"
export NODE_DOMAIN
docker compose --env-file ../env/production.env build
docker compose --env-file ../env/production.env up -d

# cron sweep
CRON_LINE="*/5 * * * * root TROODON_NODE_URL=https://${NODE_DOMAIN} TROODON_ADMIN_TOKEN=${ADMIN_TOKEN} ${INSTALL_DIR}/src/deploy/cron/sweep.sh >> /var/log/novapanda-sweep.log 2>&1"
echo "$CRON_LINE" > /etc/cron.d/novapanda-sweep
chmod 644 /etc/cron.d/novapanda-sweep

echo ""
echo "========== 部署完成 =========="
echo "NODE_DOMAIN:     https://${NODE_DOMAIN}"
echo "ADMIN_TOKEN:     ${ADMIN_TOKEN}"
echo "  （请保存！用于 cron / POST /admin/sweep）"
echo ""
echo "检查："
echo "  curl -fsS http://127.0.0.1:8000/health"
echo "  curl -fsS https://${NODE_DOMAIN}/health   # DNS + 证书就绪后"
echo ""
echo "本机 smoke（Windows）："
echo "  \$env:TROODON_NODE_URL='https://${NODE_DOMAIN}'"
echo "  \$env:TROODON_ADMIN_TOKEN='${ADMIN_TOKEN}'"
echo "  \$env:RUN_TS_LIFECYCLE='1'"
echo "  .\\deploy\\scripts\\smoke.ps1"
