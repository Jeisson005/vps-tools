#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

PORT=$(grep -E "^MCP_PORT=" .env 2>/dev/null | cut -d '=' -f2 || echo "8005")
API_KEY=$(grep -E "^MCP_API_KEY=" .env 2>/dev/null | cut -d '=' -f2 || echo "")

BASE_URL="http://127.0.0.1:${PORT}"
AUTH_HEADER=()
if [[ -n "${API_KEY}" ]]; then
  AUTH_HEADER=(-H "Authorization: Bearer ${API_KEY}")
fi

echo "========================================================================"
echo "  TESTING MCP GATEWAY PROTOCOL & COMPATIBILITY (${BASE_URL})"
echo "========================================================================"

echo ""
echo "1. Testing Health Endpoint (/health)..."
curl -s -f "${BASE_URL}/health" | (command -v jq &>/dev/null && jq . || cat)
echo ""

echo "2. Testing JSON-RPC 'initialize' on /passbolt..."
INIT_RESP=$(curl -s -X POST "${BASE_URL}/passbolt" \
  -H "Content-Type: application/json" \
  "${AUTH_HEADER[@]}" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-init-1",
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "test-cli", "version": "1.0.0"}
    }
  }')
echo "${INIT_RESP}" | (command -v jq &>/dev/null && jq . || cat)

echo ""
echo "3. Testing JSON-RPC 'tools/list' on /passbolt..."
TOOLS_RESP=$(curl -s -X POST "${BASE_URL}/passbolt" \
  -H "Content-Type: application/json" \
  "${AUTH_HEADER[@]}" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-tools-1",
    "method": "tools/list",
    "params": {}
  }')
echo "${TOOLS_RESP}" | (command -v jq &>/dev/null && jq . || cat)

echo ""
echo "4. Checking Schema Sanitization (Gemini & Strict LLM compliance)..."
if echo "${TOOLS_RESP}" | grep -q '"\$schema"'; then
  echo "[-] WARNING: Found \$schema keyword in tools response!"
else
  echo "[+] OK: No \$schema keyword in output."
fi

if echo "${TOOLS_RESP}" | grep -q '"additionalProperties": false'; then
  echo "[-] WARNING: Found additionalProperties: false in tools response!"
else
  echo "[+] OK: No restrictive additionalProperties found."
fi

echo ""
echo "5. Testing JSON-RPC 'tools/list' on /unified..."
curl -s -X POST "${BASE_URL}/unified" \
  -H "Content-Type: application/json" \
  "${AUTH_HEADER[@]}" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-tools-unified",
    "method": "tools/list",
    "params": {}
  }' | (command -v jq &>/dev/null && jq . || cat)

echo ""
echo "========================================================================"
echo "  MCP GATEWAY TESTS COMPLETED"
echo "========================================================================"
