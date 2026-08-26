#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
elif [[ -f .env.example ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.example
  set +a
fi

MCP_PORT="${MCP_PORT:-8001}"
MCP_BIND="${MCP_BIND:-127.0.0.1}"
ENDPOINT="http://${MCP_BIND}:${MCP_PORT}/mcp"

echo "==> Testing Bash-MCP HTTP Endpoint at $ENDPOINT..."

response="$(
  curl -s -X POST "$ENDPOINT" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test-client","version":"1.0"}}}' \
    || true
)"

if echo "$response" | grep -q "serverInfo"; then
  echo "--> Success! MCP Server responded with valid handshake:"
  echo "$response"
else
  echo "--> Response received:"
  echo "$response"
fi
