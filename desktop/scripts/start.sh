#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

DESKTOP_USER="jeisson"

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

echo "--> Starting Remote Desktop on-demand socket and XRDP..."
sudo systemctl enable --now kasmvnc.socket
sudo systemctl start "kasmvnc@${DESKTOP_USER}"
sudo systemctl start xrdp

echo "--> Services started."
sudo systemctl status kasmvnc.socket --no-pager || true
