#!/usr/bin/env bash
# ==============================================================================
# Headscale UI deploy helper — renders web/config.js (gitignored) with the live
# API key so no secret ever lands in git. The committed index.html reads
# window.__HEADSCALE_API_KEY__ from it (prompt+localStorage fallback).
# Usage:
#   HEADSCALE_UI_API_KEY=<key> ./scripts/deploy_ui.sh   # set/rotate key
#   ./scripts/deploy_ui.sh                              # ensure placeholder only
# Then: docker compose up -d headscale-ui
# ==============================================================================

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$(cd "${SCRIPT_DIR}/../web" && pwd)"
CONFIG_JS="${WEB_DIR}/config.js"

if [[ -n "${HEADSCALE_UI_API_KEY:-}" ]]; then
  printf 'window.__HEADSCALE_API_KEY__=%s;\n' "$(printf '%s' "${HEADSCALE_UI_API_KEY}" | jq -Rs .)" > "${CONFIG_JS}"
  # 644 like the rest of web/: nginx workers read it (browser needs it too).
  chmod 644 "${CONFIG_JS}"
  echo "config.js rendered (key length ${#HEADSCALE_UI_API_KEY})."
elif [[ ! -f "${CONFIG_JS}" ]]; then
  printf 'window.__HEADSCALE_API_KEY__="";\n' > "${CONFIG_JS}"
  chmod 644 "${CONFIG_JS}"
  echo "config.js placeholder created (dashboard will prompt for key)."
else
  echo "config.js already present, untouched."
fi
