#!/usr/bin/env bash
# ==============================================================================
# Hermes WebUI Sofia Status (host-native systemd service)
# ==============================================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

# shellcheck disable=SC1091
[[ -f .env ]] && set -a && source .env && set +a

systemctl --no-pager status hermes-webui.service 2>&1 | head -n 12
echo ""
curl -sf --max-time 5 "http://127.0.0.1:${HERMES_WEBUI_PORT:-8787}/health" >/dev/null 2>&1 \
  && echo "✅ /health OK" \
  || echo "[!] /health not responding"
echo ""
echo "--- runtime (who/where the agent executes) ---"
_svc_pid="$(systemctl show -p MainPID --value hermes-webui.service 2>/dev/null || echo 0)"
if [[ "${_svc_pid}" != "0" ]]; then
  tr '\0' ' ' < "/proc/${_svc_pid}/cmdline" 2>/dev/null; echo ""
  echo "user: $(ps -o user= -p "${_svc_pid}" 2>/dev/null)"
  tr '\0' '\n' < "/proc/${_svc_pid}/environ" 2>/dev/null | grep -E "^(DISPLAY|XAUTHORITY|HERMES_WEBUI_BOT_NAME)=" || true
  ls -d /tmp/.X11-unix/X1 2>/dev/null && echo "X11 socket visible: yes" || echo "X11 socket visible: no"
  command -v cua-driver steel-session 2>/dev/null || true
fi
