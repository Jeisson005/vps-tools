#!/usr/bin/env bash
# Verify the Gemini-compatibility proxy: handshake, Accept negotiation,
# and that tools/list is free of schema constructs Gemini rejects.
set -uo pipefail

ENDPOINT="${1:-http://127.0.0.1:8002/}"
SSE='Accept: application/json, text/event-stream'
JSONCT='Content-Type: application/json'
INIT='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}'
LIST='{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

echo "=== endpoint: $ENDPOINT ==="

echo "--- 1. initialize ---"
curl -sS -m 20 -X POST "$ENDPOINT" -H "$JSONCT" -H "$SSE" -d "$INIT" | head -c 220
echo; echo

echo "--- 2. Accept: application/json only (previously 406) ---"
curl -sS -o /dev/null -w 'status=%{http_code} ctype=%{content_type}\n' \
  -m 20 -X POST "$ENDPOINT" -H "$JSONCT" -H 'Accept: application/json' -d "$INIT"
echo

echo "--- 3. tools/list schema audit ---"
curl -sS -m 30 -X POST "$ENDPOINT" -H "$JSONCT" -H "$SSE" -d "$LIST" \
  | sed -n 's/^data: //p' > /tmp/gp_tools.json
python3 - <<'PY'
import json
raw = open('/tmp/gp_tools.json').read()
tools = json.loads(raw)['result']['tools']
bad = {"$schema","additionalProperties","anyOf","oneOf","allOf","$ref","const",
       "not","if","then","else","patternProperties","definitions","$defs"}
hits = {}
def walk(node, path, in_props=False):
    if isinstance(node, dict):
        for k, v in node.items():
            if not in_props and k in bad:
                hits.setdefault(k, []).append(path)
            walk(v, f"{path}/{k}", in_props=(k == "properties"))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, f"{path}/{i}")
for t in tools:
    walk(t.get('inputSchema', {}), t['name'])
print(f"tools: {len(tools)}   payload: {len(raw)} bytes")
print(f"unsupported keywords: {hits if hits else 'NONE (Gemini-safe)'}")
missing = [t['name'] for t in tools
           if t.get('inputSchema', {}).get('type') != 'object'
           or 'properties' not in t.get('inputSchema', {})]
print(f"tools missing type/properties: {missing or 'none'}")
PY
