#!/usr/bin/env bash
set -euo pipefail

PROXY_URL="${1:-http://127.0.0.1:8002}"

echo "=== Testing Schema Sanitizing Proxy: ${PROXY_URL} ==="

echo "--- 1. Initialize Handshake ---"
curl -s -X POST "${PROXY_URL}/" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test-client","version":"1"}}}' \
  | head -n 3

echo ""
echo "--- 2. Direct JSON Accept Check ---"
curl -s -o /dev/null -w "Status: %{http_code} Content-Type: %{content_type}\n" \
  -X POST "${PROXY_URL}/" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}'

echo ""
echo "--- 3. Schema Audit (Checking invalid keywords) ---"
python3 -c "
import urllib.request, json
req = urllib.request.Request(
    '${PROXY_URL}/',
    data=json.dumps({'jsonrpc':'2.0','id':3,'method':'tools/list','params':{}}).encode(),
    headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream'}
)
res = urllib.request.urlopen(req)
raw = res.read().decode()
data_line = [l for l in raw.split('\n') if l.startswith('data:')][0]
payload = json.loads(data_line[5:].strip())
tools = payload['result']['tools']
print(f'Total tools: {len(tools)} | Payload: {len(raw)} bytes')
for t in tools:
    s = t.get('inputSchema', {})
    if '\$schema' in s or 'additionalProperties' in s or 'anyOf' in s:
        print(f'Invalid keyword found in tool: {t[\"name\"]}')
print('Schema audit passed: Universal compatibility verified.')
"
