#!/usr/bin/env bash
# ==============================================================================
# Install RustDesk Host Client (controlled side)
# Captures the local desktop (DISPLAY=:1, KasmVNC/XFCE) so any RustDesk app
# pointed at your self-hosted server can remote-control this VPS.
#
# Usage: sudo bash scripts/install_host_client.sh
# Re-runnable: skips install when the pinned version is present.
# ==============================================================================

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Error: run as root (sudo)." >&2
  exit 1
fi

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BASE_DIR}"

if [[ ! -f ".env" ]]; then
  echo "[!] .env not found, creating from .env.example..."
  cp .env.example .env
  chmod 600 .env
fi

# shellcheck disable=SC1091
set -a; source .env; set +a

RUSTDESK_VERSION="${RUSTDESK_VERSION:-1.4.9}"
RUSTDESK_HOST_USER="${RUSTDESK_HOST_USER:-${SUDO_USER:-jeisson}}"
RUSTDESK_DOMAIN="${RUSTDESK_DOMAIN:-rustdesk.jeisson.top}"
RUSTDESK_RENDEZVOUS="${RUSTDESK_RENDEZVOUS:-127.0.0.1:21116}"
RUSTDESK_RELAY="${RUSTDESK_RELAY:-${RUSTDESK_DOMAIN}:21117}"
RUSTDESK_HOST_PASSWORD="${RUSTDESK_HOST_PASSWORD:-}"

if ! id "${RUSTDESK_HOST_USER}" &>/dev/null; then
  echo "Error: user '${RUSTDESK_HOST_USER}' does not exist." >&2
  exit 1
fi

ARCH="$(dpkg --print-architecture)"
if [[ "${ARCH}" != "amd64" ]]; then
  echo "Error: only amd64 .deb is supported by this script (arch: ${ARCH})." >&2
  exit 1
fi

USER_HOME="$(eval echo "~${RUSTDESK_HOST_USER}")"

# --- 1. Install client .deb (pinned, idempotent) ---
NEED_INSTALL=true
if command -v rustdesk &>/dev/null; then
  INSTALLED="$(rustdesk --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1 || true)"
  if [[ "${INSTALLED}" == "${RUSTDESK_VERSION}" ]]; then
    echo "[+] rustdesk ${INSTALLED} already installed, skipping download."
    NEED_INSTALL=false
  else
    echo "[+] rustdesk installed (${INSTALLED:-unknown}), wanted ${RUSTDESK_VERSION} — upgrading."
  fi
fi

if [[ "${NEED_INSTALL}" == "true" ]]; then
  DEB_URL="https://github.com/rustdesk/rustdesk/releases/download/${RUSTDESK_VERSION}/rustdesk-${RUSTDESK_VERSION}-x86_64.deb"
  echo "[+] Downloading rustdesk ${RUSTDESK_VERSION}..."
  TMP_DEB="/tmp/rustdesk-client.deb"
  if ! curl -fSL --retry 3 -o "${TMP_DEB}" "${DEB_URL}"; then
    echo "Error: could not download ${DEB_URL}" >&2
    exit 1
  fi
  DEBIAN_FRONTEND=noninteractive apt-get install -y "${TMP_DEB}"
  rm -f "${TMP_DEB}"
fi

# --- 2. Server public key (required against self-hosted MITM) ---
PUB_KEY=""
if [[ -f "data/id_ed25519.pub" ]]; then
  PUB_KEY="$(cat data/id_ed25519.pub)"
else
  echo "[!] data/id_ed25519.pub not found — is hbbs running? (bash scripts/start.sh)" >&2
  echo "    Continuing without pinned key; set it later in RustDesk2.toml." >&2
fi

# --- 3. Client config for the desktop user ---
echo "[+] Writing client config for '${RUSTDESK_HOST_USER}'..."
mkdir -p "${USER_HOME}/.config/rustdesk"
cat > "${USER_HOME}/.config/rustdesk/RustDesk2.toml" << EOF
[options]
custom-rendezvous-server = '${RUSTDESK_RENDEZVOUS}'
relay-server = '${RUSTDESK_RELAY}'
key = '${PUB_KEY}'
allow-audio = 'Y'
allow-clipboard = 'Y'
allow-file-transfer = 'Y'
allow-keyboard-mouse = 'Y'
EOF
chown -R "${RUSTDESK_HOST_USER}:${RUSTDESK_HOST_USER}" "${USER_HOME}/.config/rustdesk"
chmod 600 "${USER_HOME}/.config/rustdesk/RustDesk2.toml"

# --- 4. Permanent password placeholder (real value set via daemon below) ---
# NOTE: `rustdesk --password` only works through the RUNNING daemon and
# requires root (`is_installed() && is_root()`), otherwise it prints
# "Installation and administrative privileges required!" and changes nothing.
# So the password is applied in step 6, after the service is up.
if [[ -z "${RUSTDESK_HOST_PASSWORD}" ]]; then
  RUSTDESK_HOST_PASSWORD="$(openssl rand -hex 12)"
  echo "[+] Generated host password, storing in .env ..."
  if grep -q "^RUSTDESK_HOST_PASSWORD=" .env; then
    sed -i "s|^RUSTDESK_HOST_PASSWORD=.*|RUSTDESK_HOST_PASSWORD=${RUSTDESK_HOST_PASSWORD}|" .env
  else
    echo "RUSTDESK_HOST_PASSWORD=${RUSTDESK_HOST_PASSWORD}" >> .env
  fi
  chmod 600 .env
fi

# --- 5. Systemd service (own unit; upstream one stays disabled) ---
echo "[+] Registering rustdesk-host@${RUSTDESK_HOST_USER} ..."
cp templates/rustdesk-host.service /etc/systemd/system/'rustdesk-host@.service'
systemctl disable --now rustdesk.service 2>/dev/null || true
systemctl daemon-reload
systemctl enable --now "rustdesk-host@${RUSTDESK_HOST_USER}"
sleep 5

# --- 6. Permanent password via running daemon (must be root, service up) ---
echo "[+] Setting permanent password via daemon..."
if ! rustdesk --password "${RUSTDESK_HOST_PASSWORD}" 2>&1 | grep -q "Done!"; then
  echo "Error: daemon rejected the password (is rustdesk-host@${RUSTDESK_HOST_USER} active?)." >&2
  exit 1
fi

# --- 6. Report numeric ID ---
echo "[+] Waiting for ID registration..."
HOST_ID=""
for _i in $(seq 1 20); do
  HOST_ID="$(sudo -u "${RUSTDESK_HOST_USER}" rustdesk --get-id 2>/dev/null || true)"
  if [[ "${HOST_ID}" =~ ^[0-9]{9,}$ ]]; then
    break
  fi
  HOST_ID=""
  sleep 3
done

echo ""
echo "================================================================="
echo "✅ RustDesk Host Client Running (captures DISPLAY=:1)"
systemctl is-active "rustdesk-host@${RUSTDESK_HOST_USER}" --quiet && echo "• Service:  active" || echo "• Service:  NOT active — check journalctl -u rustdesk-host@${RUSTDESK_HOST_USER}"
echo "• Host ID:  ${HOST_ID:-<not registered yet — retry 'rustdesk --get-id' in a minute>}"
echo "• Password: (stored in rustdesk/.env as RUSTDESK_HOST_PASSWORD)"
echo "• From your laptop/phone app (server ${RUSTDESK_DOMAIN} + key): connect to ID ${HOST_ID}"
echo "================================================================="
