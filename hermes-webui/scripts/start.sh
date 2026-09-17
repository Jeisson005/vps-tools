#!/usr/bin/env bash
# ==============================================================================
# Start Hermes WebUI Sofia (host-native systemd service)
# ==============================================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

# shellcheck disable=SC1091
[[ -f .env ]] && set -a && source .env && set +a

if [[ ! -f /etc/systemd/system/hermes-webui.service ]]; then
  echo "[!] Unit not installed. Run: sudo bash scripts/install.sh" >&2
  exit 1
fi

echo "[+] Starting hermes-webui ..."
sudo systemctl start hermes-webui.service

echo "[+] Waiting for /health ..."
for _i in $(seq 1 30); do
  if curl -sf --max-time 3 "http://127.0.0.1:${HERMES_WEBUI_PORT:-8787}/health" >/dev/null 2>&1; then
    echo "[+] Hermes WebUI Sofia healthy."
    break
  fi
  sleep 2
  if [[ "${_i}" == "30" ]]; then
    echo "[!] WebUI did not become healthy — check: journalctl -u hermes-webui -n 50" >&2
  fi
done

echo ""
echo "================================================================="
echo "✅ Hermes WebUI Sofia Running (host-native)!"
echo "• Local:    http://127.0.0.1:${HERMES_WEBUI_PORT:-8787}"
echo "• Public:   https://${HERMES_WEBUI_DOMAIN:-chat.jeisson.top} (via nginx)"
echo "• Password: (stored in hermes-webui/.env as HERMES_WEBUI_PASSWORD)"
echo "================================================================="
