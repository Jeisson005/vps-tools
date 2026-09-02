---
name: passbolt-credentials
description: "Secure password, TOTP 2FA, and credential management via Passbolt MCP Gateway. Autonomous read-only access for queries, passwords, TOTPs, and folders. Mandatory human confirmation before creating, updating, or deleting any credential."
version: 1.4.2
author: VPS Tools
license: MIT
metadata:
  tags: [passbolt, passwords, credentials, secrets, totp, 2fa, mcp, security, authentication, logins, vault]
  category: security
  related_skills: [browser-automation]
---

# Passbolt Credential Management Skill

Empowers autonomous agents to search, decrypt, generate live 2FA TOTP codes, and manage credentials in the self-hosted **Passbolt Password Manager** vault via the modular **MCP Gateway** (`https://mcp.jeisson.top/passbolt` or local `http://127.0.0.1:8005/passbolt`).

---

## 🔑 MCP Tools Reference

### 🟢 1. Operaciones de Lectura (100% Autónomas - Sin Preguntar)
Ejecuta estas herramientas de forma inmediata y sin pedir confirmación:

* **`passbolt_search_resources(query, folder_id, limit, account)`**:
  Busca credenciales por nombre del servicio, dominio/URL, usuario o palabra clave (ej. `"postgres"`, `"aws"`, `"github.com"`). Devuelve IDs y metadatos sin revelar contraseñas en texto plano en la lista.
* **`passbolt_get_secret(resource_id, account)`**:
  Desencripta y obtiene la información completa de la credencial: contraseña, usuario, URL, descripción, campos personalizados y el **código TOTP 2FA generado en vivo** (con sus segundos restantes de validez).
* **`passbolt_list_folders(parent_id, account)`**:
  Inspecciona la jerarquía y lista de carpetas de la bóveda.
* **`passbolt_list_accounts()`**:
  Lista las **cuentas/bóvedas Passbolt** configuradas en el gateway (id, si es la principal, correo y servidor, sin exponer secretos). Úsala para descubrir los valores válidos de `account` antes de operar sobre una bóveda concreta.

> ⚠️ **Regla de descubrimiento:** cuando te pregunten *"cuántas cuentas gestionas"*, *"qué cuentas tienes"* o
> *"¿puedes gestionar más de una?"*, **SIEMPRE llama primero a `passbolt_list_accounts()`** y responde con su
> resultado. **No infieras el número de cuentas** a partir de las carpetas, credenciales o recursos de una bóveda:
> una bóveda puede contener muchas credenciales y aun así ser solo **una cuenta**. El `enum` del parámetro
> `account` de cada tool también te muestra las cuentas válidas.

---

### 🔴 2. Operaciones de Escritura / Mutación (PROHIBIDO Ejecutar Sin Preguntar)
**NUNCA** ejecutes estas herramientas automáticamente. Debes **SIEMPRE preguntar al usuario y esperar su autorización explícita**:

* **`passbolt_create_resource(name, password, username, uri, description, folder_id, totp_secret, custom_fields, account)`**:
  Crea una nueva credencial en Passbolt con cifrado OpenPGP.
* **`passbolt_update_resource(resource_id, name, password, username, uri, description, folder_id, totp_secret, custom_fields, account)`**:
  Modifica una credencial existente (contraseña, usuario, URL, TOTP, notas o campos).
* **`passbolt_delete_resource(resource_id, account)`**:
  Elimina definitivamente un recurso/credencial de Passbolt.
* **`passbolt_create_folder(name, parent_id, account)`**:
  Crea una nueva carpeta en la bóveda.

> **`account` (opcional):** Nombre/alias de la cuenta Passbolt a usar (`"principal"`, `"rodrigo"`, ...).
> Si se omite se usa la **cuenta principal**. Si solo hay una cuenta configurada, esa se usa automáticamente.
> Antes de operar sobre una cuenta concreta, llama **`passbolt_list_accounts()`** para ver las cuentas
> disponibles y el parámetro `account` de cada tool muestra el `enum` con los IDs válidos.

---

## 📚 Cuentas multiusuario

El gateway puede gestionar **una o varias cuentas de Passbolt** (varias bóvedas/usuarios GPG).
Cada cuenta es independiente: servidor, correo, clave privada y 2FA propios.

* **Cuenta principal:** se usa por defecto cuando se omite el parámetro `account`.
* **Selección explícita:** pasa `account` a cualquier herramienta para usar otra bóveda
  (ej. `passbolt_get_secret(resource_id, account="rodrigo")`).
* **Cuenta única:** si solo hay una cuenta configurada, todas las herramientas la usan
  sin necesidad de especificar `account`.
* Las cuentas se gestionan desde el **Panel de Administración** (Passbolt → Cuentas), donde
  cada una puede subir su propio archivo `.asc`/`.key` y su passphrase.

## 🛡️ Reglas Operativas Estrictas

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                           MATRIZ DE AUTORIZACIÓN                              │
├────────────────────────────────────────┬──────────────────────────────────────┤
│ TIPO DE ACCIÓN                         │ COMPORTAMIENTO EXIGIDO               │
├────────────────────────────────────────┼──────────────────────────────────────┤
│ 🔍 Buscar contraseñas / servicios      │ ✅ AUTÓNOMO: Ejecutar sin preguntar   │
│ 🔓 Leer contraseña / secreto           │ ✅ AUTÓNOMO: Ejecutar sin preguntar   │
│ ⏱️ Obtener código TOTP 2FA             │ ✅ AUTÓNOMO: Ejecutar sin preguntar   │
│ 📁 Listar carpetas de la bóveda        │ ✅ AUTÓNOMO: Ejecutar sin preguntar   │
├────────────────────────────────────────┼──────────────────────────────────────┤
│ ➕ CREAR una nueva credencial           │ ⚠️ BLOQUEADO: Preguntar y esperar ok │
│ ✏️ MODIFICAR una credencial existente   │ ⚠️ BLOQUEADO: Preguntar y esperar ok │
│ 🗑️ ELIMINAR / BORRAR una credencial    │ ⚠️ BLOQUEADO: Preguntar y esperar ok │
│ 📁 CREAR una carpeta                   │ ⚠️ BLOQUEADO: Preguntar y esperar ok │
└────────────────────────────────────────┴──────────────────────────────────────┘
```

---

### 📋 Protocolo Obligatorio para Creación, Modificación o Borrado

Cuando una tarea requiera crear, modificar o eliminar una credencial en Passbolt:

1. **DETÉN LA EJECUCIÓN** y presenta al usuario una ficha clara con los datos:
   * **Acción:** `[Crear Nueva Contraseña | Modificar Contraseña | Eliminar Contraseña | Crear Carpeta]`
   * **Servicio / Título:** `[Nombre del recurso]`
   * **Usuario / Login:** `[Usuario o correo]`
   * **URL / Host:** `[Dominio o URL]`
   * **Cambios propuestos:** `[Detalle de los campos a crear o modificar]`
2. **Formula la pregunta explícita:**
   > *"¿Deseas que proceda a [crear / actualizar / eliminar] esta credencial en Passbolt?"*
3. **ESPERA** a que el usuario responda afirmativamente antes de invocar la tool.

---

## ⚙️ Conexión y Gateway MCP

* **URL del Servicio**: `http://127.0.0.1:8005/passbolt` (interno) / `https://mcp.jeisson.top/passbolt` (público)
* **Transporte**: Streamable HTTP / SSE JSON-RPC 2.0
* **Autenticación**: Cabecera `Authorization: Bearer <MCP_API_KEY>`
