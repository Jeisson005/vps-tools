---
name: messaging-platforms
description: "Enviar y leer mensajes de las cuentas del usuario (WhatsApp, Telegram, Gmail, Outlook) vía MCP; revisa antes de enviar y mantén el tono del historial."
version: 1.1.1
author: VPS Tools
license: MIT
metadata:
  hermes:
    tags: [messaging, whatsapp, telegram, gmail, outlook, email, communications, mcp]
    category: communications
    related_skills: [passbolt-credentials]
---

# Messaging Platforms (WhatsApp, Telegram, Gmail, Outlook)

El modelo puede tener acceso a **cuentas de comunicación del usuario** a través del MCP Gateway:

| Plataforma | Servidor MCP | Tools principales |
| :--- | :--- | :--- |
| WhatsApp | `whatsapp` | `whatsapp_list_chats`, `whatsapp_get_messages`, `whatsapp_get_history`, `whatsapp_get_deleted`, `whatsapp_get_media`, `whatsapp_send_message`, `whatsapp_send_media`, `whatsapp_transcribe_media`, `whatsapp_get_group_info`, `whatsapp_status` |
| Telegram | `telegram` | `telegram_list_chats`, `telegram_get_messages`, `telegram_get_media`, `telegram_send_message`, `telegram_send_media`, `telegram_transcribe_media`, `telegram_status` |
| Gmail / Calendar | `google` | `google_gmail_list`, `google_gmail_get` (+adjuntos), `google_gmail_send` (+adjuntos), `google_gmail_drafts`, `google_gmail_draft_create/send`, `google_gmail_labels`, `google_gmail_set_read`, `google_gmail_thread`, `google_gmail_transcribe_attachment`, `google_calendar_*` |
| Outlook / Calendar | `microsoft` | `outlook_mail_list`, `outlook_mail_get` (+adjuntos), `outlook_mail_send` (+adjuntos), `outlook_mail_set_read`, `outlook_drafts`, `outlook_draft_send`, `outlook_folders`, `outlook_mail_transcribe_attachment`, `outlook_calendar_*` |

**Multimedia:** puedes **leer y enviar** imágenes, audio/voz, video y archivos en WhatsApp/Telegram, y **adjuntos** en Gmail/Outlook. Los audios/voz se pueden **transcribir** con `*_transcribe_*` (usa el **mismo ASR que Hermes por defecto**: local `faster-whisper`, modelo `base`, configurable vía `MCP_ASR_*`).

**Borrados (WhatsApp):** los mensajes borrados por el remitente ("eliminar para todos") se **marcan** (`deleted: true`)
pero **nunca se borran** del historial. Usa **`whatsapp_get_deleted`** para traerlos de un chat (solo funciona
con mensajes que ya estaban guardados cuando se borraron).

Cada plataforma tiene **varias cuentas** posibles. Descubre y elige con la tool `*_list_accounts()` de cada una,
y pasa `account` para seleccionar la bóveda/cuenta (si se omite, se usa la cuenta principal).

---

## 🧭 Reglas de uso

1. **Usa el MCP correspondiente.** Si el usuario pide enviar, leer, buscar o consultar algo de una de estas cuentas,
   **usa la tool de esa plataforma**. No inventes ni improvises llamadas a lo que no haya en la plataforma.
   - Enviar/responder → `*_send_message` (WhatsApp/Telegram) o `*_mail_send` (Gmail/Outlook).
   - Leer/buscar → `*_get_messages`, `*_gmail_list`, `*_mail_list`, `*_list_chats`.
   - Solo datos de un chat/hilo → lee primero el contexto (`*_get_messages`) antes de responder.

2. **Confirma antes de enviar (muy importante).** El envío es una acción sensible porque se hace **por cuenta del usuario**.
   - Si el usuario pide *"envía X a Y"* → puedes proceder, pero **muestra en el chat el mensaje exacto** que vas a enviar
     (destinatario + texto) y espera confirmación si hay ambigüedad o si el destinatario/mensaje no está claro.
   - Si el usuario dice *"quiero revisarlo/mirarlo antes"* → **NO envíes todavía**. Pégale el contenido propuesto en el
     chat para que lo revise, y usa **borradores** si la plataforma los expone (Gmail/Outlook: `drafts`), enviando solo
     cuando lo confirme.

3. **Mantén el tono y el contexto.** Para un mensaje **medio o largo** (o cuando el hilo ya tiene historial), antes de
   escribir:
   - Lee los mensajes recientes del chat (`*_get_messages`, `*_gmail_get`, `*_mail_get`) para entender el tema, el tono
     y el estilo que usa la persona.
   - Redacta con un estilo **similar** (formal/informal, emojis, longitud) y respetando el contexto de la conversación.
   - No repitas información que ya está en el hilo.

4. **Prefiere claridad y seguridad.** No reveles secretos ni expongas contenido sensible de otras cuentas sin necesidad.
   Respeta los límites de cada API (longitud, formatos).

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
| ✉️ Enviar mensaje / correo | ⚠️ Enseñar el contenido y confirmar; enviar por cuenta del usuario |
| 📝 Usar borradores (si existe) | ✅ Al revisar antes de enviar |
| 🔐 Elegir cuenta | Pasar `account`; por defecto la principal |
