#!/usr/bin/env bash
set -euo pipefail

echo "==> Configuring Passwordless Sudo..."

if [[ $EUID -ne 0 ]]; then
  echo "Error: This script must be run as root or with sudo." >&2
  exit 1
fi

TARGET_USER="${1:-${NEW_USER:-${SUDO_USER:-$(logname 2>/dev/null || echo "deploy")}}}"

if ! id "$TARGET_USER" &>/dev/null; then
  echo "Error: User '$TARGET_USER' does not exist." >&2
  exit 1
fi

# Ensure user is part of the sudo group
usermod -aG sudo "$TARGET_USER"

# Configure sudoers file
SUDOERS_FILE="/etc/sudoers.d/99-${TARGET_USER}-sudo"
TEMP_SUDOERS="$(mktemp)"

echo "--> Generating sudoers rule for user '$TARGET_USER'..."
echo "${TARGET_USER} ALL=(ALL:ALL) NOPASSWD: ALL" > "$TEMP_SUDOERS"
chmod 0440 "$TEMP_SUDOERS"

# Validate syntax with visudo
if visudo -cf "$TEMP_SUDOERS"; then
  cp "$TEMP_SUDOERS" "$SUDOERS_FILE"
  chmod 0440 "$SUDOERS_FILE"
  rm -f "$TEMP_SUDOERS"
  echo "--> Passwordless sudo successfully enabled for '$TARGET_USER' at $SUDOERS_FILE"
else
  rm -f "$TEMP_SUDOERS"
  echo "Error: Generated sudoers syntax is invalid. Aborting." >&2
  exit 1
fi
