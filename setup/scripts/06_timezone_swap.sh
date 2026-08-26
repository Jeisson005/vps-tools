#!/usr/bin/env bash
set -euo pipefail

echo "==> [06/11] Configuring Timezone and Swap space..."

if [[ $EUID -ne 0 ]]; then
  echo "Error: This script must be run as root or with sudo." >&2
  exit 1
fi

TIMEZONE="${TIMEZONE:-UTC}"
SWAP_SIZE="${SWAP_SIZE:-4G}"
SWAPPINESS="${SWAPPINESS:-10}"

# 1. Configure Timezone
echo "--> Setting system timezone to $TIMEZONE..."
timedatectl set-timezone "$TIMEZONE" || true

# 2. Check existing swap
existing_swap="$(swapon --show --noheadings | wc -l)"

if [[ "$existing_swap" -gt 0 ]]; then
  echo "--> Swap is already configured and active:"
  swapon --show
else
  if [[ "$SWAP_SIZE" != "0" ]] && [[ -n "$SWAP_SIZE" ]]; then
    echo "--> Creating $SWAP_SIZE swapfile at /swapfile..."
    
    # Try fallocate first; fallback to dd if file system doesn't support fallocate
    if ! fallocate -l "$SWAP_SIZE" /swapfile 2>/dev/null; then
      # Convert 4G/2G to MB for dd
      size_mb=4096
      [[ "$SWAP_SIZE" =~ ^([0-9]+)G$ ]] && size_mb=$((${BASH_REMATCH[1]} * 1024))
      [[ "$SWAP_SIZE" =~ ^([0-9]+)M$ ]] && size_mb=${BASH_REMATCH[1]}
      dd if=/dev/zero of=/swapfile bs=1M count="$size_mb" status=progress
    fi

    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile

    # Persist in fstab if not present
    if ! grep -q '/swapfile' /etc/fstab; then
      echo '/swapfile none swap sw 0 0' >> /etc/fstab
    fi
    echo "--> Swap space successfully enabled."
  else
    echo "--> Swap creation skipped."
  fi
fi

# 3. Optimize swappiness
echo "--> Optimizing vm.swappiness=$SWAPPINESS and vm.vfs_cache_pressure=50..."
cat <<EOF > /etc/sysctl.d/99-swap.conf
vm.swappiness = $SWAPPINESS
vm.vfs_cache_pressure = 50
EOF
sysctl -p /etc/sysctl.d/99-swap.conf >/dev/null 2>&1 || true

echo "--> Timezone and Swap setup completed."
