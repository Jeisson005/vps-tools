#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${HERMES_DIR}"

echo "========================================================================"
echo "  INSTALLING HERMES AGENT (NOUS RESEARCH)"
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
        HERMES_USER) HERMES_USER="$val" ;;
        HERMES_DASHBOARD_ENABLED) HERMES_DASHBOARD_ENABLED="$val" ;;
        HERMES_DASHBOARD_PORT) HERMES_DASHBOARD_PORT="$val" ;;
        HERMES_DASHBOARD_HOST) HERMES_DASHBOARD_HOST="$val" ;;
        HERMES_DASHBOARD_USERNAME) HERMES_DASHBOARD_USERNAME="$val" ;;
        HERMES_DASHBOARD_PASSWORD) HERMES_DASHBOARD_PASSWORD="$val" ;;
      esac
    done < "$env_file"
  fi
}

HERMES_USER="${SUDO_USER:-jeisson}"
HERMES_DASHBOARD_ENABLED="true"
HERMES_DASHBOARD_PORT="9119"
HERMES_DASHBOARD_HOST="0.0.0.0"
HERMES_DASHBOARD_USERNAME="jeisson"
HERMES_DASHBOARD_PASSWORD=""

if [[ -f .env ]]; then
  load_env_safe .env
elif [[ -f .env.example ]]; then
  load_env_safe .env.example
fi

USER_HOME="$(eval echo ~${HERMES_USER})"
HERMES_AGENT_PATH="${USER_HOME}/.hermes/hermes-agent"

# 1. Install prerequisites
echo "--> [1/5] Installing system prerequisites (ripgrep, ffmpeg, git, curl, nodejs, build-essential)..."
apt-get update -qq
apt-get install -y -qq git curl ca-certificates ripgrep ffmpeg build-essential

# 2. Run official Hermes installer as the target user
echo "--> [2/5] Downloading and installing Hermes Agent for user '${HERMES_USER}'..."
su - "${HERMES_USER}" -c 'curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash'

# 3. Create global executable wrapper in /usr/local/bin/hermes
echo "--> [3/5] Setting up global executable wrapper in /usr/local/bin/hermes..."
cat << 'WRAPPER' > /usr/local/bin/hermes
#!/usr/bin/env bash
HERMES_DIR="${HOME}/.hermes/hermes-agent"
if [[ ! -d "$HERMES_DIR" ]]; then
  for d in /home/*/.hermes/hermes-agent; do
    if [[ -d "$d" ]]; then
      HERMES_DIR="$d"
      break
    fi
  done
fi

if [[ -x "${HERMES_DIR}/venv/bin/python" ]]; then
  PYTHON_BIN="${HERMES_DIR}/venv/bin/python"
elif command -v uv &>/dev/null; then
  PYTHON_BIN="uv run python"
else
  PYTHON_BIN="python3"
fi

cd "${HERMES_DIR}" 2>/dev/null || true
exec ${PYTHON_BIN} "${HERMES_DIR}/cli.py" "$@"
WRAPPER
chmod +x /usr/local/bin/hermes

# 4. Build Web Dashboard Frontend
echo "--> [4/5] Building Hermes Web Dashboard frontend..."
if [[ -d "${HERMES_AGENT_PATH}/web" ]]; then
  su - "${HERMES_USER}" -c "cd '${HERMES_AGENT_PATH}/web' && npm run build"
fi

# 5. Configure Web Dashboard & Systemd Service
if [[ "${HERMES_DASHBOARD_ENABLED}" == "true" ]]; then
  echo "--> [5/5] Configuring Hermes Dashboard Systemd service on port ${HERMES_DASHBOARD_PORT}..."
  
  # Configure basic_auth in config.yaml if password provided
  if [[ -n "${HERMES_DASHBOARD_PASSWORD}" ]]; then
    su - "${HERMES_USER}" -c "cd '${HERMES_AGENT_PATH}' && venv/bin/python - << 'PY'
import sys, yaml, os
sys.path.insert(0, '.')
try:
    from plugins.dashboard_auth.basic import hash_password
    pw_hash = hash_password('''${HERMES_DASHBOARD_PASSWORD}''')
    config_path = os.path.expanduser('~/.hermes/config.yaml')
    cfg = {}
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            cfg = yaml.safe_load(f) or {}
    cfg['dashboard'] = {
        'basic_auth': {
            'username': '${HERMES_DASHBOARD_USERNAME}',
            'password_hash': pw_hash
        }
    }
    with open(config_path, 'w') as f:
        yaml.dump(cfg, f)
    print('[+] Updated ~/.hermes/config.yaml with basic_auth credentials')
except Exception as e:
    print(f'[-] Error configuring basic_auth: {e}')
PY"
  fi

  # Generate systemd unit file
  sed -e "s|{{HERMES_USER}}|${HERMES_USER}|g" \
      -e "s|{{HERMES_HOME}}|${USER_HOME}|g" \
      -e "s|{{HERMES_PORT}}|${HERMES_DASHBOARD_PORT}|g" \
      -e "s|{{HERMES_HOST}}|${HERMES_DASHBOARD_HOST}|g" \
      "${HERMES_DIR}/templates/hermes-dashboard.service" > /etc/systemd/system/hermes-dashboard.service

  systemctl daemon-reload
  systemctl enable hermes-dashboard.service
  systemctl restart hermes-dashboard.service
  echo "[+] hermes-dashboard.service enabled and started"
fi

echo ""
echo "========================================================================"
echo "  HERMES AGENT & DASHBOARD INSTALLED SUCCESSFULLY"
echo "  CLI: Run 'hermes setup' or 'hermes chat'"
echo "  Web: http://${HERMES_DASHBOARD_HOST}:${HERMES_DASHBOARD_PORT}"
echo "========================================================================"
