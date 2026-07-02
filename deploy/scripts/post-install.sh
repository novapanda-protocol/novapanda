#!/usr/bin/env bash
# 节点装完后的收尾：cron sweep + 开机自启确认 + 立即验收
set -euo pipefail

NODE_DOMAIN="${NODE_DOMAIN:-node.novapanda.io}"
INSTALL_DIR="${INSTALL_DIR:-/opt/novapanda}"
ENV_FILE="${INSTALL_DIR}/src/deploy/env/production.env"

if [[ -f "$ENV_FILE" ]]; then
  _domain="$(grep '^NODE_DOMAIN=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r' || true)"
  [[ -n "$_domain" ]] && NODE_DOMAIN="$_domain"
fi

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请用 sudo 运行"
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "找不到 $ENV_FILE，请先运行 install-node.sh"
  exit 1
fi

# 拉最新部署脚本（安装时可能还是旧 commit）
if [[ -d "${INSTALL_DIR}/src/.git" ]]; then
  git -C "${INSTALL_DIR}/src" fetch --depth 1 origin main
  git -C "${INSTALL_DIR}/src" reset --hard origin/main
fi

NOVAPANDA_ADMIN_TOKEN="$(grep '^NOVAPANDA_ADMIN_TOKEN=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')"
if [[ -z "$NOVAPANDA_ADMIN_TOKEN" ]]; then
  echo "NOVAPANDA_ADMIN_TOKEN missing in $ENV_FILE"
  exit 1
fi

SWEEP="${INSTALL_DIR}/src/deploy/cron/sweep.sh"
mkdir -p "$(dirname "$SWEEP")"
if [[ ! -f "$SWEEP" ]]; then
  cat > "$SWEEP" <<'EOF'
#!/usr/bin/env sh
set -eu
BASE_URL="${NOVAPANDA_NODE_URL:-http://127.0.0.1}"
ADMIN_TOKEN="${NOVAPANDA_ADMIN_TOKEN:?set NOVAPANDA_ADMIN_TOKEN}"
curl -fsS -X POST "${BASE_URL}/admin/sweep" \
  -H "Host: node.novapanda.io" \
  -H "X-Admin-Token: ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json"
EOF
fi
chmod +x "$SWEEP"

CRON_LINE="*/5 * * * * root NOVAPANDA_NODE_URL=http://127.0.0.1 NOVAPANDA_NODE_HOST=${NODE_DOMAIN} NOVAPANDA_ADMIN_TOKEN=${NOVAPANDA_ADMIN_TOKEN} ${SWEEP} >> /var/log/novapanda-sweep.log 2>&1"
echo "$CRON_LINE" > /etc/cron.d/novapanda-sweep
chmod 644 /etc/cron.d/novapanda-sweep

# 确保容器重启策略（必须 export NODE_DOMAIN，否则 Caddy 会退成 localhost 导致 HTTPS 失效）
export NODE_DOMAIN
cd "${INSTALL_DIR}/src/deploy/docker"
docker compose --env-file ../env/production.env up -d

# 立即跑一次 sweep
NOVAPANDA_NODE_URL="http://127.0.0.1" NOVAPANDA_ADMIN_TOKEN="${NOVAPANDA_ADMIN_TOKEN}" "$SWEEP"
echo ""

curl -fsS -H "Host: ${NODE_DOMAIN}" "http://127.0.0.1/health"
echo ""
echo "========== 收尾完成 =========="
echo "cron: /etc/cron.d/novapanda-sweep (每 5 分钟)"
echo "日志: /var/log/novapanda-sweep.log"
echo "ADMIN_TOKEN: ${NOVAPANDA_ADMIN_TOKEN}"
echo ""
echo "请在 AWS 控制台手动完成（见 deploy/AWS_P2_OPS.md）："
echo "1) EBS 每日快照"
echo "2) 安全组删除 22 的 0.0.0.0/0（保留 Instance Connect 即可）"
echo "3) （可选）绑定 Elastic IP"
echo ""
echo "服务器验收：sudo bash ${INSTALL_DIR}/src/deploy/scripts/verify-ops.sh"
