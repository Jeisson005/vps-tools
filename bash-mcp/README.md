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

## 4. Security Recommendations

> [!WARNING]
> Running `bash-mcp` with `BASH_MCP_MODE=off` allows arbitrary command execution as root.
> - **Never** expose port `8001` without authentication or firewall restrictions.
> - Keep `MCP_BIND=127.0.0.1` (loopback).
> - Always protect public routes using Nginx HTTPS + API Key / Basic Auth.
