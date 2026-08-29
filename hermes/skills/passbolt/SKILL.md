---
name: passbolt-credentials
description: "Secure password and credential management via Passbolt MCP Gateway. Query and retrieve secrets autonomously, with mandatory human confirmation for creating or modifying credentials."
version: 1.0.0
author: VPS Tools
license: MIT
metadata:
  hermes:
    tags: [passbolt, passwords, credentials, secrets, mcp, security, authentication, logins, vault]
    category: security
    related_skills: [browser-automation]
---

# Passbolt Credential Management Skill

Empowers autonomous agents to safely search, retrieve, and utilize stored credentials from the self-hosted **Passbolt Password Manager** vault via the modular **MCP Gateway** (`https://mcp.jeisson.top/passbolt` or local `http://127.0.0.1:8005/passbolt`).

---

## 🔑 Available MCP Tools

* **`passbolt_search_resources(query, folder_id, limit)`**:
  Search for credentials by service name, URL domain, username, or keyword (e.g. `"postgres"`, `"aws"`, `"github.com"`). Returns matching resource IDs, usernames, and URIs **without** exposing plaintext secrets in the list.
* **`passbolt_get_secret(resource_id)`**:
  Decrypted retrieval of the password, username, description, and custom fields for a specific resource UUID.
* **`passbolt_list_folders(parent_id)`**:
  Inspect vault organizational hierarchy and folders.

---

## 🛡️ Operational Guidelines & Safety Rules

### 1. Autonomous Reading & Usage (Read-Allowed)
* You are authorized to search and decrypt credentials autonomously when required to fulfill a user task (e.g. database credentials for backups, API keys for integrations, credentials for browser automation).
* **Search First:** Always call `passbolt_search_resources` with a relevant domain/name to obtain the precise `resource_id` before calling `passbolt_get_secret`.
* **Never Expose Plaintext in Logs:** Do not unnecessarily print plaintext passwords in general conversational output unless explicitly requested by the user.

### 2. Mandatory Human Confirmation for Writes (Write-Guarded)
> [!CRITICAL]
> **ZERO UNCONFIRMED WRITES:**
> You must **ALWAYS** ask the user for explicit confirmation before creating, updating, deleting, or saving any new or modified password/credential in Passbolt or local files.

Before executing any credential creation or modification:
1. Explain clearly to the user:
   - **Target Service / Resource Name**
   - **URL / Domain**
   - **Username / Identifier**
   - **Action Intent** (e.g., "Create new database password", "Update expired API token")
2. **Wait for the user's explicit approval** before applying changes.

---

## ⚙️ Configuration & Connection Reference

* **Endpoint**: `https://mcp.jeisson.top/passbolt` (or internal `http://127.0.0.1:8005/passbolt`)
* **Transport**: Streamable HTTP / SSE JSON-RPC 2.0
* **Authentication**: `Authorization: Bearer <MCP_API_KEY>` or header `X-API-Key: <MCP_API_KEY>`
