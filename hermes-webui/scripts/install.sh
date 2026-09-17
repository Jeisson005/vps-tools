#!/usr/bin/env bash
# ==============================================================================
# Install Hermes WebUI Sofia (host-native, systemd) — no Docker.
#
# - Ensures the upstream checkout exists at ${WEBUI_SRC_DIR} pinned to
#   ${WEBUI_VERSION} (same code as the image it replaces).
# - Generates .env with a strong password on first run (chmod 600, gitignored).
# - Renders templates/hermes-webui.service to /etc/systemd/system and enables it.
#
# Usage: sudo bash scripts/install.sh [--version exp-v0.52.314]
# ==============================================================================

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

WEBUI_VERSION="exp-v0.52.314"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) WEBUI_VERSION="${2:-}"; shift 2 ;;
    *) echo "[-] Unknown parameter: $1" >&2; exit 1 ;;
  esac
done

WEBUI_USER="${SUDO_USER:-$(id -un)}"
WEBUI_HOME="$(eval echo "~${WEBUI_USER}")"
WEBUI_SRC="${WEBUI_SRC_DIR:-${WEBUI_HOME}/hermes-webui}"
AGENT_VENV="${WEBUI_HOME}/.hermes/hermes-agent/venv"
UNIT_SRC="${BASE_DIR}/templates/hermes-webui.service"
UNIT_DST="/etc/systemd/system/hermes-webui.service"

if [[ "${EUID}" -ne 0 ]]; then
  echo "[!] Run with sudo: sudo bash scripts/install.sh" >&2
  exit 1
fi

echo "[+] WebUI user:      ${WEBUI_USER} (${WEBUI_HOME})"
echo "[+] Source checkout: ${WEBUI_SRC} @ ${WEBUI_VERSION}"
echo "[+] Agent venv:      ${AGENT_VENV}"

# 1. Upstream source checkout (pinned — same code as the image it replaces)
if [[ ! -d "${WEBUI_SRC}/.git" ]]; then
  echo "[+] Cloning nesquena/hermes-webui @ ${WEBUI_VERSION} ..."
  sudo -u "${WEBUI_USER}" git clone --branch "${WEBUI_VERSION}" --depth 1 \
    https://github.com/nesquena/hermes-webui "${WEBUI_SRC}"
else
  echo "[+] Checkout exists, fetching + pinning to ${WEBUI_VERSION} ..."
  git -C "${WEBUI_SRC}" fetch --tags --depth 1 origin "${WEBUI_VERSION}" || true
  sudo -u "${WEBUI_USER}" git -C "${WEBUI_SRC}" checkout "${WEBUI_VERSION}" || true
fi

# 2. Agent venv must exist (provides server.py interpreter + all agent deps)
if [[ ! -x "${AGENT_VENV}/bin/python" ]]; then
  echo "[!] Agent venv not found at ${AGENT_VENV}/bin/python" >&2
  echo "    Install Hermes agent first (vps-tools/hermes/scripts/install.sh)." >&2
  exit 1
fi

# 3. .env with secrets (server-only, gitignored via **/.env)
if [[ ! -f ".env" ]]; then
  echo "[+] Creating .env from .env.example ..."
  cp .env.example .env
  chmod 600 .env
  chown "${WEBUI_USER}:${WEBUI_USER}" .env
fi
# shellcheck disable=SC1091
set -a; source .env; set +a
if [[ -z "${HERMES_WEBUI_PASSWORD:-}" ]]; then
  HERMES_WEBUI_PASSWORD="$(openssl rand -hex 16)"
  echo "[+] Generated WebUI password, storing in .env ..."
  if grep -q "^HERMES_WEBUI_PASSWORD=" .env; then
    sed -i "s|^HERMES_WEBUI_PASSWORD=.*|HERMES_WEBUI_PASSWORD=${HERMES_WEBUI_PASSWORD}|" .env
  else
    echo "HERMES_WEBUI_PASSWORD=${HERMES_WEBUI_PASSWORD}" >> .env
  fi
  chmod 600 .env
fi

mkdir -p "${HERMES_WORKSPACE_DIR:-${WEBUI_HOME}/workspace}"
chown "${WEBUI_USER}:${WEBUI_USER}" "${HERMES_WORKSPACE_DIR:-${WEBUI_HOME}/workspace}" 2>/dev/null || true

# 4. Render + install systemd unit
echo "[+] Rendering systemd unit ..."
sed -e "s|{{WEBUI_USER}}|${WEBUI_USER}|g" \
    -e "s|{{WEBUI_HOME}}|${WEBUI_HOME}|g" \
    -e "s|{{WEBUI_SRC}}|${WEBUI_SRC}|g" \
    -e "s|{{AGENT_VENV}}|${AGENT_VENV}|g" \
    -e "s|{{WEBUI_ENV}}|${BASE_DIR}/.env|g" \
    "${UNIT_SRC}" > "${UNIT_DST}"
chmod 644 "${UNIT_DST}"

systemctl daemon-reload
systemctl enable hermes-webui.service
systemctl restart hermes-webui.service

echo ""
echo "================================================================="
echo "✅ Hermes WebUI Sofia installed (host-native, no Docker)"
echo "• Service:  systemctl status hermes-webui"
echo "• Local:    http://127.0.0.1:${HERMES_WEBUI_PORT:-8787} (loopback only)"
echo "• Public:   https://${HERMES_WEBUI_DOMAIN:-chat.jeisson.top} (via nginx)"
echo "• Password: stored in hermes-webui/.env as HERMES_WEBUI_PASSWORD"
echo "================================================================="
