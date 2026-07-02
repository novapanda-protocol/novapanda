#!/usr/bin/env bash
# 服务器上验收 P2 运维项（EC2 Instance Connect 执行）
#   curl -fsSL https://raw.githubusercontent.com/novapanda-protocol/novapanda/main/deploy/scripts/verify-ops.sh | sudo bash
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/novapanda}"
ENV_FILE="${INSTALL_DIR}/src/deploy/env/production.env"
SWEEP_LOG="${SWEEP_LOG:-/var/log/novapanda-sweep.log}"
CRON_FILE="/etc/cron.d/novapanda-sweep"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "OK: $*"; }

echo "========== NovaPanda ops verify =========="

[[ -f "$ENV_FILE" ]] || fail "missing $ENV_FILE"
TOKEN="$(grep '^NOVAPANDA_ADMIN_TOKEN=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')"
[[ -n "$TOKEN" ]] || fail "NOVAPANDA_ADMIN_TOKEN empty"

echo ""
echo "== Docker =="
cd "${INSTALL_DIR}/src/deploy/docker"
docker compose --env-file ../env/production.env ps
docker compose --env-file ../env/production.env ps --format json | grep -q '"State":"running"' || fail "container not running"

echo ""
echo "== Health (127.0.0.1) =="
body="$(curl -fsS http://127.0.0.1/health)"
echo "$body" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"' || fail "health: $body"
ok "health"

echo ""
echo "== Cron sweep =="
[[ -f "$CRON_FILE" ]] || fail "missing $CRON_FILE"
grep -q 'NOVAPANDA_NODE_URL=http://127.0.0.1' "$CRON_FILE" || fail "cron must use http://127.0.0.1"
grep -q 'novapanda-sweep' "$CRON_FILE" || fail "unexpected cron content"
ok "cron file"
echo "--- $CRON_FILE ---"
cat "$CRON_FILE"

echo ""
echo "== Sweep log (last 10 lines) =="
if [[ -f "$SWEEP_LOG" ]]; then
  tail -n 10 "$SWEEP_LOG"
  ok "sweep log exists"
else
  echo "WARN: $SWEEP_LOG not found yet (wait 5 min after cron install)"
fi

echo ""
echo "== Manual sweep =="
SWEEP="${INSTALL_DIR}/src/deploy/cron/sweep.sh"
[[ -x "$SWEEP" ]] || fail "missing $SWEEP"
NOVAPANDA_NODE_URL=http://127.0.0.1 NOVAPANDA_ADMIN_TOKEN="$TOKEN" "$SWEEP"
ok "manual sweep"

echo ""
echo "== Disk =="
df -h / /var/lib/docker 2>/dev/null || df -h /

echo ""
echo "========== OPS VERIFY OK =========="
echo "P2 待办（AWS 控制台，本脚本无法代做）："
echo "  1) EBS 每日快照（见 deploy/AWS_P2_OPS.md）"
echo "  2) 安全组删除 22 对 0.0.0.0/0"
echo "  3) Elastic IP（可选，当前暂缓）"
