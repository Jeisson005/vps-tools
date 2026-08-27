#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

if [[ -f .env ]]; then
  # Extract STEEL_API_KEY
  STEEL_API_KEY=$(grep "^STEEL_API_KEY=" .env | cut -d '=' -f2- | tr -d '"' | tr -d "'")
else
  STEEL_API_KEY=""
fi

PORT=$(grep "^STEEL_PORT=" .env 2>/dev/null | cut -d '=' -f2- || echo "3000")
BASE_URL="http://127.0.0.1:${PORT:-3000}"

echo "========================================================================"
echo "  TESTING STEEL BROWSER API & SESSION LIFECYCLE"
echo "  Target: ${BASE_URL}"
echo "========================================================================"

AUTH_HEADER=()
if [[ -n "$STEEL_API_KEY" ]]; then
  AUTH_HEADER=(-H "x-steel-api-key: ${STEEL_API_KEY}" -H "Authorization: Bearer ${STEEL_API_KEY}")
fi

echo "--> 1. Checking Active Sessions..."
curl -s "${AUTH_HEADER[@]}" "${BASE_URL}/v1/sessions" | head -n 10
echo ""

echo "--> 2. Launching a Test Browser Session..."
CREATE_RESP=$(curl -s -X POST "${AUTH_HEADER[@]}" \
  -H "Content-Type: application/json" \
  -d '{"useProxy": false}' \
  "${BASE_URL}/v1/sessions" || true)

echo "Response: ${CREATE_RESP}"
echo ""

SESSION_ID=$(echo "${CREATE_RESP}" | grep -o '"id":"[^"]*' | cut -d '"' -f4 || true)

if [[ -n "${SESSION_ID}" ]]; then
  echo "[+] SUCCESS: Session created with ID: ${SESSION_ID}"
  
  echo "--> 3. Fetching Session Details & Live URLs..."
  SESSION_DATA=$(curl -s "${AUTH_HEADER[@]}" "${BASE_URL}/v1/sessions/${SESSION_ID}" || true)
  echo "Session Details: ${SESSION_DATA}"
  echo ""
  
  echo "--> 4. Releasing / Stopping Test Session..."
  RELEASE_RESP=$(curl -s -X POST "${AUTH_HEADER[@]}" "${BASE_URL}/v1/sessions/${SESSION_ID}/release" || true)
  echo "Release result: ${RELEASE_RESP}"
  echo "[+] Test completed successfully."
else
  echo "[!] Notice: Session creation returned unexpected format or is starting up."
fi

echo "========================================================================"
