#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

DESKTOP_USER="${SUDO_USER:-$(id -un)}"

# Safe parsing of .env without variable expansion
load_env_safe() {
  local env_file="$1"
  if [[ -f "$env_file" ]]; then
    while IFS='=' read -r key val || [[ -n "$key" ]]; do
      # Strip leading/trailing whitespace
      key="$(echo "$key" | xargs)"
      # Ignore comments and empty lines
      [[ -z "$key" || "$key" =~ ^# ]] && continue
      # Strip quotes from value
      val="${val%\"}"
      val="${val#\"}"
      val="${val%\'}"
      val="${val#\'}"
      case "$key" in
        DESKTOP_USER) DESKTOP_USER="$val" ;;
      esac
    done < "$env_file"
  fi
}

if [[ -f .env ]]; then
  load_env_safe .env
elif [[ -f .env.example ]]; then
  load_env_safe .env.example
fi

echo "========================================================================"
echo "  REMOTE DESKTOP STATUS (KASMVNC & XRDP)"
echo "========================================================================"
echo "--> KasmVNC Socket (On-Demand 0 MB idle):"
systemctl status kasmvnc.socket --no-pager || true

echo ""
echo "--> KasmVNC Desktop Session (kasmvnc@${DESKTOP_USER}):"
systemctl status "kasmvnc@${DESKTOP_USER}" --no-pager || true

echo ""
echo "--> XRDP Service:"
systemctl status xrdp --no-pager || true

echo ""
echo "--> Listening Ports:"
ss -tulpn | grep -E "8444|8445|3389|vnc|xrdp" || true
echo "========================================================================"
