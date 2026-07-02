#!/usr/bin/env sh
# 上云前本地门禁：pytest + conformance + plugfest + run_demo
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd)
cd "${REPO_ROOT}"

echo "== pytest =="
python -m pytest -q

echo "== conformance C1-C7 =="
python -m conformance.run

echo "== plugfest (9 scenarios) =="
python demo/plugfest.py

echo "== run_demo =="
python demo/run_demo.py

echo ""
echo "PRE-DEPLOY GATE OK"
