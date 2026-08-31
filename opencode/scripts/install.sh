#!/usr/bin/env bash
set -euo pipefail

# Ensure we are in the opencode directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENCODE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${OPENCODE_DIR}"

echo "========================================================================"
echo "  INSTALLING OPENCODE AI (CLI, MCPs, SKILLS & WEB INTERFACE)"
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
        MCP_API_KEY) MCP_API_KEY="$val" ;;
        PASSBOLT_MCP_URL) PASSBOLT_MCP_URL="$val" ;;
        OPENCODE_LOG_LEVEL) OPENCODE_LOG_LEVEL="$val" ;;
      esac
    done < "$env_file"
  fi
}

# Defaults
OPENCODE_USER="${SUDO_USER:-$(id -un)}"
OPENCODE_WORKSPACE="/home/${OPENCODE_USER}"
OPENCODE_PORT="4096"
OPENCODE_HOST="0.0.0.0"
OPENCODE_SERVER_USERNAME="${OPENCODE_USER}"
OPENCODE_SERVER_PASSWORD=""
BRAVE_API_KEY=""
MCP_API_KEY=""
PASSBOLT_MCP_URL="http://127.0.0.1:8005/passbolt/sse"
OPENCODE_LOG_LEVEL="INFO"

if [[ -f .env ]]; then
  load_env_safe .env
elif [[ -f .env.example ]]; then
  load_env_safe .env.example
fi

# Auto-detect MCP_API_KEY from mcp/.env if empty
if [[ -z "$MCP_API_KEY" && -f "${OPENCODE_DIR}/../mcp/.env" ]]; then
  DETECTED_KEY=$(grep "^MCP_API_KEY=" "${OPENCODE_DIR}/../mcp/.env" 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'" || true)
  if [[ -n "$DETECTED_KEY" ]]; then
    MCP_API_KEY="$DETECTED_KEY"
    echo "[+] Auto-detected MCP_API_KEY from vps-tools/mcp/.env"
  fi
fi

USER_HOME="$(eval echo ~${OPENCODE_USER})"

# 1. Install prerequisites (curl, ca-certificates, nodejs, npm)
echo "--> [1/6] Checking prerequisites..."
apt-get update -qq
apt-get install -y -qq curl ca-certificates

if ! command -v node &>/dev/null; then
  echo "--> Installing Node.js..."
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y -qq nodejs
fi

# 2. Download and install OpenCode binary natively
echo "--> [2/6] Downloading and installing OpenCode native binary..."
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
echo "--> [3/6] Installing MCP servers (@brave/brave-search-mcp-server & @playwright/mcp)..."
OPENCODE_CONFIG_DIR="${USER_HOME}/.config/opencode"
mkdir -p "${OPENCODE_CONFIG_DIR}"
mkdir -p "${USER_HOME}/.config/steel/profiles/persistent"
chown -R "${OPENCODE_USER}:${OPENCODE_USER}" "${USER_HOME}/.config/steel" 2>/dev/null || true

su - "${OPENCODE_USER}" -c "mkdir -p ~/.config/opencode && cd ~/.config/opencode && npm install --save-dev @brave/brave-search-mcp-server @playwright/mcp 2>&1"
su - "${OPENCODE_USER}" -c "npx playwright install chromium 2>/dev/null || true"

# Resolve STEEL_DOMAIN if available
STEEL_DOMAIN="browser.localhost"
if [[ -f "${OPENCODE_DIR}/../steel/.env" ]]; then
  STEEL_DOMAIN_FROM_ENV=$(grep "^STEEL_DOMAIN=" "${OPENCODE_DIR}/../steel/.env" 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'" || true)
  if [[ -n "$STEEL_DOMAIN_FROM_ENV" ]]; then
    STEEL_DOMAIN="$STEEL_DOMAIN_FROM_ENV"
  fi
fi

# Configure opencode.jsonc dynamically based on available/configured modules
if [[ -f "${OPENCODE_DIR}/templates/INSTRUCTIONS.md" ]]; then
  cp "${OPENCODE_DIR}/templates/INSTRUCTIONS.md" "${OPENCODE_CONFIG_DIR}/INSTRUCTIONS.md"
  chown "${OPENCODE_USER}:${OPENCODE_USER}" "${OPENCODE_CONFIG_DIR}/INSTRUCTIONS.md"
fi

python3 - << PY
import json, os

config = {
    "\$schema": "https://opencode.ai/config.json",
    "plugin": [],
    "instructions": [
        "${OPENCODE_CONFIG_DIR}/INSTRUCTIONS.md"
    ],
    "mcp": {}
}

# 1. Brave Search MCP (if API key provided)
brave_key = "${BRAVE_API_KEY}"
if brave_key:
    config["mcp"]["brave-search"] = {
        "type": "local",
        "command": [
            "node",
            "${OPENCODE_CONFIG_DIR}/node_modules/@brave/brave-search-mcp-server/dist/index.js"
        ],
        "environment": {
            "BRAVE_API_KEY": brave_key
        }
    }

# 2. Browser Automation MCP (Steel Browser if installed, else fallback to standard Playwright)
has_steel = os.path.exists("/usr/local/bin/steel-mcp") or os.path.exists("${OPENCODE_DIR}/../steel/.env")
if has_steel:
    config["mcp"]["playwright"] = {
        "type": "local",
        "command": ["steel-mcp", "--isolated"]
    }
    config["mcp"]["playwright-persistent"] = {
        "type": "local",
        "command": [
            "steel-mcp",
            "--user-data-dir",
            "${USER_HOME}/.config/steel/profiles/persistent",
            "--shared-browser-context"
        ]
    }
else:
    config["mcp"]["playwright"] = {
        "type": "local",
        "command": ["npx", "@playwright/mcp"]
    }

# 3. Passbolt MCP (if API key provided)
mcp_key = "${MCP_API_KEY}"
if mcp_key:
    config["mcp"]["passbolt"] = {
        "type": "remote",
        "url": "${PASSBOLT_MCP_URL}",
        "headers": {
            "Authorization": f"Bearer {mcp_key}"
        }
    }

# 4. Sentinel Tasks & Self-Healing MCP
config["mcp"]["sentinel"] = {
    "type": "remote",
    "url": "http://127.0.0.1:8006/sse"
}

out_path = "${OPENCODE_CONFIG_DIR}/opencode.jsonc"
with open(out_path, "w") as f:
    json.dump(config, f, indent=2)

print(f"[+] Configured {out_path} with {len(config['mcp'])} active MCP server(s): {', '.join(config['mcp'].keys()) or 'none'}")
PY

chown -R "${OPENCODE_USER}:${OPENCODE_USER}" "${OPENCODE_CONFIG_DIR}"

# 4. Synchronize Curated Skills
echo "--> [4/6] Synchronizing curated skills to ~/.config/opencode/skills..."
if [[ -f "${OPENCODE_DIR}/../skills/scripts/sync_skills.sh" ]]; then
  bash "${OPENCODE_DIR}/../skills/scripts/sync_skills.sh" \
    --target opencode \
    --user "${OPENCODE_USER}" \
    --steel-domain "${STEEL_DOMAIN}"
fi

# 5. Configure Environment File for Service Authentication
echo "--> [5/6] Configuring OpenCode authentication and environment..."
ENV_DEFAULT="/etc/default/opencode-web"
cat << EOF > "${ENV_DEFAULT}"
OPENCODE_PORT=${OPENCODE_PORT}
OPENCODE_HOST=${OPENCODE_HOST}
OPENCODE_SERVER_USERNAME=${OPENCODE_SERVER_USERNAME}
OPENCODE_SERVER_PASSWORD=${OPENCODE_SERVER_PASSWORD}
OPENCODE_LOG_LEVEL=${OPENCODE_LOG_LEVEL}
EOF
chmod 600 "${ENV_DEFAULT}"

# 6. Configure Systemd Service for OpenCode Web
echo "--> [6/6] Registering and enabling opencode-web systemd service..."
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
echo "  OPENCODE AI, MCPs & SKILLS INSTALLED SUCCESSFULLY"
echo "  CLI binary: /usr/local/bin/opencode (opencode --version)"
echo "  Skills:     ~/.config/opencode/skills/"
echo "  MCP Status:"
su - "${OPENCODE_USER}" -c "opencode mcp list" || true
echo "  Web status:"
systemctl status opencode-web.service --no-pager || true
echo "========================================================================"
