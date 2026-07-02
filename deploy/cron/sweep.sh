#!/usr/bin/env sh
#  cron 示例：*/5 * * * * /opt/troodon/deploy/cron/sweep.sh
set -eu

BASE_URL="${TROODON_NODE_URL:-https://node.example.com}"
ADMIN_TOKEN="${TROODON_ADMIN_TOKEN:?set TROODON_ADMIN_TOKEN}"

curl -fsS -X POST "${BASE_URL}/admin/sweep" \
  -H "X-Admin-Token: ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json"
