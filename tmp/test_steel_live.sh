#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

if [[ -f "steel/.env" ]]; then
  STEEL_API_KEY=$(grep "^STEEL_API_KEY=" steel/.env | cut -d '=' -f2- | tr -d '"' | tr -d "'")
else
  STEEL_API_KEY="${STEEL_API_KEY:-}"
fi

if [[ -z "$STEEL_API_KEY" ]]; then
  echo "[-] ERROR: STEEL_API_KEY not found in steel/.env" >&2
  exit 1
fi

node "${SCRIPT_DIR}/test_steel_live.js"
