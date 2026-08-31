#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Hermes Agent Update & Patch Manager
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VPS_TOOLS_DIR="$(cd "${HERMES_DIR}/.." && pwd)"

# Load .env if present
if [[ -f "${HERMES_DIR}/.env" ]]; then
  # shellcheck disable=SC1091
  source "${HERMES_DIR}/.env"
fi

HERMES_USER="${HERMES_USER:-$(logname 2>/dev/null || echo "${SUDO_USER:-$USER}")}"
USER_HOME=$(eval echo "~${HERMES_USER}")
HERMES_AGENT_PATH="${HERMES_AGENT_PATH:-${USER_HOME}/.hermes/hermes-agent}"

echo "================================================================="
echo "--> Updating Hermes Agent safely at: ${HERMES_AGENT_PATH}"
echo "================================================================="

if [[ ! -d "${HERMES_AGENT_PATH}/.git" ]]; then
  echo "[-] ERROR: ${HERMES_AGENT_PATH} is not a git repository."
  exit 1
fi

CURRENT_COMMIT=$(git -C "${HERMES_AGENT_PATH}" rev-parse --short HEAD)
echo "[*] Current commit: ${CURRENT_COMMIT}"

# 1. Stash any temporary changes before pulling
STASHED=0
if [[ -n "$(git -C "${HERMES_AGENT_PATH}" status --porcelain)" ]]; then
  echo "[*] Stashing working directory changes before pulling..."
  su - "${HERMES_USER}" -c "cd '${HERMES_AGENT_PATH}' && git stash save 'vps-tools-auto-update-stash'"
  STASHED=1
fi

# 2. Pull latest upstream changes
echo "[*] Pulling latest upstream code from origin/main..."
su - "${HERMES_USER}" -c "cd '${HERMES_AGENT_PATH}' && git pull --rebase origin main" || {
  echo "[!] git pull --rebase failed. Attempting git pull..."
  su - "${HERMES_USER}" -c "cd '${HERMES_AGENT_PATH}' && git pull"
}

NEW_COMMIT=$(git -C "${HERMES_AGENT_PATH}" rev-parse --short HEAD)
echo "[+] Upstream updated: ${CURRENT_COMMIT} -> ${NEW_COMMIT}"

# 3. Apply custom patches with validation
echo "[*] Applying and validating custom patches..."
python3 "${HERMES_DIR}/scripts/patch-hermes.py" "${HERMES_AGENT_PATH}"

# 4. Sync SOUL.md and skills
if [[ -f "${HERMES_DIR}/templates/SOUL.md" ]]; then
  echo "[*] Synchronizing SOUL.md system identity..."
  cp "${HERMES_DIR}/templates/SOUL.md" "${USER_HOME}/.hermes/SOUL.md"
  chown "${HERMES_USER}:${HERMES_USER}" "${USER_HOME}/.hermes/SOUL.md"
fi

if [[ -f "${HERMES_DIR}/../skills/scripts/sync_skills.sh" ]]; then
  echo "[*] Synchronizing curated skills from central catalog..."
  bash "${HERMES_DIR}/../skills/scripts/sync_skills.sh" \
    --target hermes \
    --user "${HERMES_USER}"
fi

# 5. Check dependencies in venv
echo "[*] Checking python dependencies..."
if [[ -f "${HERMES_AGENT_PATH}/venv/bin/pip" ]]; then
  su - "${HERMES_USER}" -c "cd '${HERMES_AGENT_PATH}' && venv/bin/pip install -q -r requirements.txt 2>/dev/null || true"
fi

# 6. Rebuild frontend if changed
if [[ "${CURRENT_COMMIT}" != "${NEW_COMMIT}" ]] && [[ -d "${HERMES_AGENT_PATH}/web" ]]; then
  echo "[*] Rebuilding Dashboard frontend..."
  su - "${HERMES_USER}" -c "cd '${HERMES_AGENT_PATH}/web' && npm run build --silent"
fi

# 7. Restart Gateway and Dashboard services
echo "[*] Restarting systemd services..."
sudo systemctl restart hermes-gateway.service || true
sudo systemctl restart hermes-dashboard.service || true

echo "================================================================="
echo "[+] Hermes update completed successfully!"
echo "================================================================="
