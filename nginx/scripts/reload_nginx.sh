#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose up -d core
docker compose exec core nginx -t
docker compose exec core nginx -s reload
