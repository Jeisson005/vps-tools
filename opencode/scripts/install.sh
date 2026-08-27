#!/usr/bin/env bash
set -euo pipefail

# Ensure we are in the opencode directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENCODE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${OPENCODE_DIR}"

echo "========================================================================"
echo "  INSTALLING OPENCODE AI (CLI, MCPs & WEB INTERFACE)"
echo "========================================================================"

# Check root privileges
if [[ $EUID -ne 0 ]]; then
  echo "[-] ERROR: This installation script must be run with sudo or as root." >&2
  exit 1
fi

# Safe .env loader without arbitrary variable expansion
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
        OPENCODE_USER) OPENCODE_USER="$val" ;;
        OPENCODE_WORKSPACE) OPENCODE_WORKSPACE="$val" ;;
        OPENCODE_PORT) OPENCODE_PORT="$val" ;;
        OPENCODE_HOST) OPENCODE_HOST="$val" ;;
        OPENCODE_SERVER_USERNAME) OPENCODE_SERVER_USERNAME="$val" ;;
        OPENCODE_SERVER_PASSWORD) OPENCODE_SERVER_PASSWORD="$val" ;;
        BRAVE_API_KEY) BRAVE_API_KEY="$val" ;;
        OPENCODE_LOG_LEVEL) OPENCODE_LOG_LEVEL="$val" ;;
      esac
    done < "$env_file"
  fi
}

# Defaults
OPENCODE_USER="${SUDO_USER:-jeisson}"
OPENCODE_WORKSPACE="/home/${OPENCODE_USER}"
OPENCODE_PORT="4096"
OPENCODE_HOST="0.0.0.0"
OPENCODE_SERVER_USERNAME="${OPENCODE_USER}"
OPENCODE_SERVER_PASSWORD=""
BRAVE_API_KEY=""
OPENCODE_LOG_LEVEL="INFO"

if [[ -f .env ]]; then
  load_env_safe .env
elif [[ -f .env.example ]]; then
  load_env_safe .env.example
fi

USER_HOME="$(eval echo ~${OPENCODE_USER})"

# 1. Install prerequisites (curl, ca-certificates, nodejs, npm)
echo "--> [1/5] Checking prerequisites..."
apt-get update -qq
apt-get install -y -qq curl ca-certificates

if ! command -v node &>/dev/null; then
  echo "--> Installing Node.js..."
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y -qq nodejs
fi

# 2. Download and install OpenCode binary natively
echo "--> [2/5] Downloading and installing OpenCode native binary..."
su - "${OPENCODE_USER}" -c 'curl -fsSL https://opencode.ai/install | bash'

# Locate binary and symlink to /usr/local/bin/opencode
OPENCODE_BIN=""
if [[ -f "${USER_HOME}/.opencode/bin/opencode" ]]; then
  OPENCODE_BIN="${USER_HOME}/.opencode/bin/opencode"
elif [[ -f "${USER_HOME}/.local/bin/opencode" ]]; then
  OPENCODE_BIN="${USER_HOME}/.local/bin/opencode"
fi

if [[ -n "$OPENCODE_BIN" && -f "$OPENCODE_BIN" ]]; then
  ln -sf "$OPENCODE_BIN" /usr/local/bin/opencode
  chmod +x "$OPENCODE_BIN" /usr/local/bin/opencode
  echo "--> OpenCode binary linked to /usr/local/bin/opencode"
else
  echo "[-] ERROR: OpenCode binary could not be found after installation." >&2
  exit 1
fi

# 3. Install MCP Dependencies & Create Persistent Directories
echo "--> [3/5] Installing MCP servers (@brave/brave-search-mcp-server & @playwright/mcp)..."
OPENCODE_CONFIG_DIR="${USER_HOME}/.config/opencode"
mkdir -p "${OPENCODE_CONFIG_DIR}"
mkdir -p "${USER_HOME}/.config/steel/profiles/persistent"
chown -R "${OPENCODE_USER}:${OPENCODE_USER}" "${USER_HOME}/.config/steel" 2>/dev/null || true

su - "${OPENCODE_USER}" -c "mkdir -p ~/.config/opencode && cd ~/.config/opencode && npm install --save-dev @brave/brave-search-mcp-server @playwright/mcp 2>&1"
su - "${OPENCODE_USER}" -c "npx playwright install chromium 2>/dev/null || true"

# Configure opencode.jsonc from template
OPENCODE_CONF_DIR="${USER_HOME}/.config/opencode"
sed \
  -e "s|{{OPENCODE_CONFIG_DIR}}|${OPENCODE_CONF_DIR}|g" \
  -e "s|{{USER_HOME}}|${USER_HOME}|g" \
  -e "s|{{BRAVE_API_KEY}}|${BRAVE_API_KEY}|g" \
  "${OPENCODE_DIR}/templates/opencode.jsonc" > "${OPENCODE_CONF_DIR}/opencode.jsonc"
chown -R "${OPENCODE_USER}:${OPENCODE_USER}" "${OPENCODE_CONF_DIR}"

# 4. Configure Environment File for Service Authentication
echo "--> [4/5] Configuring OpenCode authentication and environment..."
ENV_DEFAULT="/etc/default/opencode-web"
cat << EOF > "${ENV_DEFAULT}"
OPENCODE_PORT=${OPENCODE_PORT}
OPENCODE_HOST=${OPENCODE_HOST}
OPENCODE_SERVER_USERNAME=${OPENCODE_SERVER_USERNAME}
OPENCODE_SERVER_PASSWORD=${OPENCODE_SERVER_PASSWORD}
OPENCODE_LOG_LEVEL=${OPENCODE_LOG_LEVEL}
EOF
chmod 600 "${ENV_DEFAULT}"

# 5. Configure Systemd Service for OpenCode Web
echo "--> [5/5] Registering and enabling opencode-web systemd service..."
SERVICE_FILE="/etc/systemd/system/opencode-web.service"
sed \
  -e "s|{{OPENCODE_USER}}|${OPENCODE_USER}|g" \
  -e "s|{{OPENCODE_WORKSPACE}}|${OPENCODE_WORKSPACE}|g" \
  -e "s|{{OPENCODE_PORT}}|${OPENCODE_PORT}|g" \
  -e "s|{{OPENCODE_HOST}}|${OPENCODE_HOST}|g" \
  -e "s|{{OPENCODE_LOG_LEVEL}}|${OPENCODE_LOG_LEVEL}|g" \
  "${OPENCODE_DIR}/templates/opencode-web.service" > "${SERVICE_FILE}"

systemctl daemon-reload
systemctl enable opencode-web.service
systemctl restart opencode-web.service
sleep 2

# Firewall configuration if UFW is active
if command -v ufw &>/dev/null && ufw status | grep -qw "active"; then
  echo "--> Allowing Docker bridge subnets (172.16.0.0/12) to OpenCode Web port ${OPENCODE_PORT}..."
  ufw allow from 172.16.0.0/12 to any port "${OPENCODE_PORT}" proto tcp comment "Docker to OpenCode Web" >/dev/null || true
fi

echo ""
echo "========================================================================"
echo "  OPENCODE AI & MCPs INSTALLED SUCCESSFULLY"
echo "  CLI binary: /usr/local/bin/opencode (opencode --version)"
echo "  MCP Status:"
su - "${OPENCODE_USER}" -c "opencode mcp list" || true
echo "  Web status:"
systemctl status opencode-web.service --no-pager || true
echo "========================================================================"
