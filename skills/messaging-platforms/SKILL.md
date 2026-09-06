---
name: messaging-platforms
description: "Enviar y leer mensajes del usuario o del agente (WhatsApp, Telegram, Gmail, Outlook); elige el canal correcto y el tono adecuado."
version: 1.2.0
author: VPS Tools
license: MIT
metadata:
  hermes:
    tags: [messaging, whatsapp, telegram, gmail, outlook, email, communications, mcp]
    category: communications
    related_skills: [passbolt-credentials]
---

# Messaging Platforms (WhatsApp, Telegram, Gmail, Outlook)

El modelo puede comunicarse por dos vías distintas. **No las mezcles.** Elegir el canal equivocado hace que un mensaje salga desde la identidad equivocada o que el destinatario nunca lo vea.

## 📡 Los dos canales

1. **Cuentas del usuario vía MCP Gateway.** Una o varias cuentas personales del usuario (WhatsApp, Telegram, Gmail, Outlook), expuestas como servidores MCP (`whatsapp`, `telegram`, `google`, `microsoft`).
   - Todo lo que sale por aquí aparece **como si lo hubiera enviado el propio usuario** desde su número / correo.
   - Puede haber **múltiples cuentas** por plataforma. Descúbrelas con `*_list_accounts()` y selecciona con el parámetro `account` (si se omite, se usa la principal).
2. **Canal propio del agente.** La identidad del bot en cada plataforma (su propio WhatsApp/Telegram/correo de agente, según lo que tenga configurado el gateway local).
   - Todo lo que sale por aquí aparece **como el agente**, no como el usuario.
   - Sirve para responder en el chat donde el usuario te está hablando, o para envíos donde el destinatario espera al agente.

| Plataforma | Servidor MCP (cuentas del usuario) | Tools principales |
| :--- | :--- | :--- |
| WhatsApp | `whatsapp` | `whatsapp_list_chats`, `whatsapp_get_messages`, `whatsapp_get_history`, `whatsapp_get_deleted`, `whatsapp_get_media`, `whatsapp_send_message`, `whatsapp_send_media`, `whatsapp_transcribe_media`, `whatsapp_get_group_info`, `whatsapp_status` |
| Telegram | `telegram` | `telegram_list_chats`, `telegram_get_messages`, `telegram_get_media`, `telegram_send_message`, `telegram_send_media`, `telegram_transcribe_media`, `telegram_status` |
| Gmail / Calendar | `google` | `google_gmail_list`, `google_gmail_get` (+adjuntos), `google_gmail_send` (+adjuntos), `google_gmail_drafts`, `google_gmail_draft_create/send`, `google_gmail_labels`, `google_gmail_set_read`, `google_gmail_thread`, `google_gmail_transcribe_attachment`, `google_calendar_*` |
| Outlook / Calendar | `microsoft` | `outlook_mail_list`, `outlook_mail_get` (+adjuntos), `outlook_mail_send` (+adjuntos), `outlook_mail_set_read`, `outlook_drafts`, `outlook_draft_send`, `outlook_folders`, `outlook_mail_transcribe_attachment`, `outlook_calendar_*` |

**Multimedia:** puedes **leer y enviar** imágenes, audio/voz, video y archivos en WhatsApp/Telegram, y **adjuntos** en Gmail/Outlook. Los audios/voz se pueden **transcribir** con `*_transcribe_*` (usa el **mismo ASR que Hermes por defecto**: local `faster-whisper`, modelo `base`, configurable vía `MCP_ASR_*`).

**Borrados (WhatsApp):** los mensajes borrados por el remitente ("eliminar para todos") se **marcan** (`deleted: true`)
pero **nunca se borran** del historial. Usa **`whatsapp_get_deleted`** para traerlos de un chat (solo funciona
con mensajes que ya estaban guardados cuando se borraron).

---

## 🧭 Reglas de uso

### 1. Elige el canal correcto (lo más importante)

- **Si es respuesta dentro de una conversación activa** (el usuario te habla por un chat y te pide responder ahí o hacer algo en ese mismo hilo): usa **el mismo canal por el que llegó el mensaje**, salvo que el usuario pida explícitamente otro.
- **Si es un envío nuevo sin contexto de conversación** (p. ej. *"envíale X a Y"*, *"escríbele a Z"*): el usuario **debe especificar** si va por su cuenta o por la del agente. Si no lo dice, **pregunta antes de enviar**: *"¿Lo envío desde tu cuenta o desde la mía (agente)?"*. Nunca asumas.
- **Pista rápida:** *"envíalo por mi WhatsApp / mi correo"* = vía MCP con su cuenta. *"respóndeme por aquí / avísale como agente"* = canal del agente.

### 2. Cómo escribir según el canal

- **Por cuenta del usuario (vía MCP):** estás suplantando legítimamente al usuario con su autorización.
  - Si hay historial disponible (`*_get_messages`, `*_gmail_get`, `*_mail_get`), **revísalo primero** y adapta tono, longitud, formalidad y muletillas al estilo previo del usuario en ese hilo.
  - **Escribe como si fueras el propio usuario.** No firmes como agente, no menciones al agente, no añadas aclaraciones tipo *"te escribe el asistente de..."*. El destinatario no debe notar que lo redactó un agente.
  - No repitas información que ya está en el hilo.
- **Por el canal del agente:** escribe con naturalidad como agente.
  - **No necesitas** revisar el historial previo del usuario con ese destinatario ni imitar su estilo.
  - **No te hagas pasar por el usuario.** Si hace falta, identifica brevemente que eres el agente.

### 3. Usa la tool correspondiente

- Enviar/responder → `*_send_message` (WhatsApp/Telegram) o `*_mail_send` (Gmail/Outlook).
- Leer/buscar → `*_get_messages`, `*_gmail_list`, `*_mail_list`, `*_list_chats`.
- No inventes ni improvises llamadas fuera de lo que expone cada plataforma.

### 4. Confirma antes de enviar

El envío es una acción sensible.

- Si el usuario pide *"envía X a Y"* y el canal + destinatario + contenido están claros → puedes proceder, pero **muestra el mensaje exacto** (canal, cuenta, destinatario, texto/adjunto) en tu respuesta.
- Si hay ambigüedad (canal, cuenta, destinatario o contenido) → **pregunta y espera confirmación**.
- Si el usuario dice *"quiero revisarlo antes"* → **NO envíes todavía**. Muestra el borrador en el chat y usa **borradores** si la plataforma los expone (Gmail/Outlook: `drafts`), enviando solo cuando lo confirme.

### 5. Claridad y seguridad

No reveles secretos ni expongas contenido sensible de otras cuentas sin necesidad. Respeta los límites de cada API (longitud, formatos).

---

## ⚠️ Notas y límites (transparencia con el usuario)

- **Media**: leer/enviar imágenes, audio/voz, video y archivos en WhatsApp/Telegram; adjuntos en Gmail/Outlook.
  Para **transcribir** audios/voz usa `*_transcribe_media`/`*_transcribe_attachment`.
- **Historial**: lo que devuelven las tools (mensajes/correos recientes). No hay procesamiento periódico ni
  notificación automática de mensajes nuevos (eso es un watcher aparte).
- **Leído/no leído**: disponible en Gmail (`google_gmail_set_read`) y Outlook (`outlook_mail_set_read`).
- **Borradores**: disponibles en Gmail (`google_gmail_draft_create/send`) y Outlook (`outlook_drafts`/`outlook_draft_send`).
- Si el usuario pide algo fuera de estas capacidades, **dilo claramente** en vez de fingir.

---

## 🔐 Matriz de autorización

| Acción | Comportamiento |
| :--- | :--- |
| 🔍 Listar / leer mensajes y correos | ✅ Autónomo |
| 🗑️ Leer mensajes eliminados (`whatsapp_get_deleted`, ya guardados) | ✅ Autónomo |
| 📅 Consultar calendario | ✅ Autónomo |
| ✉️ Enviar mensaje / correo (cualquier canal) | ⚠️ Canal claro + contenido visible; si hay ambigüedad, confirmar |
| 📝 Usar borradores (si existe) | ✅ Al revisar antes de enviar |
| 🔐 Elegir cuenta MCP | Pasar `account`; por defecto la principal |
