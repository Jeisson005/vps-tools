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
1. **Accounts Manager multi-cuenta (para cualquier servicio):**
   - Gestiona **una o varias cuentas** por servicio (Passbolt, Google, Microsoft 365) desde el panel, con campos dinámicos según el servicio y un **nombre/etiqueta** opcional por cuenta.
   - Añadir / editar / eliminar cuentas; cada cuenta guarda sus credenciales cifradas (clave GPG, OAuth tokens, etc.).
   - Marcar una cuenta como **principal** (se usa cuando los agentes no especifican `account`).
   - **"Probar Conexión Live"** por cuenta sin reiniciar.
2. **Interactive Tool Tester & Inspector:**
   - Execute tool calls directly from your browser (`passbolt_search_resources`, `passbolt_get_secret`, etc.) and view raw JSON-RPC 2.0 responses.
3. **Client Configuration Snippets:**
   - Real-time generated JSON configurations ready to copy into Cursor, Claude Desktop, and Open WebUI.
4. **Audit Logs:**
   - Visual inspection of tool executions, configuration updates, and error traces.
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
| `passbolt_search_resources` | Search credentials by name, URI, username, or keyword. Returns metadata and UUIDs **without** exposing plaintext passwords in search results. | `query` (str), `folder_id` (optional str), `limit` (int, default 20), `account` (optional str) |
| `passbolt_get_secret` | Retrieves and decrypts the password/credential for a specific resource UUID using the configured GPG private key. | `resource_id` (str, required), `account` (optional str) |
| `passbolt_list_folders` | Inspects folder hierarchy to find categorized secrets. | `parent_id` (optional str), `account` (optional str) |
| `passbolt_list_accounts` | Lists the configured Passbolt accounts (id, default flag, email, server) so agents can discover valid `account` values. | none |

> **Multi-cuenta:** todas las herramientas aceptan un parámetro opcional `account` (nombre/alias de la
> cuenta). Si se omite se usa la **cuenta principal**; si solo hay una cuenta, esa se usa automáticamente.
> Las cuentas se gestionan en el panel (Servicio → Cuentas). Cada servicio expone además una tool
> `*_list_accounts()` para descubrir las cuentas disponibles.

## 4b. Servicios incluidos (multi-instancia)

| Service | Subroute | Tools | Credenciales por cuenta |
| :--- | :--- | :--- | :--- |
| `passbolt` | `/passbolt` | `passbolt_*` | clave GPG + passphrase |
| `google` | `/google` | `google_gmail_*`, `google_calendar_*` | OAuth2 (client id/secret + refresh_token) |
| `microsoft` | `/microsoft` | `outlook_mail_*`, `outlook_calendar_*` | OAuth2 (tenant/client id/secret + refresh_token) |

> Los agentes los consumen todos desde el endpoint **unificado** `/unified` (o `/mcp`).

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
