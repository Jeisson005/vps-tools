#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${HERMES_DIR}"

echo "========================================================================"
echo "  INSTALLING HERMES AGENT & SERVICES (NOUS RESEARCH)"
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
        HERMES_GATEWAY_ENABLED) HERMES_GATEWAY_ENABLED="$val" ;;
        TELEGRAM_BOT_TOKEN) TELEGRAM_BOT_TOKEN="$val" ;;
        TELEGRAM_ALLOWED_USERS) TELEGRAM_ALLOWED_USERS="$val" ;;
      esac
    done < "$env_file"
  fi
}

HERMES_USER="${SUDO_USER:-$(id -un)}"
HERMES_DASHBOARD_ENABLED="true"
HERMES_DASHBOARD_PORT="9119"
HERMES_DASHBOARD_HOST="0.0.0.0"
HERMES_DASHBOARD_USERNAME="${HERMES_USER}"
HERMES_DASHBOARD_PASSWORD=""
HERMES_GATEWAY_ENABLED="true"
TELEGRAM_BOT_TOKEN=""
TELEGRAM_ALLOWED_USERS=""

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

# 4. Install Custom Skills & Configure Browser/Desktop Integrations
echo "--> [4/5] Installing custom skills and setting up browser/desktop integrations..."
STEEL_DOMAIN="browser.localhost"
if [[ -f "${HERMES_DIR}/../steel/.env" ]]; then
  STEEL_DOMAIN_FROM_ENV=$(grep "^STEEL_DOMAIN=" "${HERMES_DIR}/../steel/.env" 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'" || true)
  if [[ -n "$STEEL_DOMAIN_FROM_ENV" ]]; then
    STEEL_DOMAIN="$STEEL_DOMAIN_FROM_ENV"
  fi
fi

mkdir -p "${USER_HOME}/.config/steel/profiles/persistent"
mkdir -p "${USER_HOME}/.hermes/skills/browser/browser-automation"
mkdir -p "${USER_HOME}/.hermes/skills/computer-use/desktop-gui-control"
chown -R "${HERMES_USER}:${HERMES_USER}" "${USER_HOME}/.config/steel" 2>/dev/null || true

# Remove old deprecated skills if present
rm -rf "${USER_HOME}/.hermes/skills/browser/steel-browser" 2>/dev/null || true
rm -rf "${USER_HOME}/.hermes/skills/computer-use/visual-session-control" 2>/dev/null || true

if [[ -f "${HERMES_DIR}/skills/browser-automation/SKILL.md" ]]; then
  sed -e "s|{{STEEL_DOMAIN}}|${STEEL_DOMAIN}|g" \
      "${HERMES_DIR}/skills/browser-automation/SKILL.md" > "${USER_HOME}/.hermes/skills/browser/browser-automation/SKILL.md"
fi

if [[ -f "${HERMES_DIR}/skills/desktop-gui-control/SKILL.md" ]]; then
  cp "${HERMES_DIR}/skills/desktop-gui-control/SKILL.md" "${USER_HOME}/.hermes/skills/computer-use/desktop-gui-control/SKILL.md"
fi

chown -R "${HERMES_USER}:${HERMES_USER}" "${USER_HOME}/.hermes/skills"

# Build Web Dashboard Frontend
if [[ -d "${HERMES_AGENT_PATH}/web" ]]; then
  su - "${HERMES_USER}" -c "cd '${HERMES_AGENT_PATH}/web' && npm run build"
fi

# 5. Configure Web Dashboard & Gateway Services
echo "--> [5/5] Configuring Hermes Dashboard and Gateway Systemd services..."

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

# Configure quiet Telegram display mode and Steel Browser CDP in config.yaml
su - "${HERMES_USER}" -c "cd '${HERMES_AGENT_PATH}' && venv/bin/python - << 'PY'
import sys, yaml, os
try:
    config_path = os.path.expanduser('~/.hermes/config.yaml')
    cfg = {}
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            cfg = yaml.safe_load(f) or {}
    if 'display' not in cfg:
        cfg['display'] = {}
    if 'platforms' not in cfg['display']:
        cfg['display']['platforms'] = {}
    cfg['display']['platforms']['telegram'] = {
        'tool_progress': 'off',
        'busy_ack_detail': False,
        'interim_assistant_messages': False
    }
    if 'browser' not in cfg:
        cfg['browser'] = {}
    cfg['browser']['backend'] = 'off'
    cfg['browser']['cdp_url'] = 'ws://127.0.0.1:9223'
    with open(config_path, 'w') as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=True)
    print('[+] Configured quiet Telegram display and Steel CDP in ~/.hermes/config.yaml')
except Exception as e:
    print(f'[-] Error configuring display/browser settings: {e}')
PY"

# Configure Telegram env vars if provided
if [[ -n "${TELEGRAM_BOT_TOKEN}" ]]; then
  HERMES_ENV="${USER_HOME}/.hermes/.env"
  touch "${HERMES_ENV}"
  chmod 600 "${HERMES_ENV}"
  if ! grep -q "^TELEGRAM_BOT_TOKEN=" "${HERMES_ENV}" 2>/dev/null; then
    echo "TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}" >> "${HERMES_ENV}"
  else
    sed -i "s|^TELEGRAM_BOT_TOKEN=.*|TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}|" "${HERMES_ENV}"
  fi
  if [[ -n "${TELEGRAM_ALLOWED_USERS}" ]]; then
    if ! grep -q "^TELEGRAM_ALLOWED_USERS=" "${HERMES_ENV}" 2>/dev/null; then
      echo "TELEGRAM_ALLOWED_USERS=${TELEGRAM_ALLOWED_USERS}" >> "${HERMES_ENV}"
    else
      sed -i "s|^TELEGRAM_ALLOWED_USERS=.*|TELEGRAM_ALLOWED_USERS=${TELEGRAM_ALLOWED_USERS}|" "${HERMES_ENV}"
    fi
  fi
fi

# Generate dashboard systemd unit
if [[ "${HERMES_DASHBOARD_ENABLED}" == "true" ]]; then
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

# Generate gateway systemd unit
if [[ "${HERMES_GATEWAY_ENABLED}" == "true" ]]; then
  sed -e "s|{{HERMES_USER}}|${HERMES_USER}|g" \
      -e "s|{{HERMES_HOME}}|${USER_HOME}|g" \
      "${HERMES_DIR}/templates/hermes-gateway.service" > /etc/systemd/system/hermes-gateway.service

  systemctl daemon-reload
  systemctl enable hermes-gateway.service
  systemctl restart hermes-gateway.service
  echo "[+] hermes-gateway.service enabled and started"
fi

# Firewall configuration if UFW is active
if command -v ufw &>/dev/null && ufw status | grep -qw "active"; then
  echo "--> Allowing Docker bridge subnets (172.16.0.0/12) to Hermes Dashboard port ${HERMES_DASHBOARD_PORT}..."
  ufw allow from 172.16.0.0/12 to any port "${HERMES_DASHBOARD_PORT}" proto tcp comment "Docker to Hermes Dashboard" >/dev/null || true
fi

echo ""
echo "========================================================================"
echo "  HERMES AGENT, DASHBOARD & GATEWAY INSTALLED SUCCESSFULLY"
echo "  CLI: Run 'hermes setup' or 'hermes chat'"
echo "  Web Dashboard: http://${HERMES_DASHBOARD_HOST}:${HERMES_DASHBOARD_PORT}"
echo "  Gateway Service: Running (Telegram/Discord listener)"
echo "========================================================================"
