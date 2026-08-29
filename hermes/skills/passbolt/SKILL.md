---
name: passbolt-credentials
description: "Secure password, TOTP, and credential management via Passbolt MCP Gateway. Query and retrieve secrets and TOTP 2FA codes autonomously, with mandatory human confirmation for creating, updating, or deleting credentials."
version: 1.1.0
author: VPS Tools
license: MIT
metadata:
  hermes:
    tags: [passbolt, passwords, credentials, secrets, totp, 2fa, mcp, security, authentication, logins, vault]
    category: security
    related_skills: [browser-automation]
---

# Passbolt Credential Management Skill

Empowers autonomous agents to search, decrypt, generate live 2FA TOTP codes, and manage credentials in the self-hosted **Passbolt Password Manager** vault via the modular **MCP Gateway** (`https://mcp.jeisson.top/passbolt` or local `http://127.0.0.1:8005/passbolt`).

---

## 🔑 Available MCP Tools

### Consultas y Lectura (Autónomas)
* **`passbolt_search_resources(query, folder_id, limit)`**:
  Search for credentials by service name, URL domain, username, or keyword (e.g. `"postgres"`, `"aws"`, `"github.com"`). Returns matching resource IDs, names, usernames, and URIs **without** exposing plaintext secrets in the list.
* **`passbolt_get_secret(resource_id)`**:
  Decrypted retrieval of the password, username, URI, description, **live 2FA TOTP code** (with expiration countdown), and custom fields for a specific resource UUID.
* **`passbolt_list_folders(parent_id)`**:
  Inspect vault organizational hierarchy and folders.

### Mutaciones y Escritura (Requieren Confirmación del Usuario)
* **`passbolt_create_resource(name, password, username, uri, description, folder_id, totp_secret, custom_fields)`**:
  Create a new credential resource with client-side OpenPGP encryption.
* **`passbolt_update_resource(resource_id, name, password, username, uri, description, folder_id, totp_secret, custom_fields)`**:
  Update an existing credential resource (password, username, URI, TOTP secret, custom fields) with OpenPGP re-encryption.
* **`passbolt_delete_resource(resource_id)`**:
  Delete / remove a credential resource from Passbolt vault.
* **`passbolt_create_folder(name, parent_id)`**:
  Create a new folder to categorize credentials.

---

## 🛡️ Operational Guidelines & Safety Rules

### 1. Consultas y Uso Autónomo (Libre y Sin Restricciones)
* **Lectura libre:** Tienes autorización para buscar credenciales, desencriptar contraseñas y obtener códigos TOTP 2FA de forma autónoma siempre que sea necesario para cumplir una tarea del usuario (ej. desplegar bases de datos, iniciar sesión en servicios web con Steel Browser, automatizar tareas).
* **Búsqueda primero:** Llama siempre a `passbolt_search_resources` con el nombre o dominio del servicio para localizar el `resource_id` exacto antes de llamar a `passbolt_get_secret`.
* **Soporte TOTP:** Si la credencial cuenta con 2FA configurado en Passbolt (campo `totp` o URI `otpauth://`), `passbolt_get_secret` entregará el código TOTP numérico listo para autenticación junto con los segundos restantes de validez.
* **Discreción de texto plano:** No imprimas contraseñas en texto plano en tus respuestas a menos que el usuario te lo pida explícitamente.

### 2. Creaciones y Modificaciones (Estrictamente con Confirmación Humana)
> [!CRITICAL]
> **CONFIRMACIÓN OBLIGATORIA PARA ESCRITURA:**
> Tienes **ESTRICTAMENTE PROHIBIDO** ejecutar `passbolt_create_resource`, `passbolt_update_resource` o `passbolt_delete_resource` de manera silenciosa o automática.
> **SIEMPRE debes preguntar al usuario y esperar su autorización explícita antes de ejecutar cualquier cambio en la bóveda.**

Antes de crear, modificar o eliminar una credencial:
1. Presenta claramente al usuario un resumen con:
   - **Acción a realizar:** (Crear nueva credencial / Actualizar contraseña / Eliminar credencial)
   - **Nombre del Servicio:** (ej. `PostgreSQL Producción`)
   - **Usuario / Login:** (ej. `admin_db`)
   - **URL / Dominio:** (ej. `https://db.articc.top`)
2. Pregunta: *"¿Deseas que proceda con esta acción en Passbolt?"*
3. **Espera la respuesta afirmativa del usuario** antes de llamar a la tool correspondiente.

---

## ⚙️ Configuration & Connection Reference

* **Endpoint**: `https://mcp.jeisson.top/passbolt` (o interno `http://127.0.0.1:8005/passbolt`)
* **Transport**: Streamable HTTP / SSE JSON-RPC 2.0
* **Authentication**: `Authorization: Bearer <MCP_API_KEY>` o cabecera `X-API-Key: <MCP_API_KEY>`
