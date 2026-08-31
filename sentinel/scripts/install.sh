#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SENTINEL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${SENTINEL_DIR}"

echo "========================================================================"
echo "  INSTALLING SENTINEL AUTONOMOUS SELF-HEALING & TASK SUITE"
echo "========================================================================"

if [[ $EUID -ne 0 ]]; then
  echo "[-] ERROR: This installation script must be run with sudo or as root." >&2
  exit 1
fi

load_env_safe() {
  local env_file="$1"
  if [[ -f "$env_file" ]]; then
    while IFS='=' read -r key val || [[ -n "$key" ]]; do
      key="$(echo "$key" | xargs)"
      [[ -z "$key" || "$key" =~ ^# ]] && continue
      val="${val%\"}"
      val="${val#\"}"
      val="${val%\'}"
      val="${val#\'}"
      case "$key" in
        SENTINEL_USER|CENTINELA_USER) SENTINEL_USER="$val" ;;
        SENTINEL_PORT|CENTINELA_PORT) SENTINEL_PORT="$val" ;;
        SENTINEL_HOST|CENTINELA_HOST) SENTINEL_HOST="$val" ;;
      esac
    done < "$env_file"
  fi
}

SENTINEL_USER="${SUDO_USER:-$(id -un)}"
SENTINEL_PORT="8006"
SENTINEL_HOST="0.0.0.0"

if [[ -f .env ]]; then
  load_env_safe .env
elif [[ -f .env.example ]]; then
  load_env_safe .env.example
fi

USER_HOME="$(eval echo ~${SENTINEL_USER})"

# 1. Install prerequisites
echo "--> [1/5] Installing system dependencies (python3-venv, git, curl)..."
apt-get update -qq
apt-get install -y -qq python3-venv git curl

# 2. Setup Virtualenv
echo "--> [2/5] Setting up Python virtual environment..."
if [[ ! -d "${SENTINEL_DIR}/venv" ]]; then
  python3 -m venv "${SENTINEL_DIR}/venv"
fi
"${SENTINEL_DIR}/venv/bin/pip" install -q --upgrade pip
"${SENTINEL_DIR}/venv/bin/pip" install -q -r "${SENTINEL_DIR}/requirements.txt"

# 3. Setup CLI Binaries in /usr/local/bin
echo "--> [3/5] Installing CLI utilities in /usr/local/bin..."
chmod +x "${SENTINEL_DIR}/bin/sentinel-run" "${SENTINEL_DIR}/bin/sentinel-ctl" "${SENTINEL_DIR}/bin/sentinel-hitl"
ln -sf "${SENTINEL_DIR}/bin/sentinel-run" /usr/local/bin/sentinel-run
ln -sf "${SENTINEL_DIR}/bin/sentinel-ctl" /usr/local/bin/sentinel-ctl
ln -sf "${SENTINEL_DIR}/bin/sentinel-hitl" /usr/local/bin/sentinel-hitl
# Provide backwards-compatible symlinks
ln -sf "${SENTINEL_DIR}/bin/sentinel-run" /usr/local/bin/centinela-run
ln -sf "${SENTINEL_DIR}/bin/sentinel-ctl" /usr/local/bin/centinela-ctl
ln -sf "${SENTINEL_DIR}/bin/sentinel-hitl" /usr/local/bin/centinela-hitl

# Create essential directories
mkdir -p "${SENTINEL_DIR}/tasks" "${SENTINEL_DIR}/cron" "${SENTINEL_DIR}/logs"
chown -R "${SENTINEL_USER}:${SENTINEL_USER}" "${SENTINEL_DIR}"

# 4. Configure Systemd Service
echo "--> [4/5] Registering sentinel.service..."
SERVICE_FILE="/etc/systemd/system/sentinel.service"
sed \
  -e "s|{{SENTINEL_USER}}|${SENTINEL_USER}|g" \
  -e "s|{{SENTINEL_DIR}}|${SENTINEL_DIR}|g" \
  -e "s|{{PYTHON_BIN}}|${SENTINEL_DIR}/venv/bin/python|g" \
  -e "s|{{SENTINEL_PORT}}|${SENTINEL_PORT}|g" \
  -e "s|{{SENTINEL_HOST}}|${SENTINEL_HOST}|g" \
  "${SENTINEL_DIR}/templates/sentinel.service" > "${SERVICE_FILE}"

systemctl daemon-reload
systemctl enable sentinel.service
systemctl restart sentinel.service
sleep 2

# 5. Synchronize Curated Skills to Agents
echo "--> [5/5] Synchronizing Sentinel skills to OpenCode and Hermes..."
if [[ -f "${SENTINEL_DIR}/../skills/scripts/sync_skills.sh" ]]; then
  bash "${SENTINEL_DIR}/../skills/scripts/sync_skills.sh" --user "${SENTINEL_USER}"
fi

echo ""
echo "========================================================================"
echo "  SENTINEL SUITE INSTALLED & RUNNING SUCCESSFULLY"
echo "  MCP & REST Endpoint: http://${SENTINEL_HOST}:${SENTINEL_PORT} (/sse & /mcp)"
echo "  CLIs available:      sentinel-run, sentinel-ctl, sentinel-hitl"
echo "  Service Status:"
systemctl status sentinel.service --no-pager || true
echo "========================================================================"
