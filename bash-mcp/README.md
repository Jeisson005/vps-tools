# Bash-MCP (Host-Native Model Context Protocol Server)

Host-native **Model Context Protocol (MCP)** server for Linux VPS, enabling AI assistants (Cursor, OpenCode, Claude Desktop, Antigravity, etc.) to execute tools and inspect the host server.

---

## 1. Overview & Architecture

Unlike containerized tools, `bash-mcp` runs **directly on the VPS host system** as a managed `systemd` service. This gives the AI assistant the capability to:
- Inspect host hardware, system load, processes, memory, and disk.
- Manage system services (`systemctl`, `journalctl`).
- Manage Docker containers across the entire `vps-tools` stack.
- Inspect and edit server configuration files.

### Available Execution Modes
| Binary / Mode | Setting | Description |
| :--- | :--- | :--- |
| `/usr/local/bin/bash-mcp` | `BASH_MCP_MODE=readOnly` | Safe mode. Blocks write commands and destructive filesystem operations. |
| `/usr/local/bin/bash-server` | `BASH_MCP_MODE=off` | Full root/admin mode. Unrestricted bash execution on the server. |

---

## 2. Getting Started

### 1. Installation on the VPS
```bash
cd vps-tools/bash-mcp
sudo bash scripts/install.sh
```
This will:
1. Verify / install Node.js and npm.
2. Install `@nickw8/bash-mcp` and `supergateway`.
3. Create `/usr/local/bin/bash-mcp` and `/usr/local/bin/bash-server`.
4. Register and activate the `bash-mcp-http.service` systemd service bound to `127.0.0.1:8001`.

### 2. Service Management
```bash
# Check service status and recent journal logs
sudo bash scripts/status.sh

# Run local JSON-RPC handshake test
bash scripts/test_mcp.sh

# Stop and uninstall the service
sudo bash scripts/uninstall.sh
```

---

## 3. How to Connect from AI Clients

### Method 1: stdio over SSH (Recommended — Zero Open Ports)
The most secure transport. No HTTP server, no port forwarding, and fully encrypted via your SSH key.

#### Claude Desktop / Cursor / OpenCode Config (`mcpServers`):
```json
{
  "mcpServers": {
    "vps-bash": {
      "command": "ssh",
      "args": [
        "deploy@YOUR_SERVER_IP",
        "-p", "22",
        "/usr/local/bin/bash-server"
      ]
    }
  }
}
```

---

### Method 2: HTTP via SSH Tunnel
Keep the service listening on `127.0.0.1:8001` (loopback only) on the server, and forward it locally:

```bash
# In your local terminal:
ssh -L 8001:127.0.0.1:8001 deploy@YOUR_SERVER_IP
```

Point your AI tool to:
`http://127.0.0.1:8001/mcp`

---

### Method 3: Public HTTPS via Nginx with API Key or Basic Auth
To expose the MCP endpoint securely over the internet:

1. Use the `nginx` tool in this repository to configure a domain and proxy to `host.docker.internal:8001/mcp`.
2. Protect it with an **API Key** or **HTTP Basic Auth**:
   ```bash
   cd ../nginx
   # Add domain / sub-route for MCP proxy
   bash scripts/site_add.sh --domain mcp.yourdomain.com --upstream host.docker.internal:8001 --api-key "your_secret_api_token_here"
   ```
3. Your client connects with HTTPS and includes the header:
   `X-API-Key: your_secret_api_token_here` or `Authorization: Bearer your_secret_api_token_here`.

---

### Method 4: Universal AI Web Clients & Google Gemini
For web AI clients (Google Gemini, web agents, etc.) that accept the key in the URL and require sanitized, high-efficiency schemas:

`https://mcp.yourdomain.com/bash?key=your_secret_api_token_here`

---

## 4. Universal Schema Sanitizing Proxy (`schema_proxy.py`)

Some AI clients (including Google Gemini Function Calling and strict protobuf parsers)
complete the MCP handshake successfully but **discard tool lists** if tool schemas contain
draft-07 JSON Schema keywords that their schema deserializers do not support. `@nickw8/bash-mcp`
publishes draft-07 schemas that contain:

| Construct | Where | Reason |
| :--- | :--- | :--- |
| `"$schema": "…draft-07/schema#"` | all 60 tools | Unknown field in strict protobuf schema definitions |
| `"additionalProperties": false` | all 60 tools | Unsupported constraint |
| `anyOf: [string, array<string>]` | 9 tools | Heterogeneous unions are rejected |

### The Sanitizing Proxy Architecture

`schema_proxy.py` sits between Nginx and supergateway, rewriting `tools/list`
responses into a clean, universally compatible JSON Schema subset. Every other MCP method (like tool calls)
streams through untouched.

```bash
cd vps-tools/bash-mcp
sudo bash scripts/install_schema_proxy.sh   # systemd: bash-mcp-schema-proxy
bash scripts/test_schema_proxy.sh           # audits schema compatibility
```

Key features:
- Strips `$schema`, `additionalProperties` and unsupported keywords.
- Collapses `anyOf` / `oneOf` unions to their most expressive branch.
- Guarantees every schema has explicit `type` and `properties`.
- Drops `outputSchema` (reduces payload from 93 KB to 60 KB — **35% context token savings**).
- Transparently handles clients sending `Accept: application/json` or `text/event-stream`.
- Preserves literal user-defined property names (`format`, `pattern`, etc.).

### Endpoint Layout in Nginx

| Route | Upstream | Ideal for |
| :--- | :--- | :--- |
| `/bash` | `schema_proxy` (`:8002`) | Universal compatibility (Gemini, Web agents, OpenAI, Claude, Cursor) |
| `/bash/` | `supergateway` (`:8001`) | Full-fidelity draft-07 raw schemas |

> [!IMPORTANT]
> Do **not** serve `/.well-known/oauth-protected-resource` unless real OAuth is in
> use. Returning `200` with an empty `authorization_servers` array tells clients the
> resource is OAuth-protected while offering no way to authorize it. It must `404`
> so clients fall back to the API-key transport.

---

### Process leak: why memory grew to 6 GB

`supergateway` in its default **stateless** mode forks a brand-new MCP server
child (`sh` -> `node`, ~85 MB RSS) for **every HTTP request** and never reaps it.
Measured on a live server: 190 orphaned children, 1519 tasks, **5.9 GB** resident.

```
antes: 7 requests -> 7 procesos (permanentes)
```

The fix is `--stateful --sessionTimeout <ms>`, which reuses one child per
session. The catch: stateful mode then rejects any request without an
`Mcp-Session-Id` header with `400`, and clients like Gemini never send one.

So the proxy owns the session. It performs the upstream handshake, caches the
session id, injects it into every forwarded request, and strips it from
responses — callers still see a plain stateless endpoint. A stale session
(idle timeout, upstream restart) returns `400`, which the proxy detects and
retries once against a freshly opened session, transparently.

```
despues: 33 requests -> 1 proceso, 94 MB
```

`install.sh` also sets `TasksMax=512`, `MemoryHigh=768M` and `MemoryMax=1G` on
the unit, so any future transport regression is capped instead of consuming the
whole box.

> [!NOTE]
> With stateful mode on, the raw `/bash/` route requires clients to track
> `Mcp-Session-Id` — correct MCP behaviour, which Claude and Cursor implement.
> Only the sanitized `/bash` route is session-free.

---

## 5. Security Recommendations

> [!WARNING]
> Running `bash-mcp` with `BASH_MCP_MODE=off` allows arbitrary command execution as root.
> - **Never** expose port `8001` without authentication or firewall restrictions.
> - Keep `MCP_BIND=127.0.0.1` (loopback).
> - Always protect public routes using Nginx HTTPS + API Key / Basic Auth.
