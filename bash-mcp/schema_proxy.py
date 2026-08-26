#!/usr/bin/env python3
"""
Universal MCP Schema Sanitizing & Compatibility Proxy.

Sits between Nginx and the supergateway Streamable-HTTP endpoint and rewrites
`tools/list` responses into a clean, universal JSON Schema subset accepted by
all LLM providers (Google Gemini, OpenAI, Claude, Cursor, Ollama, etc.).

Why this exists
---------------
`@nickw8/bash-mcp` publishes draft-07 schemas containing constructs that
strict schema parsers (like Google Gemini) reject, which makes connectors fail
*after* a fully successful MCP handshake:

  * `"$schema": "http://json-schema.org/draft-07/schema#"`  (all 60 tools)
  * `"additionalProperties": false`                          (all 60 tools)
  * `anyOf: [string, array<string>]` mixed-type unions       (9 tools)

This proxy strips/collapses these keywords, ensures explicit types and properties,
drops redundant output schemas (reducing payload from 93 KB to 60 KB — 35% token savings),
and leaves every other MCP method (like tool calls) streaming through untouched.

Env:
  SCHEMA_PROXY_BIND          default 127.0.0.1
  SCHEMA_PROXY_PORT          default 8002
  SCHEMA_PROXY_UPSTREAM      default http://127.0.0.1:8001/mcp
  SCHEMA_PROXY_STRIP_OUTPUT  default 1  (drop outputSchema to save token context)
"""

import json
import os
import sys
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BIND = os.environ.get("SCHEMA_PROXY_BIND") or os.environ.get("GEMINI_PROXY_BIND", "127.0.0.1")
PORT = int(os.environ.get("SCHEMA_PROXY_PORT") or os.environ.get("GEMINI_PROXY_PORT", "8002"))
UPSTREAM = os.environ.get("SCHEMA_PROXY_UPSTREAM") or os.environ.get("GEMINI_PROXY_UPSTREAM", "http://127.0.0.1:8001/mcp")
STRIP_OUTPUT = (os.environ.get("SCHEMA_PROXY_STRIP_OUTPUT") or os.environ.get("GEMINI_PROXY_STRIP_OUTPUT", "1")) not in ("0", "false", "no")

_u = urlparse(UPSTREAM)
UP_HOST, UP_PORT, UP_PATH = _u.hostname, _u.port or 80, _u.path or "/mcp"

# Schema keywords strict Schema types have no field for. Dropped wherever they
# appear as *keywords* (never when they are property names).
DROP_KEYWORDS = {
    "$schema", "$id", "$ref", "$defs", "$comment", "definitions",
    "additionalProperties", "unevaluatedProperties", "unevaluatedItems",
    "patternProperties", "propertyNames", "dependentSchemas",
    "dependentRequired", "dependencies", "contains", "prefixItems",
    "additionalItems", "if", "then", "else", "not", "const", "examples",
}

SCHEMA_VALUE_KEYS = {"items", "contains", "not", "additionalItems"}


def _pick_branch(branches):
    """Collapse a union to its most expressive branch (arrays win over scalars)."""
    real = [b for b in branches if isinstance(b, dict) and b.get("type") != "null"]
    if not real:
        return {"type": "string"}
    for b in real:
        if b.get("type") == "array":
            return b
    return real[0]


def clean_schema(node):
    """Rewrite a JSON Schema node into universal supported subset."""
    if isinstance(node, list):
        return [clean_schema(n) for n in node]
    if not isinstance(node, dict):
        return node

    out = {}
    for key, val in node.items():
        if key in DROP_KEYWORDS:
            continue
        if key == "properties" and isinstance(val, dict):
            # keys here are user-defined property NAMES, not keywords
            out[key] = {pk: clean_schema(pv) for pk, pv in val.items()}
        elif key in SCHEMA_VALUE_KEYS:
            out[key] = clean_schema(val)
        elif key in ("anyOf", "oneOf", "allOf") and isinstance(val, list):
            out[key] = [clean_schema(v) for v in val]
        else:
            out[key] = val

    # Collapse anyOf/oneOf unions, preserving the sibling description.
    for union_key in ("anyOf", "oneOf"):
        if union_key in out:
            branches = out.pop(union_key)
            chosen = dict(_pick_branch(branches))
            for k, v in out.items():
                chosen.setdefault(k, v)
            out = chosen

    # Flatten allOf by shallow-merging its branches.
    if "allOf" in out:
        merged = {}
        for branch in out.pop("allOf"):
            if isinstance(branch, dict):
                merged.update(branch)
        merged.update(out)
        out = merged

    # Ensure explicit type; enums are always strings here.
    if "type" not in out:
        if "enum" in out:
            out["type"] = "string"
        elif "properties" in out:
            out["type"] = "object"
        elif "items" in out:
            out["type"] = "array"

    if out.get("type") == "object" and "properties" not in out:
        out["properties"] = {}

    return out


def clean_tool(tool):
    if not isinstance(tool, dict):
        return tool
    out = dict(tool)
    if isinstance(out.get("inputSchema"), dict):
        schema = clean_schema(out["inputSchema"])
        schema.setdefault("type", "object")
        schema.setdefault("properties", {})
        out["inputSchema"] = schema
    if STRIP_OUTPUT:
        out.pop("outputSchema", None)
    elif isinstance(out.get("outputSchema"), dict):
        out["outputSchema"] = clean_schema(out["outputSchema"])
    return out


def transform_message(raw):
    """Sanitize a single JSON-RPC message; return it unchanged if not tools/list."""
    try:
        msg = json.loads(raw)
    except (ValueError, TypeError):
        return raw
    result = msg.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("tools"), list):
        return raw
    result["tools"] = [clean_tool(t) for t in result["tools"]]
    return json.dumps(msg, ensure_ascii=False)


HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "content-length", "host",
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "mcp-schema-proxy"

    def log_message(self, fmt, *args):
        sys.stderr.write("[schema-proxy] %s - %s\n" % (self.address_string(), fmt % args))

    def _forward(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""

        # Clients that advertise only application/json get a 406 from the MCP
        # transport. Always ask upstream for both, then answer in the format the
        # caller actually accepts.
        client_accept = (self.headers.get("Accept") or "").lower()
        wants_sse = "text/event-stream" in client_accept

        headers = {
            k: v for k, v in self.headers.items()
            if k.lower() not in HOP_BY_HOP and k.lower() != "accept"
        }
        headers["Accept"] = "application/json, text/event-stream"
        headers["Host"] = f"{UP_HOST}:{UP_PORT}"
        if body:
            headers["Content-Length"] = str(len(body))

        conn = http.client.HTTPConnection(UP_HOST, UP_PORT, timeout=300)
        try:
            conn.request(method, UP_PATH, body=body, headers=headers)
            resp = conn.getresponse()
            ctype = (resp.getheader("Content-Type") or "").lower()

            passthrough = {
                k: v for k, v in resp.getheaders()
                if k.lower() not in HOP_BY_HOP and k.lower() != "content-type"
            }

            if "text/event-stream" in ctype:
                self._relay_sse(resp, passthrough, wants_sse)
            else:
                raw = resp.read()
                try:
                    out = transform_message(raw.decode("utf-8")).encode("utf-8")
                except UnicodeDecodeError:
                    out = raw
                self.send_response(resp.status)
                for k, v in passthrough.items():
                    self.send_header(k, v)
                self.send_header("Content-Type", ctype or "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                if method != "HEAD":
                    self.wfile.write(out)
        except Exception as exc:  # upstream unreachable / malformed
            self.log_message("upstream error: %s", exc)
            payload = json.dumps({
                "jsonrpc": "2.0", "id": None,
                "error": {"code": -32001, "message": f"Upstream MCP error: {exc}"},
            }).encode("utf-8")
            try:
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception:
                pass
        finally:
            conn.close()

    def _relay_sse(self, resp, passthrough, wants_sse):
        """Stream SSE events through the sanitizer, event by event."""
        if wants_sse:
            self.send_response(resp.status)
            for k, v in passthrough.items():
                self.send_header(k, v)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache, no-transform")
            self.send_header("Connection", "close")
            self.end_headers()

        first_payload = None
        event_name = None
        data_lines = []

        def flush_event():
            nonlocal first_payload, event_name, data_lines
            if not data_lines:
                event_name = None
                return
            payload = transform_message("\n".join(data_lines))
            if wants_sse:
                if event_name:
                    self.wfile.write(f"event: {event_name}\n".encode("utf-8"))
                for line in payload.split("\n"):
                    self.wfile.write(f"data: {line}\n".encode("utf-8"))
                self.wfile.write(b"\n")
                self.wfile.flush()
            elif first_payload is None:
                first_payload = payload
            event_name = None
            data_lines = []

        for raw_line in resp:
            line = raw_line.decode("utf-8", "replace").rstrip("\r\n")
            if line == "":
                flush_event()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
            elif line.startswith("event:"):
                event_name = line[6:].strip()
            # ":" comments and other fields are ignored
        flush_event()

        if not wants_sse:
            out = (first_payload or "").encode("utf-8")
            self.send_response(resp.status)
            for k, v in passthrough.items():
                self.send_header(k, v)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

    def do_POST(self):
        self._forward("POST")

    def do_GET(self):
        self._forward("GET")

    def do_HEAD(self):
        self._forward("HEAD")

    def do_DELETE(self):
        self._forward("DELETE")


class ProxyServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    # Burst support for multiple simultaneous AI client connections
    request_queue_size = 128


def main():
    srv = ProxyServer((BIND, PORT), Handler)
    sys.stderr.write(
        f"[schema-proxy] listening on {BIND}:{PORT} -> {UPSTREAM} "
        f"(strip_output_schema={STRIP_OUTPUT})\n"
    )
    srv.serve_forever()


if __name__ == "__main__":
    main()
