#!/usr/bin/env bash
# 在零号 EC2 上执行：拉取最新 main 并重建 Docker。
set -euo pipefail

ROOT="${NOVAPANDA_ROOT:-/opt/novapanda/src}"
BRANCH="${NOVAPANDA_BRANCH:-main}"

cd "$ROOT"
git fetch origin
git pull --ff-only "origin" "$BRANCH"

cd deploy/docker
docker compose --env-file ../env/production.env build
docker compose --env-file ../env/production.env up -d

sleep 3
curl -fsS "https://node.novapanda.io/health"
curl -fsS -o /dev/null -w "poster HTTP %{http_code}\n" \
  "https://node.novapanda.io/static/brand/novapanda-intelligent-open-delivery-protocol-poster-zh.png"
echo "NODE UPDATE OK"
