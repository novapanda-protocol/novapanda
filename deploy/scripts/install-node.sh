#!/usr/bin/env bash
# NovaPanda 参考节点 — 一键安装/升级（EC2 Instance Connect 或 SSH 执行）
set -euo pipefail

NODE_DOMAIN="${NODE_DOMAIN:-node.novapanda.io}"
INSTALL_DIR="${INSTALL_DIR:-/opt/novapanda}"
REPO_URL="${REPO_URL:-https://github.com/novapanda-protocol/novapanda.git}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请用 sudo 运行"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git curl ca-certificates openssl docker-compose-plugin || true

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker || true

mkdir -p "$INSTALL_DIR"
if [[ -d "$INSTALL_DIR/src/.git" ]]; then
  git -C "$INSTALL_DIR/src" fetch --depth 1 origin main
  git -C "$INSTALL_DIR/src" reset --hard origin/main
else
  rm -rf "$INSTALL_DIR/src"
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR/src"
fi

ADMIN_TOKEN="$(openssl rand -hex 32)"
ENV_FILE="$INSTALL_DIR/src/deploy/env/production.env"
mkdir -p "$(dirname "$ENV_FILE")"
cp "$INSTALL_DIR/src/deploy/env/mock.env.example" "$ENV_FILE"
sed -i "s/change-me-to-long-random-secret/${ADMIN_TOKEN}/" "$ENV_FILE"

# 停掉旧 mock 容器（若存在）
docker rm -f novapanda-node novapanda-caddy 2>/dev/null || true

cd "$INSTALL_DIR/src/deploy/docker"
export NODE_DOMAIN
docker compose --env-file ../env/production.env build
docker compose --env-file ../env/production.env up -d

sleep 8
curl -fsS "https://${NODE_DOMAIN}/health" || curl -fsS http://127.0.0.1/health || docker compose --env-file ../env/production.env exec -T node curl -fsS http://127.0.0.1:8000/health
echo ""
curl -fsS "https://${NODE_DOMAIN}/.well-known/novapanda.json" | head -c 200 || true
echo ""

echo "========== 完成 =========="
echo "NODE: https://${NODE_DOMAIN}"
echo "ADMIN_TOKEN: ${ADMIN_TOKEN}"
echo "验证: curl -fsS https://${NODE_DOMAIN}/health"
