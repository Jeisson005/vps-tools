#!/usr/bin/env bash
set -euo pipefail

echo "--> Stopping OpenCode Web service..."
sudo systemctl stop opencode-web.service || true
echo "--> Service stopped."
