#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "========================================================================"
echo "  INSTALLING REMOTE DESKTOP (XFCE4, XRDP, KASMVNC)"
echo "========================================================================"

if [[ $EUID -ne 0 ]]; then
  echo "Error: This script must be run as root or with sudo." >&2
  exit 1
fi

load_env() {
  local env_file="$1"
  if [[ -f "$env_file" ]]; then
    while IFS='=' read -r key value || [[ -n "$key" ]]; do
      [[ "$key" =~ ^[[:space:]]*# ]] && continue
      [[ -z "$key" ]] && continue
      key="$(echo "$key" | tr -d '[:space:]')"
      # Strip quotes from value
      value="$(echo "$value" | sed -e "s/^[[:space:]]*['\"]*//" -e "s/['\"]*[[:space:]]*$//")"
      export "${key}=${value}"
    done < "$env_file"
  fi
}

if [[ -f .env ]]; then
  load_env .env
elif [[ -f .env.example ]]; then
  load_env .env.example
fi

DESKTOP_USER="${DESKTOP_USER:-jeisson}"
DESKTOP_PASSWORD="${DESKTOP_PASSWORD:-}"
KASMVNC_PORT="${KASMVNC_PORT:-8444}"
KASMVNC_BIND="${KASMVNC_BIND:-0.0.0.0}"
KASMVNC_DISPLAY="${KASMVNC_DISPLAY:-1}"
KASMVNC_RESOLUTION="${KASMVNC_RESOLUTION:-1920x1080}"
KASMVNC_DEPTH="${KASMVNC_DEPTH:-24}"
XRDP_PORT="${XRDP_PORT:-3389}"
XRDP_BIND="${XRDP_BIND:-127.0.0.1}"

# Verify target user exists
if ! id "$DESKTOP_USER" &>/dev/null; then
  echo "Error: User '$DESKTOP_USER' does not exist." >&2
  exit 1
fi

USER_HOME=$(eval echo "~$DESKTOP_USER")

# 1. Update and install desktop packages
echo "--> [1/6] Installing XFCE4, XRDP, and essential dependencies..."
DEBIAN_FRONTEND=noninteractive apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  xfce4 xfce4-goodies dbus-x11 xrdp xorgxrdp wget curl ca-certificates

# 2. Install KasmVNC if not present
echo "--> [2/6] Verifying / Installing KasmVNC Server..."
if ! command -v vncserver &>/dev/null || ! command -v kasmvncpasswd &>/dev/null; then
  echo "--> Downloading KasmVNC Noble/Ubuntu package..."
  TMP_DEB="/tmp/kasmvncserver.deb"
  wget -q -O "$TMP_DEB" "https://github.com/kasmtech/KasmVNC/releases/download/v1.5.0/kasmvncserver_noble_1.5.0_amd64.deb"
  apt-get install -y "$TMP_DEB"
  rm -f "$TMP_DEB"
  echo "--> KasmVNC installed successfully."
else
  echo "--> KasmVNC is already installed."
fi

# Add user to ssl-cert group if exists (required by xrdp / kasmvnc)
if getent group ssl-cert >/dev/null; then
  adduser "$DESKTOP_USER" ssl-cert || true
fi

# 3. Configure XRDP (Restricted to loopback / internal)
echo "--> [3/6] Configuring XRDP..."
if [[ -f /etc/xrdp/xrdp.ini ]]; then
  sed -i "s/^port=.*/port=${XRDP_BIND}:${XRDP_PORT}/" /etc/xrdp/xrdp.ini || true
fi

# Configure ~/.xsession for target user
cat << 'EOF' > "${USER_HOME}/.xsession"
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
export XDG_SESSION_TYPE=x11
export XDG_CURRENT_DESKTOP=XFCE
export DESKTOP_SESSION=xfce
exec dbus-launch --exit-with-session startxfce4
EOF
chown "${DESKTOP_USER}:${DESKTOP_USER}" "${USER_HOME}/.xsession"
chmod 755 "${USER_HOME}/.xsession"

systemctl enable xrdp
systemctl restart xrdp

# 4. Configure KasmVNC user environment
echo "--> [4/6] Configuring KasmVNC user environment for '$DESKTOP_USER'..."
mkdir -p "${USER_HOME}/.vnc"

# xstartup for KasmVNC
cp templates/xstartup "${USER_HOME}/.vnc/xstartup"
chmod +x "${USER_HOME}/.vnc/xstartup"

# kasmvnc.yaml configuration
mkdir -p "${USER_HOME}/.vnc"
cat << YAML > "${USER_HOME}/.vnc/kasmvnc.yaml"
desktop:
  resolution:
    width: $(echo "$KASMVNC_RESOLUTION" | cut -d'x' -f1)
    height: $(echo "$KASMVNC_RESOLUTION" | cut -d'x' -f2)
  allow_resize: true
  pixel_depth: ${KASMVNC_DEPTH}

network:
  protocol: http
  interface: ${KASMVNC_BIND}
  websocket_port: ${KASMVNC_PORT}
  use_ipv4: true
  use_ipv6: true
  ssl:
    require_ssl: false

logging:
  log_writer_name: all
  log_dest: logfile
  level: 30

data_loss_prevention:
  clipboard:
    server_to_client:
      enabled: true
    client_to_server:
      enabled: true
  keyboard:
    enabled: true

encoding:
  max_frame_rate: 60

server:
  http:
    httpd_directory: /usr/share/kasmvnc/www
  advanced:
    kasm_password_file: ${USER_HOME}/.kasmpasswd

command_line:
  prompt: false
YAML

# Configure password if provided
if [[ -n "$DESKTOP_PASSWORD" ]]; then
  echo "--> Setting KasmVNC credentials for user '$DESKTOP_USER'..."
  # Write password to ~/.kasmpasswd using -w -o
  rm -f "${USER_HOME}/.kasmpasswd" "${USER_HOME}/.vnc/.kasmpasswd"
  echo -e "${DESKTOP_PASSWORD}\n${DESKTOP_PASSWORD}\n" | kasmvncpasswd -u "$DESKTOP_USER" -w -o "${USER_HOME}/.kasmpasswd" 2>/dev/null || true
  cp -f "${USER_HOME}/.kasmpasswd" "${USER_HOME}/.vnc/.kasmpasswd" 2>/dev/null || true
  chown "${DESKTOP_USER}:${DESKTOP_USER}" "${USER_HOME}/.kasmpasswd" "${USER_HOME}/.vnc/.kasmpasswd" 2>/dev/null || true
  chmod 600 "${USER_HOME}/.kasmpasswd" "${USER_HOME}/.vnc/.kasmpasswd" 2>/dev/null || true
  
  # Also sync system password
  echo "${DESKTOP_USER}:${DESKTOP_PASSWORD}" | chpasswd
fi

chown -R "${DESKTOP_USER}:${DESKTOP_USER}" "${USER_HOME}/.vnc"

# 5. Configure Systemd Service for KasmVNC
echo "--> [5/6] Registering KasmVNC systemd service..."
cat << 'UNIT' > "/etc/systemd/system/kasmvnc@.service"
[Unit]
Description=KasmVNC HTML5 Remote Desktop Server for %i
After=network.target

[Service]
Type=forking
User=%i
Environment=HOME=/home/%i
Environment=USER=%i
PIDFile=/home/%i/.vnc/%H:1.pid
ExecStartPre=-/usr/bin/vncserver -kill :1
ExecStart=/usr/bin/vncserver :1 -select-de xfce
ExecStop=/usr/bin/vncserver -kill :1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable "kasmvnc@${DESKTOP_USER}"
systemctl restart "kasmvnc@${DESKTOP_USER}"
sleep 2

# 6. Firewall Configuration (UFW)
echo "--> [6/6] Configuring Firewall rules..."
if command -v ufw &>/dev/null && ufw status | grep -qw "active"; then
  echo "--> Allowing Docker bridge subnets (172.16.0.0/12) to KasmVNC port ${KASMVNC_PORT}..."
  ufw allow from 172.16.0.0/12 to any port "${KASMVNC_PORT}" proto tcp comment "Docker to KasmVNC" >/dev/null || true
  
  # Ensure XRDP is NOT exposed publicly, but allowed from localhost / wireguard
  ufw deny 3389/tcp comment "Block public XRDP" >/dev/null || true
fi

echo ""
echo "========================================================================"
echo "  REMOTE DESKTOP (XFCE4 + KASMVNC + XRDP) INSTALLED SUCCESSFULLY"
echo "  KasmVNC Status:"
systemctl status "kasmvnc@${DESKTOP_USER}" --no-pager || true
echo "========================================================================"
