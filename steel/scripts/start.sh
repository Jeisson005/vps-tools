#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

echo "--> Starting Steel Browser container..."
docker compose up -d

echo "--> Applying security patches..."
python3 "${SCRIPT_DIR}/patch-steel.py"

docker compose ps
