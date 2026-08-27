#!/usr/bin/env bash
set -euo pipefail

echo "--> Starting OpenCode Web service..."
sudo systemctl start opencode-web.service
sudo systemctl status opencode-web.service --no-pager || true
