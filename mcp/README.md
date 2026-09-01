# MCP Gateway (Modular Model Context Protocol Server & Admin Panel)

Lightweight, modular **Model Context Protocol (MCP)** Gateway and Admin Dashboard for Linux VPS. Encapsulates multiple APIs and services into isolated subroutes (e.g. `/passbolt`) and a unified catalog (`/unified`), starting with **Passbolt Password Manager**.

---

## 1. Overview & Architecture

```
                  ┌────────────────────────────────────────────────────────┐
                  │                   AI Clients / LLMs                    │
                  │   (Cursor, Claude Desktop, Open WebUI, OpenCode, etc.) │
                  └───────────────────────────┬────────────────────────────┘
                                              │  Streamable HTTP / SSE
                                              ▼
                                ┌───────────────────────────┐
                                │      Nginx (TLS + Auth)   │
                                │   https://mcp.jeisson.top │
                                └─────────────┬─────────────┘
                                              │
                                              ▼
                  ┌────────────────────────────────────────────────────────┐
                  │                 MCP GATEWAY (FastAPI)                  │
                  │  - Admin Web UI (Vanilla JS, 0 MB SSR, <50KB bundle)   │
                  │  - Subroute Routing (/passbolt, /unified, /sse)        │
                  │  - Universal Schema Sanitizer (Gemini / Claude / GPT)  │
                  │  - SQLite Database (<100KB, WAL mode, AES encrypted)   │
                  └───────────────┬────────────────────────┬───────────────┘
                                  │                        │
                     ┌────────────▼─────────┐    ┌─────────▼────────────┐
                     │   Service: Passbolt  │    │   Future Services    │
                     │ - GPG Auth & Decrypt │    │ - Docker / System    │
                     │ - Secret Search & Read│   │ - WireGuard / Headscale│
                     └──────────────────────┘    └──────────────────────┘
```

### Key Architectural Highlights
- **Ultra-Low Memory Footprint:** Built with Python 3.11 + FastAPI and Vanilla JS. Requires **no** heavy Node/React SSR runtime and **no** external database service. The entire container consumes only **~40–50 MB of RAM**.
- **Isolated Subroutes:**
  - `https://mcp.jeisson.top/passbolt` (Streamable-HTTP & SSE): Exposes *only* Passbolt tools.
  - `https://mcp.jeisson.top/unified` (or `/mcp`, `/sse`): Aggregated endpoint with all active tools.
  - `https://mcp.jeisson.top/admin`: Modern, responsive Admin Web Panel.
- **Learnings from `bash-mcp` (Strict Schema Sanitization):**
  - Completely strips `$schema: "http://json-schema.org/draft-07/schema#"`.
  - Removes restrictive `additionalProperties: false` that cause strict LLM parsers (like Google Gemini) to fail.
  - Unwraps `anyOf` / `oneOf` unions into clean, explicit types.
  - Drops redundant output schemas to prevent context-window bloat.
  - Transparent `Mcp-Session-Id` management for both stateless and stateful clients.
- **SQLite Persistence & Encrypted Secrets:**
  - Stored in `./data/mcp.db`.
  - GPG private keys and passphrases are encrypted at rest using AES-GCM / Fernet derived from `MCP_MASTER_KEY`.

---

## 2. Quick Start & Deployment

### 1. Installation
```bash
cd vps-tools/mcp
sudo bash scripts/install.sh
```
This will:
1. Generate `.env` with cryptographically secure random values for `MCP_ADMIN_PASSWORD`, `MCP_API_KEY`, and `MCP_MASTER_KEY`.
2. Ensure the `nginx_default` Docker network exists.
3. Build and launch the `mcp-gateway` container on `127.0.0.1:8005`.

### 2. Service Management
```bash
# Check service status and healthcheck
bash scripts/status.sh

# Run JSON-RPC protocol compliance test
bash scripts/test_mcp.sh

# Stop the service
bash scripts/stop.sh

# Rebuild and update
bash scripts/update.sh
```

---

## 3. Web Admin Dashboard

Open `http://127.0.0.1:8005/admin` (or `https://mcp.jeisson.top/admin` once configured behind Nginx).

### Features:
1. **Passbolt Configuration:**
   - Server URL input (e.g. `https://passbolt.yourdomain.com`).
   - Drag-and-drop GPG Private Key upload (`.asc`, `.key`, `.gpg`) or paste ASCII armored text.
   - GPG Passphrase with show/hide toggle.
   - **"Probar Conexión Live"** button: Performs an instant GPG challenge-response test against your Passbolt server and displays the result without needing to restart.
2. **Interactive Tool Tester & Inspector:**
   - Execute tool calls directly from your browser (`passbolt_search_resources`, `passbolt_get_secret`, etc.) and view raw JSON-RPC 2.0 responses.
3. **Client Configuration Snippets:**
   - Real-time generated JSON configurations ready to copy into Cursor, Claude Desktop, and Open WebUI.
4. **Audit Logs:**
   - Visual inspection of tool executions, configuration updates, and error traces.

---

## 4. Passbolt MCP Tools Catalog

| Tool Name | Description | Arguments |
| :--- | :--- | :--- |
| `passbolt_search_resources` | Search credentials by name, URI, username, or keyword. Returns metadata and UUIDs **without** exposing plaintext passwords in search results. | `query` (str), `folder_id` (optional str), `limit` (int, default 20) |
| `passbolt_get_secret` | Retrieves and decrypts the password/credential for a specific resource UUID using the configured GPG private key. | `resource_id` (str, required) |
| `passbolt_list_folders` | Inspects folder hierarchy to find categorized secrets. | `parent_id` (optional str) |

---

## 5. Connecting AI Clients

### Method 1: Cursor & Claude Desktop (`mcpServers`)

Add the following to your `~/.cursor/mcp.json` or `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "vps-passbolt": {
      "url": "https://mcp.jeisson.top/passbolt/sse",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_API_KEY"
      }
    },
    "vps-unified": {
      "url": "https://mcp.jeisson.top/unified/sse",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_API_KEY"
      }
    }
  }
}
```

### Method 2: Open WebUI (Internal Docker Network)

In **Open WebUI > Settings > Tools / Function Calling > Add MCP Server**:
* **Name:** `VPS MCP Gateway`
* **URL:** `http://mcp-gateway:8000/unified/sse`
* **Type:** `sse`
* **Headers:** `Authorization: Bearer YOUR_MCP_API_KEY`

---

## 6. Security Best Practices

1. **Dedicated Service Account in Passbolt:**
   - Do **not** use your personal administrator account. Create a dedicated bot user (e.g. `ai-agent@yourdomain.com`) in Passbolt and only grant it read/share permissions to the specific folders the agent needs.
2. **Encryption at Rest:**
   - All passphrases and private keys are saved encrypted in SQLite using AES-GCM / Fernet.
3. **Password Protection:**
   - Change `MCP_ADMIN_PASSWORD` in `.env` immediately if not using the automatically generated password.
4. **Token Leakage Prevention:**
   - `passbolt_search_resources` strictly omits secret payloads to prevent filling LLM context windows or leaking passwords during exploratory searches. Plaintext secrets are only decrypted when `passbolt_get_secret` is explicitly called for a given resource ID.
