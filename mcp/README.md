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
| `clickup` | `/clickup` | `clickup_*` | Personal API Token (`pk_...`) |
| `notebooklm` | `/notebooklm` | `notebooklm_*` | Auth JSON (`storage_state.json` de notebooklm-py) |
| `google` | `/google` | `google_gmail_*`, `google_calendar_*` | OAuth2 (client id/secret + refresh_token) |
| `microsoft` | `/microsoft` | `outlook_mail_*`, `outlook_calendar_*` | OAuth2 (tenant/client id/secret + refresh_token) |
| `telegram` | `/telegram` | `telegram_send_message`, `telegram_list_chats`, ... | MTProto (api_id/api_hash) + login por código |
| `whatsapp` | `/whatsapp` | `whatsapp_send_message`, `whatsapp_list_chats`, ... | bridge Baileys (por teléfono, link por QR) |

> **WhatsApp:** la cuenta **solo pide el número de teléfono**. El bridge Baileys se provee **un contenedor por
> cuenta** en el host (el contenedor MCP no tiene Node). La dirección se deriva automáticamente
> (`http://127.0.0.1:<puerto>` con puerto estable por cuenta). Automatizado:
> ```
> # 1) una vez: construir la imagen y, en el host, instalar el timer systemd
> bash mcp/scripts/whatsapp_bridge_provision.sh build
> sudo cp mcp/templates/whatsapp-bridges.{service,timer} /etc/systemd/system/
>   # ajusta {{VPS_TOOLS_DIR}} y {{WHATSAPP_USER}}
> sudo systemctl daemon-reload && sudo systemctl enable --now whatsapp-bridges.timer
> ```
> El timer ejecuta el `provision.sh reconcile` cada 60s: al añadir una cuenta levanta su contenedor
> `wa-<cuenta>`, al quitarla lo elimina, y autorrepara si alguno se cae. Manual: `... provision.sh {build|list|stop-all}`.
> El puerto del bridge se publica **solo en `127.0.0.1`** (variable `WHATSAPP_BRIDGE_HOST`,
> por defecto `127.0.0.1`): el gateway lo consume por la red Docker (nombre `wa-<slug>`), los
> agentes del host por `http://127.0.0.1:<puerto>`, y **nunca** queda accesible desde Internet.
> Para otro host, setea `WHATSAPP_BRIDGE_HOST`.
> **Telegram:** en el panel pon `api_id`/`api_hash` (de my.telegram.org) y el teléfono; luego llama
> `telegram_request_code` → `telegram_sign_in(code)` para guardar la sesión.

> Los agentes los consumen todos desde el endpoint **unificado** `/unified` (o `/mcp`).

## 4b-bis. ClickUp MCP Tools Catalog

| Tool Name | Description | Arguments |
| :--- | :--- | :--- |
| `clickup_list_accounts` | Lists configured ClickUp accounts (id, default flag) WITHOUT exposing tokens. | none |
| `clickup_list_workspaces` | Lists accessible Workspaces (teams): id, name, members. Start here to get `team_id`. | `account` (optional) |
| `clickup_list_spaces` | Lists Spaces in a Workspace. | `team_id`, `archived` (opt), `account` (opt) |
| `clickup_get_space` / `clickup_create_space` / `clickup_update_space` / `clickup_delete_space` | Full Space CRUD. | ids + `name`, `color`, `private`, `archived` |
| `clickup_list_folders` / `clickup_create_folder` | Folders in a Space (each with its lists). | `space_id`, `name` |
| `clickup_list_lists` | Lists in a Folder (`folder_id`) or folderless Lists in a Space (`space_id`). | `folder_id` or `space_id` |
| `clickup_get_list` / `clickup_create_list` / `clickup_update_list` / `clickup_delete_list` | Full List CRUD. | ids + `name`, `content`, `status` |
| `clickup_list_tasks` | Tasks in a List (id, name, status, assignees, due, url; 100/page). | `list_id`, `page`, `include_closed`, `subtasks` |
| `clickup_get_task` | Full task detail (description, custom fields, subtasks, url). | `task_id` |
| `clickup_create_task` | Create a task (`name` required; `status`, `priority` 1-4, `assignees`, `tags`, `due_date` ms, `parent` for subtasks). | `list_id`, `name`, ... |
| `clickup_update_task` | Update a task (`name`, `description`, `status`, `priority`, `due_date`, `assignees: {add, rem}`, `archived`). | `task_id`, ... |
| `clickup_delete_task` | Delete a task. | `task_id` |
| `clickup_list_task_comments` / `clickup_create_task_comment` | Task comments. | `task_id`, `comment_text` |

> **Multi-cuenta:** igual que los demás servicios, todas aceptan `account` opcional (alias de la cuenta;
> `clickup_list_accounts` para descubrirlas). Cada cuenta guarda su Personal API Token (`pk_...`,
> ClickUp → Settings → Apps → API Token) cifrado en SQLite. Aislamiento por subruta: `/clickup`.

### 4b-ter. NotebookLM (Gemini Notebook) MCP Tools Catalog

Basado en el proyecto recomendado **`teng-lin/notebooklm-py`** (API no oficial, la única
opción con MCP real para NotebookLM de consumidor; Google solo ofrece API oficial para
NotebookLM Enterprise en GCP). El gateway lo envuelve vía CLI (`notebooklm --json`) con un
perfil aislado por cuenta (`<data>/notebooklm/profiles/<cuenta>/`), **sin navegador en el
contenedor**: la autenticación se pega una vez en el panel.

| Tool Name | Description | Arguments |
| :--- | :--- | :--- |
| `notebooklm_list_accounts` | Cuentas configuradas (sin exponer cookies). | none |
| `notebooklm_auth_check` | Valida la sesión Google con test live. | `account` (opt) |
| `notebooklm_list_notebooks` | Lista notebooks (id, título). | `limit`, `account` |
| `notebooklm_create_notebook` / `notebooklm_rename_notebook` / `notebooklm_delete_notebook` | CRUD de notebooks. | `title` / `notebook_id`+`new_title` / `notebook_id` |
| `notebooklm_describe_notebook` | Metadata + lista de fuentes. | `notebook_id` |
| `notebooklm_list_sources` / `notebooklm_get_source` | Fuentes (id, título, tipo, estado). | `notebook_id`, `limit`/`status`, `source_id` |
| `notebooklm_fulltext_source` | Texto indexado (truncado con `truncated`+`char_count`). | `notebook_id`, `source_id`, `max_chars` |
| `notebooklm_search_sources` | Búsqueda por pasajes con ranking. | `notebook_id`, `query`, `limit` |
| `notebooklm_add_source_url` / `notebooklm_add_source_text` | Añadir URL/YouTube o texto pegado. | `notebook_id`, `url`/`text`+`title` |
| `notebooklm_ask` | Pregunta grounded con citas (RAG sin gastar tokens del agente). Soporta `source_ids` y `conversation_id`. | `notebook_id`, `question`, ... |
| `notebooklm_history` / `notebooklm_suggest_prompts` | Historial Q&A y prompts sugeridos. | `notebook_id`, `limit` |

> **Configuración 100% desde el panel** (Servicio → NotebookLM → Añadir cuenta):
> `email` + `auth_json` (contenido de `storage_state.json`).
> Cómo obtenerlo **una vez en tu PC** (no en el VPS):
> ```
> uv tool install "notebooklm-py[browser]"
> notebooklm login   # o: notebooklm login --browser-cookies chrome
> cat ~/.notebooklm/profiles/default/storage_state.json   # ← pega esto en auth_json
> ```
> Luego en el panel pulsa **Probar Conexión Live** (`notebooklm_auth_check`).
> Aislamiento por subruta: `/notebooklm`. Agregado al endpoint **unificado** `/unified`.
>
> **Límites honestos v1:** solo lectura + Q&A + añadir URL/texto. Sin generación Studio
> (audio/video/slides/quiz — son trabajos largos con binarios; usa el CLI local para eso),
> sin subida de ficheros PDF (pégalo como texto o súbelo en la web y pregunta vía `ask`).
> API no oficial: Google puede cambiar endpoints sin aviso; si `ask` falla con AUTH,
> re-genera el `auth_json` (las cookies caducan en 2-4 semanas).

### 4c. WhatsApp MCP — capacidades

**Cuenta:** solo el número de teléfono. El bridge Baileys vive en un **contenedor por cuenta** (`wa-<slug>`)
en la misma red Docker que el gateway, con **persistencia total** en su volumen (`<session>/`):

#### Mensajes y chats
- `whatsapp_list_chats` → lista **todos** los chats con datos (union del buffer en vivo + historial en disco).
- `whatsapp_get_messages(chat_id, limit)` → mensajes recientes (cae al historial si el chat no está en memoria).
- `whatsapp_get_history(chat_id, limit)` → **historial real desde disco** (`history/<jid>.jsonl`), sobrevive reinicios.
- `whatsapp_get_deleted(chat_id, limit)` → **solo los mensajes borrados** del chat, con su contenido
  (`deleted: true`). Solo funciona con mensajes que ya estaban guardados **antes** de ser borrados.
- `whatsapp_status`, `whatsapp_list_accounts`, `whatsapp_get_group_info`.

#### Media (leer, enviar, transcribir)
- `whatsapp_get_media(message_id)` → devuelve `{size, mimetype, url}` y `base64` **solo si ≤ 4 MB**.
  - Para media grande devuelve un **enlace de descarga**: `http://127.0.0.1:<puerto>/download?id=<id>`
    (el agente lo baja con `curl`). Servido por el bridge `GET /download`.
- `whatsapp_send_media(chat_id, media_type, base64, caption, filename)` → imagen/video/audio/nota de voz/documento/sticker.
- `whatsapp_transcribe_media(message_id, language)` → transcribe audio/voz con el **ASR compartido**
  (por defecto local `faster-whisper`, modelo `base`, **el mismo que usa Hermes**; configurable vía
  `MCP_ASR_PROVIDER/MODEL/BASE_URL/API_KEY/LANGUAGE`).

#### Persistencia
- **Todo lo enviado/recibido se guarda**: metadatos+texto en `history/<jid>.jsonl` y **media en `media/<id>.<ext>`**
  (imágenes, audio/voz, video, PDF, documentos, stickers).
- **Límite**: `WHATSAPP_HISTORY_LIMIT` (default **100 000** líneas por chat). Al podar, **se borra la media**
  de los mensajes que salen para limitar disco. El buffer en memoria es `WHATSAPP_MESSAGE_LIMIT` (default 10 000).

#### Mensajes especiales
- **Stickers** → se detectan (`sticker`), se persisten (webp) y se descargan.
- **Notas de video / video** → se detectan como `video` y se persisten (mp4); se pueden transcribir si traen audio.
- **Mensajes / fotos de "ver una vez" (view-once) y temporales (ephemeral)** → se **detectan** el tipo y se muestra
  su caption, pero **NO se persiste la media** (WhatsApp no permite re-descargarla tras verla una vez;
  el bridge falla limpiamente en `whatsapp_get_media`).
- **Borrados** → cuando el remitente elimina un mensaje ("eliminar para todos"), se **marca**
  (`deleted: true`) pero **nunca se borra** del historial. `whatsapp_get_deleted` los trae con su contenido.
  - El propio mensaje de protocolo REVOKE **no se guarda** como mensaje (antes aparecía como "mensaje vacío").
  - Limitaciones honestas: solo se marcan mensajes **ya guardados** al momento del borrado; el borrado "solo para mí" del remitente es invisible.
- **Ediciones** → no se procesan (queda la versión original).

### 4d. Capacidades de Telegram / Google / Outlook
- **Telegram**: `telegram_get_media`, `telegram_send_media` (foto/video/audio/voz/video-note/archivo),
  `telegram_transcribe_media`; `get_messages` indica el tipo de media.
- **Google (Gmail)**: adjuntos en `google_gmail_get`/`_send`, borradores (`google_gmail_drafts`,
  `google_gmail_draft_create/send`), etiquetas (`google_gmail_labels`), leído/no leído (`google_gmail_set_read`),
  hilos (`google_gmail_thread`), transcribir adjunto (`google_gmail_transcribe_attachment`).
- **Outlook (Graph)**: adjuntos en `outlook_mail_get`/`_send`, leído/no leído (`outlook_mail_set_read`),
  borradores (`outlook_drafts`, `outlook_draft_send`), carpetas (`outlook_folders`),
  transcribir adjunto (`outlook_mail_transcribe_attachment`).
- La transcripción de todas usa el **mismo ASR que Hermes** por defecto.

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
