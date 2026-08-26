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

### Method 4: Google Gemini / Connected Apps
Gemini needs schema-sanitized tools and accepts the key in the URL. Install the
proxy (see section 4) and use:

`https://mcp.yourdomain.com/bash?key=your_secret_api_token_here`

---

## 4. Google Gemini / Connected Apps Compatibility

Google's Gemini connector ("Configura una app conectada personalizada") completes the
MCP handshake successfully but then **discards the whole tool list** if any tool schema
contains JSON Schema constructs its strict parser does not model. `@nickw8/bash-mcp`
publishes draft-07 schemas that trip this on every tool:

| Construct | Where | Why it fails |
| :--- | :--- | :--- |
| `"$schema": "…draft-07/schema#"` | all 60 tools | Not a field of Gemini's `Schema` type |
| `"additionalProperties": false` | all 60 tools | Not a field of Gemini's `Schema` type |
| `anyOf: [string, array<string>]` | 9 tools | Mixed-type unions are unsupported |

The symptom is misleading: TLS, auth and the handshake all work, the server returns a
valid 93 KB `tools/list`, and the UI still reports *"Tuvimos problemas para conectarnos
a este servidor."*

### The sanitizing proxy

`gemini_proxy.py` sits between Nginx and supergateway and rewrites `tools/list`
responses into the subset Gemini accepts. Every other MCP method streams through
untouched.

```bash
cd vps-tools/bash-mcp
sudo bash scripts/install_gemini_proxy.sh   # systemd: bash-mcp-gemini-proxy
bash scripts/test_gemini_proxy.sh           # audits the live schema output
```

What it does:
- strips `$schema`, `additionalProperties` and other unsupported keywords
- collapses `anyOf` / `oneOf` unions to their most expressive branch (arrays win)
- guarantees every schema has an explicit `type` and `properties`
- drops `outputSchema` (Gemini ignores it) — payload drops from 93 KB to 60 KB
- answers clients that send `Accept: application/json` alone, which the raw MCP
  transport rejects with `406 Not Acceptable`

Property names are never mistaken for keywords — a tool with a property literally
named `format` or `pattern` is preserved intact.

### Endpoint layout

| Route | Upstream | Use for |
| :--- | :--- | :--- |
| `/bash` | proxy `:8002` | Gemini, connected apps, strict clients |
| `/bash/` | supergateway `:8001` | Claude, Cursor — full-fidelity schemas |

> [!IMPORTANT]
> Do **not** serve `/.well-known/oauth-protected-resource` unless real OAuth is in
> use. Returning `200` with an empty `authorization_servers` array tells clients the
> resource is OAuth-protected while offering no way to authorize it. It must `404`
> so clients fall back to the API-key transport.

---

## 5. Security Recommendations

> [!WARNING]
> Running `bash-mcp` with `BASH_MCP_MODE=off` allows arbitrary command execution as root.
> - **Never** expose port `8001` without authentication or firewall restrictions.
> - Keep `MCP_BIND=127.0.0.1` (loopback).
> - Always protect public routes using Nginx HTTPS + API Key / Basic Auth.
