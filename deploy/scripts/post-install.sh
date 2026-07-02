#!/usr/bin/env bash
# 节点装完后的收尾：cron sweep + 开机自启确认 + 立即验收
set -euo pipefail

NODE_DOMAIN="${NODE_DOMAIN:-node.novapanda.io}"
INSTALL_DIR="${INSTALL_DIR:-/opt/novapanda}"
ENV_FILE="${INSTALL_DIR}/src/deploy/env/production.env"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "请用 sudo 运行"
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "找不到 $ENV_FILE，请先运行 install-node.sh"
  exit 1
fi

NOVAPANDA_ADMIN_TOKEN="$(grep '^NOVAPANDA_ADMIN_TOKEN=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')"
if [[ -z "$NOVAPANDA_ADMIN_TOKEN" ]]; then
  echo "NOVAPANDA_ADMIN_TOKEN missing in $ENV_FILE"
  exit 1
fi

SWEEP="${INSTALL_DIR}/src/deploy/cron/sweep.sh"
chmod +x "$SWEEP"

CRON_LINE="*/5 * * * * root NOVAPANDA_NODE_URL=https://${NODE_DOMAIN} NOVAPANDA_ADMIN_TOKEN=${NOVAPANDA_ADMIN_TOKEN} ${SWEEP} >> /var/log/novapanda-sweep.log 2>&1"
echo "$CRON_LINE" > /etc/cron.d/novapanda-sweep
chmod 644 /etc/cron.d/novapanda-sweep

# 确保容器重启策略
cd "${INSTALL_DIR}/src/deploy/docker"
docker compose --env-file ../env/production.env up -d

# 立即跑一次 sweep
NOVAPANDA_NODE_URL="https://${NODE_DOMAIN}" NOVAPANDA_ADMIN_TOKEN="${NOVAPANDA_ADMIN_TOKEN}" "$SWEEP"
echo ""

curl -fsS "https://${NODE_DOMAIN}/health"
echo ""
echo "========== 收尾完成 =========="
echo "cron: /etc/cron.d/novapanda-sweep (每 5 分钟)"
echo "日志: /var/log/novapanda-sweep.log"
echo "ADMIN_TOKEN: ${NOVAPANDA_ADMIN_TOKEN}"
echo ""
echo "请在 AWS 控制台手动完成："
echo "1) 绑定 Elastic IP 到本实例"
echo "2) 安全组删除 22 的 0.0.0.0/0（保留 Instance Connect 即可）"
