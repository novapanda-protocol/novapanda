#!/usr/bin/env sh
set -eu

BASE_URL="${NOVAPANDA_NODE_URL:-https://node.novapanda.io}"
ADMIN_TOKEN="${NOVAPANDA_ADMIN_TOKEN:?set NOVAPANDA_ADMIN_TOKEN}"

curl -fsS -X POST "${BASE_URL}/admin/sweep" \
  -H "X-Admin-Token: ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json"
