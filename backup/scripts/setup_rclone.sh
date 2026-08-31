#!/usr/bin/env bash
# ==============================================================================
# Helper to install Rclone and configure Google Drive remote
# ==============================================================================

set -euo pipefail

echo "================================================================="
echo "🔧 Rclone Setup for Google Drive Backup on your VPS"
echo "================================================================="

# 1. Install rclone if not installed
if ! command -v rclone &>/dev/null; then
  echo "[+] Installing official rclone..."
  curl -fsSL https://rclone.org/install.sh | sudo bash
  echo "[+] ✓ Rclone installed successfully ($(rclone --version | head -n1))"
else
  echo "[+] ✓ Rclone is already installed ($(rclone --version | head -n1))"
fi

echo ""
echo "================================================================="
echo "📋 Steps to link your Google Drive:"
echo "================================================================="
echo "1. Run: rclone config"
echo "2. Choose: 'n' (New remote)"
echo "3. Name: 'gdrive'"
echo "4. Storage: 'drive' (Google Drive)"
echo "5. client_id & client_secret: Press ENTER (leave blank)"
echo "6. scope: Choose '1' (Full access to all files)"
echo "7. service_account_file: ENTER (blank)"
echo "8. Edit advanced config: 'n' (No)"
echo "9. Use web browser to authenticate: 'n' (Headless VPS mode)"
echo "   -> Run the provided rclone authorize command on local PC, or paste code"
echo "10. Configure as a team drive: 'n' (No)"
echo "11. Confirm and quit with 'q'."
echo "================================================================="
echo ""
read -r -p "Do you want to run 'rclone config' right now? [y/N]: " RESP
if [[ "${RESP}" =~ ^[yYsS]$ ]]; then
  rclone config
fi

echo ""
echo "[+] Verifying Google Drive connection..."
if rclone lsd gdrive: &>/dev/null; then
  echo "✅ Connection to Google Drive successful!"
  rclone mkdir gdrive:vps-tools-backups/daily 2>/dev/null || true
  rclone mkdir gdrive:vps-tools-backups/monthly 2>/dev/null || true
  rclone mkdir gdrive:vps-tools-backups/manual 2>/dev/null || true
  echo "📁 Folders 'daily', 'monthly', and 'manual' ready on Google Drive."
else
  echo "⚠️ Remote 'gdrive' not detected yet. You can run 'rclone config' anytime."
fi

# 2. Configure Backup Encryption Master Key
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${BASE_DIR}/.env"

echo ""
echo "================================================================="
echo "🔐 Backup Encryption Master Key Setup (GPG AES-256)"
echo "================================================================="
echo "⚠️  IMPORTANT: Backups are encrypted so no one can read your"
echo "   files or passwords on Google Drive. Save this master key"
echo "   in your personal password manager (1Password, Bitwarden, etc.)."
echo "   Without this key, you CANNOT restore data if the VPS is lost."
echo "================================================================="

if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${BASE_DIR}/.env.example" "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
fi

CURRENT_KEY=$(grep -E '^BACKUP_ENCRYPTION_KEY=' "${ENV_FILE}" | cut -d'=' -f2- | tr -d '"' || true)

if [[ -n "${CURRENT_KEY}" && "${CURRENT_KEY}" != *"ChangeThis"* ]]; then
  echo "Your current configured key is:"
  echo "👉 ${CURRENT_KEY}"
  echo ""
  read -r -p "Do you want to change it to your own key? [y/N]: " CHANGE_KEY
  if [[ "${CHANGE_KEY}" =~ ^[yYsS]$ ]]; then
    read -r -s -p "Enter your new master key: " NEW_KEY
    echo ""
    if [[ -n "${NEW_KEY}" ]]; then
      sed -i "s/^BACKUP_ENCRYPTION_KEY=.*/BACKUP_ENCRYPTION_KEY=\"${NEW_KEY}\"/" "${ENV_FILE}"
      echo "✅ Master key updated in ${ENV_FILE}."
    fi
  fi
else
  read -r -s -p "Enter your backup encryption master key: " USER_KEY
  echo ""
  if [[ -z "${USER_KEY}" ]]; then
    USER_KEY=$(openssl rand -hex 24)
    echo "Generated random secure master key: ${USER_KEY}"
  fi
  sed -i "s/^BACKUP_ENCRYPTION_KEY=.*/BACKUP_ENCRYPTION_KEY=\"${USER_KEY}\"/" "${ENV_FILE}"
  echo "✅ Master key saved to ${ENV_FILE}."
  echo "⚠️  Copy and store it now in your password manager: ${USER_KEY}"
fi
