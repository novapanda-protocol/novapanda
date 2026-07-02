#!/usr/bin/env sh
# Mock 节点线上/Staging 冒烟：health + manifest + registry + sweep + 可选 TS 全生命周期
#
#   export TROODON_NODE_URL=https://node.example.com
#   export TROODON_ADMIN_TOKEN=your-secret
#   export RUN_TS_LIFECYCLE=1   # 可选，默认 0
#   ./deploy/scripts/smoke.sh

set -eu

BASE_URL="${TROODON_NODE_URL:?set TROODON_NODE_URL e.g. https://node.example.com}"
ADMIN_TOKEN="${TROODON_ADMIN_TOKEN:?set TROODON_ADMIN_TOKEN}"
RUN_TS="${RUN_TS_LIFECYCLE:-0}"

# 去掉末尾 /
BASE_URL=$(printf '%s' "$BASE_URL" | sed 's#/$##')

fail() {
  echo "SMOKE FAIL: $*" >&2
  exit 1
}

curl_json() {
  curl -fsS "$@"
}

echo "== [1/6] GET /health =="
body=$(curl_json "${BASE_URL}/health") || fail "health unreachable"
echo "$body" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"' || fail "health body: $body"
echo "OK"

echo "== [2/6] GET /.well-known/troodon.json =="
body=$(curl_json "${BASE_URL}/.well-known/troodon.json") || fail "manifest unreachable"
echo "$body" | grep -q '"protocol"' || fail "manifest missing protocol"
echo "OK"

echo "== [3/6] GET /registry/rules =="
body=$(curl_json "${BASE_URL}/registry/rules") || fail "registry/rules unreachable"
echo "$body" | grep -q 'R-extract-invoice-v1' || fail "rule R-extract-invoice-v1 not found"
echo "OK"

echo "== [4/6] POST /admin/sweep without token (expect 401) =="
code=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "${BASE_URL}/admin/sweep") || fail "sweep unreachable"
if [ "$code" != "401" ]; then
  fail "expected 401 without X-Admin-Token, got $code"
fi
echo "OK (401)"

echo "== [5/6] POST /admin/sweep with token =="
body=$(curl_json -X POST "${BASE_URL}/admin/sweep" \
  -H "X-Admin-Token: ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json") || fail "authorized sweep failed"
echo "$body" | grep -q '"expired"' || fail "sweep response missing expired: $body"
echo "OK"

if [ "$RUN_TS" = "1" ]; then
  echo "== [6/6] TS SDK lifecycle (auth) =="
  SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
  REPO_ROOT=$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd)
  TS_DIR="${REPO_ROOT}/sdk/typescript"
  if [ ! -d "${TS_DIR}" ]; then
    fail "sdk/typescript not found at ${TS_DIR}"
  fi
  (
    cd "${TS_DIR}"
    npm run build --silent
    node test/plugfest_lifecycle.mjs "${BASE_URL}"
  ) || fail "TS plugfest_lifecycle failed"
  echo "OK"
else
  echo "== [6/6] TS lifecycle skipped (set RUN_TS_LIFECYCLE=1 to enable) =="
fi

echo ""
echo "SMOKE OK: ${BASE_URL}"
