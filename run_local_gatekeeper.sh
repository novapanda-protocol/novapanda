#!/usr/bin/env bash
# NovaPanda 本地看门狗（Unix / Git Bash）
# 跨平台请优先: python run_local_gatekeeper.py
set -euo pipefail
cd "$(dirname "$0")"
exec python run_local_gatekeeper.py "$@"
