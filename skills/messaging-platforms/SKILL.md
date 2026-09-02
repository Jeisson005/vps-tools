---
name: messaging-platforms
description: "Enviar y leer mensajes de las cuentas del usuario (WhatsApp, Telegram, Gmail, Outlook) vía MCP; revisa antes de enviar y mantén el tono del historial."
version: 1.0.0
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
| WhatsApp | `whatsapp` | `whatsapp_list_chats`, `whatsapp_get_messages`, `whatsapp_send_message`, `whatsapp_status` |
| Telegram | `telegram` | `telegram_list_chats`, `telegram_get_messages`, `telegram_send_message`, `telegram_status` |
| Gmail / Calendar | `google` | `google_gmail_list`, `google_gmail_get`, `google_gmail_send`, `google_calendar_events`, `google_calendar_create` |
| Outlook / Calendar | `microsoft` | `outlook_mail_list`, `outlook_mail_get`, `outlook_mail_send`, `outlook_calendar_events`, `outlook_calendar_create` |

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

## ⚠️ Limitaciones actuales (transparencia con el usuario)

- Los conectores son **solo texto**: `*_get_messages` devuelve el cuerpo de texto y `*_send_message`/`*_mail_send`
  envían texto. **Aún no** se leen ni envían adjuntos/audiovisuales (imágenes, audio, videos, archivos), ni hay
  gestión de borradores ni marcado de leído/no leído.
- El "historial" disponible es lo que devuelven las tools (mensajes recientes); no hay procesamiento periódico ni
  notificaciones automáticas de mensajes nuevos.
- Si el usuario pide algo fuera de estas capacidades (multimedia, leído/no leído), **dilo claramente** en vez de fingir.

---

## 🔐 Matriz de autorización

| Acción | Comportamiento |
| :--- | :--- |
| 🔍 Listar / leer mensajes y correos | ✅ Autónomo |
| 📅 Consultar calendario | ✅ Autónomo |
| ✉️ Enviar mensaje / correo | ⚠️ Enseñar el contenido y confirmar; enviar por cuenta del usuario |
| 📝 Usar borradores (si existe) | ✅ Al revisar antes de enviar |
| 🔐 Elegir cuenta | Pasar `account`; por defecto la principal |
