#!/usr/bin/env bash
set -euo pipefail

echo "==> [02/11] Configuring administrative (non-root) user..."

if [[ $EUID -ne 0 ]]; then
  echo "Error: This script must be run as root or with sudo." >&2
  exit 1
fi

NEW_USER="${NEW_USER:-deploy}"
NEW_USER_PASSWORD="${NEW_USER_PASSWORD:-}"
NEW_USER_SSH_KEY="${NEW_USER_SSH_KEY:-}"
PASSWORDLESS_SUDO="${PASSWORDLESS_SUDO:-yes}"

# 1. Create user if it doesn't already exist
if id "$NEW_USER" &>/dev/null; then
  echo "--> User '$NEW_USER' already exists. Updating configuration..."
else
  echo "--> Creating user '$NEW_USER'..."
  useradd -m -s /bin/bash "$NEW_USER"
  
  if [[ -n "$NEW_USER_PASSWORD" ]]; then
    echo "$NEW_USER:$NEW_USER_PASSWORD" | chpasswd
  else
    # Lock password until set, or allow key-only login
    passwd -d "$NEW_USER" 2>/dev/null || true
  fi
fi

# 2. Add to sudo group
usermod -aG sudo "$NEW_USER"

# 3. Configure sudo privileges
SUDOERS_FILE="/etc/sudoers.d/99-${NEW_USER}-sudo"
if [[ "$PASSWORDLESS_SUDO" == "yes" ]]; then
  echo "$NEW_USER ALL=(ALL) NOPASSWD:ALL" > "$SUDOERS_FILE"
else
  echo "$NEW_USER ALL=(ALL) ALL" > "$SUDOERS_FILE"
fi
chmod 0440 "$SUDOERS_FILE"

# 4. Configure SSH authorized keys
USER_HOME="$(eval echo "~$NEW_USER")"
mkdir -p "$USER_HOME/.ssh"
chmod 700 "$USER_HOME/.ssh"

AUTH_KEYS_FILE="$USER_HOME/.ssh/authorized_keys"

if [[ -n "$NEW_USER_SSH_KEY" ]]; then
  echo "--> Adding provided SSH key to $AUTH_KEYS_FILE..."
  if ! grep -Fxq "$NEW_USER_SSH_KEY" "$AUTH_KEYS_FILE" 2>/dev/null; then
    echo "$NEW_USER_SSH_KEY" >> "$AUTH_KEYS_FILE"
  fi
elif [[ -f /root/.ssh/authorized_keys ]] && [[ -s /root/.ssh/authorized_keys ]]; then
  echo "--> Copying existing root authorized_keys to '$NEW_USER'..."
  cp /root/.ssh/authorized_keys "$AUTH_KEYS_FILE"
else
  echo "--> Note: No SSH key provided and /root/.ssh/authorized_keys was empty."
  touch "$AUTH_KEYS_FILE"
fi

chmod 600 "$AUTH_KEYS_FILE"
chown -R "$NEW_USER:$NEW_USER" "$USER_HOME/.ssh"

echo "--> User '$NEW_USER' configured with sudo access and SSH directory."
